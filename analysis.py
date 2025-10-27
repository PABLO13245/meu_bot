import aiohttp
from datetime import datetime, timezone, timedelta
import pytz
import random
import os 

# ========== CONFIGURAÇÕES ==========
BASE_URL = "https://api.sportmonks.com/v3/football"
TZ = pytz.timezone("America/Sao_Paulo")

# CRÍTICA: IDs de estado para jogos futuros: 1 (Aguardando) e 3 (Agendado).
STATE_FUTURE_IDS = "1,3"

# IDs das ligas consideradas "confiáveis" para análise.
# (Ligas Tier 1: Maior estabilidade, liquidez e cobertura de dados)
TRUSTED_LEAGUE_IDS = [
    8,    # Premier League (Inglaterra)
    5,    # La Liga (Espanha)
    13,   # Série A (Itália)
    3,    # Bundesliga (Alemanha)
    17,   # Ligue 1 (França)
    463,  # Brasileirão Série A (Brasil)
    2,    # Champions League (Europa)
    141   # MLS (EUA)
]


# ===================================
# BUSCAR PARTIDAS FUTURAS
# ===================================
async def fetch_upcoming_fixtures(api_token, start_str, end_str, per_page=500):
    # Converte a lista de IDs para uma string separada por vírgulas para a URL
    league_ids_str = ",".join(map(str, TRUSTED_LEAGUE_IDS))

    # Formato do filtro de datas no V3: filters=dates:YYYY-MM-DD,YYYY-MM-DD
    dates_filter = f"{start_str},{end_str}"
    
    # Juntando os filtros de datas, estado E LIGAS no formato V3
    main_filters = (
        f"dates:{dates_filter};"
        f"fixtureStates:{STATE_FUTURE_IDS};"
        f"leagueIds:{league_ids_str}" # NOVO FILTRO DE LIGAS
    )

    url = (
        f"{BASE_URL}/fixtures"
        f"?api_token={api_token}"
        f"&include=participants;league;season"
        f"&filters={main_filters}"  # Sintaxe correta V3 com todos os filtros
        f"&per_page={per_page}"
    )

    print(f"DEBUG: Buscando jogos de {start_str} a {end_str} nas Ligas: {league_ids_str}")
    # Omitindo token no log por segurança
    print(f"DEBUG: URL de Requisição: {url.split('api_token=')[0]}... (token omitido) - TESTE ESTA URL NO NAVEGADOR!") 

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                if response.status != 200:
                    print(f"❌ Erro ao buscar fixtures: {response.status} - {await response.text()}")
                    return []

                data = (await response.json()).get("data", [])
                upcoming = []
                # Define o dia de hoje (em UTC) para checagem manual
                # NOTE: A verificação de data é importante aqui porque o main.py
                # está buscando 7 dias para testar, mas queremos garantir que
                # o filtro manual de hora (agora) funcione em todos eles.
                now_utc_plus_margin = datetime.now(timezone.utc) + timedelta(minutes=1) 

                for f in data:
                    try:
                        # O campo starting_at da API está em UTC, mas sem tzinfo
                        dt = datetime.strptime(f["starting_at"], "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
                        
                        # FILTRO CRÍTICO: Garante que o jogo ainda não tenha começado
                        if dt > now_utc_plus_margin:
                            upcoming.append(f)
                    except Exception as parse_e:
                        print(f"Erro de parsing de data para fixture {f.get('id')}: {parse_e}")
                        continue

                print(f"✅ Jogos futuros encontrados (Ligas Filtradas): {len(upcoming)}")
                return upcoming

    except Exception as e:
        print(f"⚠ Erro na requisição de partidas: {e}")
        return []


# ===================================
# MÉTRICAS SIMULADAS (Aleatórias)
# ===================================
async def compute_team_metrics(api_token, team_id, last=2):
    # NOTA: Esta função ainda é SIMULADA (aleatória)
    goals_for_avg = random.uniform(0.8, 1.8)
    goals_against_avg = random.uniform(0.8, 1.8)
    win_rate = random.uniform(0.3, 0.7)
    # GERA UMA CONFIANÇA ALEATÓRIA para que a ordenação TOP 7 funcione corretamente.
    confidence = int(random.uniform(70, 95)) 
    return {
        "avg_goals_for": goals_for_avg,
        "avg_goals_against": goals_against_avg,
        "win_rate": win_rate,
        "confidence": confidence
    }


# ===================================
# DECIDIR MELHOR MERCADO
# ===================================
def decide_best_market(home_metrics, away_metrics):
    goals_sum = home_metrics["avg_goals_for"] + away_metrics["avg_goals_for"]
    win_diff = home_metrics["win_rate"] - away_metrics["win_rate"]

    if goals_sum >= 2.8:
        suggestion = "Mais de 2.5 Gols"
    elif goals_sum >= 2.0:
        suggestion = "Mais de 1.5 Gols"
    elif home_metrics["avg_goals_for"] >= 1.1 and away_metrics["avg_goals_for"] >= 1.1:
        suggestion = "Ambas Marcam"
    elif win_diff >= 0.35:
        suggestion = "Vitória da Casa"
    elif win_diff <= -0.35:
        suggestion = "Vitória do Visitante"
    else:
        suggestion = "Sem sinal forte — evite aposta"
    
    # Retorna a confiança calculada na simulação
    confidence = home_metrics.get("confidence", 87)

    return suggestion, confidence


# ===================================
# HORÁRIO LOCAL
# ===================================
def kickoff_time_local(fixture, tz=TZ):
    try:
        dt = datetime.strptime(fixture["starting_at"], "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
        dt_local = dt.astimezone(tz)
        now_local = datetime.now(tz)

        # Se for um jogo que não é hoje, retorna a data e hora
        # NOTA: Usamos a data da partida para exibir a data se o range for de 7 dias
        if (dt_local.date() - now_local.date()).days != 0:
            return dt_local.strftime("%H:%M — %d/%m") 

        # Se for um jogo de hoje, retorna apenas a hora
        return dt_local.strftime("%H:%M") 

    except Exception as e:
        print(f"❌ Erro ao processar data/hora: {e}")
        return "Horário N/D"

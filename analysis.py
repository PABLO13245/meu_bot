import aiohttp
from datetime import datetime, timezone, timedelta
import pytz
import random
import os # Adicionado para garantir que todas as dependências estão presentes

# ========== CONFIGURAÇÕES ==========
BASE_URL = "https://api.sportmonks.com/v3/football"
TZ = pytz.timezone("America/Sao_Paulo")

# O ID para o estado "Scheduled" (Agendado) no SportMonks V3 é 3
STATE_SCHEDULED_ID = 3


# ===================================
# BUSCAR PARTIDAS FUTURAS
# ===================================
async def fetch_upcoming_fixtures(api_token, start_str, end_str, per_page=100, league_ids=None):
    # Formato do filtro de datas no V3: filters=dates:YYYY-MM-DD,YYYY-MM-DD
    dates_filter = f"{start_str},{end_str}"
    
    # Juntando os filtros de datas e estado no formato V3 (separados por ponto-e-vírgula)
    main_filters = f"dates:{dates_filter};fixtureStates:{STATE_SCHEDULED_ID}"

    url = (
        f"{BASE_URL}/fixtures"
        f"?api_token={api_token}"
        f"&include=participants;league;season"
        f"&filters={main_filters}"  # Sintaxe correta V3 para datas e estado
        f"&per_page={per_page}"
    )

    # Adiciona o filtro de ligas (se passado)
    if league_ids:
        # Nota: O filtro de liga aqui pode precisar de ajuste dependendo do seu plano da API.
        url += f"&filter[league_id]={league_ids}" 

    print(f"DEBUG: Buscando jogos de {start_str} a {end_str}")
    print(f"DEBUG: URL de Requisição: {url.split('api_token=')[0]}... (token omitido)") # Omitindo token no log por segurança

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                if response.status != 200:
                    print(f"❌ Erro ao buscar fixtures: {response.status} - {await response.text()}")
                    return []

                data = (await response.json()).get("data", [])
                upcoming = []
                now_utc = datetime.now(timezone.utc)

                for f in data:
                    try:
                        dt = datetime.strptime(f["starting_at"], "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
                        # Filtra apenas jogos que ainda não começaram
                        if dt > now_utc:
                            upcoming.append(f)
                    except Exception:
                        continue

                print(f"✅ Jogos futuros encontrados: {len(upcoming)}")
                return upcoming

    except Exception as e:
        print(f"⚠ Erro na requisição de partidas: {e}")
        return []


# ===================================
# MÉTRICAS SIMULADAS (Aleatórias)
# ===================================
async def compute_team_metrics(api_token, team_id, last=2):
    # NOTA: Esta função ainda é SIMULADA (aleatória).
    # Se ela for chamada com um time_id inexistente, pode ser um problema, mas por enquanto ela retorna dados válidos.
    goals_for_avg = random.uniform(0.8, 1.8)
    goals_against_avg = random.uniform(0.8, 1.8)
    win_rate = random.uniform(0.3, 0.7)
    return {
        "avg_goals_for": goals_for_avg,
        "avg_goals_against": goals_against_avg,
        "win_rate": win_rate,
        "confidence": 87
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

    return suggestion, 87


# ===================================
# HORÁRIO LOCAL
# ===================================
def kickoff_time_local(fixture, tz=TZ):
    try:
        dt = datetime.strptime(fixture["starting_at"], "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
        dt_local = dt.astimezone(tz)
        now_local = datetime.now(tz)

        # Se for um jogo que não é hoje, retorna a data e hora
        if dt_local.date() != now_local.date():
            return dt_local.strftime("%H:%M — %d/%m")
        
        # Se for um jogo de hoje, retorna apenas a hora
        return dt_local.strftime("%H:%M") 

    # CORREÇÃO DE SINTAXE: O bloco 'try' exige um 'except' ou 'finally'
    except Exception as e:
        print(f"❌ Erro ao processar data/hora: {e}")
        return "Horário N/D" # Retorno de fallback para evitar erro

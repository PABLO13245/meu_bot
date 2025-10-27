import asyncio
import aiohttp
from datetime import datetime, timezone
import pytz

# Configurações Base
BASE_URL = "https://api.sportmonks.com/v3/football"
STATE_FUTURE_IDS = "1,3" # 1=Awaiting, 3=Scheduled 
# Removido o filtro de ligas confiáveis (TRUSTED_LEAGUE_IDS). O bot buscará TODAS as ligas.

# Mapeamento manual para corrigir ligas onde o código do país está ausente (Ex: Suécia)
MANUAL_COUNTRY_MAP = {
    "Allsvenskan": "SE", 
}

# Mapeamento de Países para Bandeiras (Emojis)
def get_flag_emoji(country_code):
    """Converte o código de país (ISO 3166-1 alpha-2) em emoji de bandeira."""
    if country_code is None or len(country_code) != 2:
        return ""
    # Emojis de bandeira são gerados a partir de 2 caracteres regionais:
    # chr(127462 + offset) é o ponto de código Unicode para o caractere de bandeira regional
    return "".join(chr(0x1F1E6 + ord(char) - ord('A')) for char in country_code.upper())


# ----------------------------------------------------------------------
# FUNÇÕES DE BUSCA DA API
# ----------------------------------------------------------------------

async def fetch_upcoming_fixtures(api_token, start_date, per_page=100):
    """Busca jogos futuros na API da SportMonks, filtrando apenas por data e estado (TODAS AS LIGAS)."""
    
    # Filtro de data e estado (AGORA SEM O FILTRO DE LEAGUE IDS)
    main_filters = f"dates:{start_date};fixtureStates:{STATE_FUTURE_IDS}"
    
    url = (
        f"{BASE_URL}/fixtures"
        f"?api_token={api_token}"
        f"&include=participants;league;season;participants.country;league.country"
        f"&filters={main_filters}"
        f"&per_page={per_page}"
    )
    
    # DEBUG: URL de Requisição (token omitido por segurança)
    print(f"DEBUG: Buscando jogos de {start_date} em TODAS as ligas.")
    print(f"DEBUG: URL de Requisição: {url.split('api_token=')[0]}... (token omitido) - TESTE ESTA URL NO NAVEGADOR!")
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                if response.status != 200:
                    print(f"❌ Erro ao buscar fixtures: {response.status} - {await response.text()}")
                    return []
                
                data = await response.json()
                fixtures = data.get("data", [])
                
                # CORREÇÃO PÓS-PROCESSAMENTO: Injetar códigos de país se ausentes (Bandeiras)
                for f in fixtures:
                    league_name = f.get("league", {}).get("name")
                    
                    # 1. Tenta usar mapeamento manual para a liga
                    if league_name in MANUAL_COUNTRY_MAP:
                        country_code = MANUAL_COUNTRY_MAP[league_name]
                        f['league']['country'] = {'code': country_code}
                        
                        # 2. Injeta o código do país da liga nos times (se o time não tiver)
                        for p in f.get('participants', []):
                            if 'country' not in p or not p['country'].get('code'):
                                p['country'] = {'code': country_code}

                print(f"✅ Jogos futuros encontrados (Todas as Ligas): {len(fixtures)}")
                return fixtures
                
    except Exception as e:
        print(f"❌ Erro na requisição de fixtures: {e}")
        return []

async def compute_team_metrics(api_token, team_id, last=5):
    """
    Simula a busca e cálculo de métricas de uma equipe.
    (Em uma versão real, este seria o ponto onde você buscar a performance real do time)
    """
    
    # Simulação: Retornamos dados simulados com variações para que a ordenação funcione.
    import random
    
    # Gera uma pequena variação para simular diferentes estatísticas de times
    if random.random() < 0.1: # 10% de chance de ter um time ruim
        gols_marcados = random.randint(0, 5)
        gols_sofridos = random.randint(5, 10)
        vitorias = random.randint(0, 2)
    else: # 90% de chance de ter um time mediano/bom
        gols_marcados = random.randint(5, 10)
        gols_sofridos = random.randint(3, 7)
        vitorias = random.randint(2, 4)
        
    return {
        "team_id": team_id,
        "goals_scored": gols_marcados,
        "goals_conceded": gols_sofridos,
        "wins": vitorias,
        "avg_gs": gols_marcados / last,
        "avg_gc": gols_sofridos / last,
        "form_score": (vitorias / last) * 100 # Pontuação baseada em vitórias
    }


# ----------------------------------------------------------------------
# FUNÇÕES DE ANÁLISE E DECISÃO
# ----------------------------------------------------------------------

def decide_best_market(home_metrics, away_metrics):
    """
    Decide a melhor sugestão de aposta e calcula a confiança.
    (Lógica altamente simplificada para demonstração)
    """
    
    # 1. CÁLCULO DE FORÇA
    
    # Média de gols esperados do jogo
    total_avg_goals = home_metrics["avg_gs"] + away_metrics["avg_gc"] + \
                      away_metrics["avg_gs"] + home_metrics["avg_gc"]
                      
    total_avg_goals /= 2 # Média por partida
    
    # Força relativa de cada time
    home_form = home_metrics["form_score"]
    away_form = away_metrics["form_score"]
    
    form_diff = abs(home_form - away_form)
    
    
    # 2. DECISÃO (SIMPLIFICADA)
    
    suggestion = "Sem sinal forte — evite aposta"
    confidence = 50 # Base
    
    # Analisando o mercado de Gols
    if total_avg_goals >= 2.8:
        suggestion = "Mais de 2.5 Gols"
        confidence += int(min(total_avg_goals * 10, 40)) # Aumenta confiança com a média
    elif total_avg_goals >= 2.0:
        suggestion = "Mais de 1.5 Gols"
        confidence += int(min(total_avg_goals * 10, 30))
        
    # Analisando o mercado de Vencedor (se a diferença de forma é grande)
    if form_diff > 40:
        winner = "Casa" if home_form > away_form else "Fora"
        if winner == "Casa" and home_metrics["avg_gs"] > 2:
            suggestion = f"Vitória do Time da Casa ({winner})"
            confidence = max(confidence, 80) # Sobe a confiança para alto
        elif winner == "Fora" and away_metrics["avg_gs"] > 1.8:
            suggestion = f"Vitória do Time Visitante ({winner})"
            confidence = max(confidence, 80)

    # Garante que a confiança fique entre 50% e 99%
    confidence = min(99, max(50, confidence))

    return suggestion, confidence

def kickoff_time_local(fixture, tz, return_datetime=False):
    """Converte a string de horário UTC da API para horário local (BRT) e formata."""
    
    # String da API está no formato: YYYY-MM-DD HH:MM:SS
    starting_at_str = fixture.get("starting_at") 
    
    if not starting_at_str:
        return "N/A"
        
    try:
        # 1. Parsear como UTC
        dt_utc = datetime.strptime(starting_at_str, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
        
        # 2. Converter para o fuso horário local (BRT)
        dt_local = dt_utc.astimezone(tz)
        
        if return_datetime:
            return dt_local
        
        # 3. Formatar
        # Se for HOJE, mostra apenas a hora. Se for amanhã ou depois, mostra hora e data.
        now_local = datetime.now(tz).date()
        if dt_local.date() == now_local:
            return dt_local.strftime("%H:%M")
        else:
            return dt_local.strftime("%H:%M — %d/%m")
            
    except Exception as e:
        print(f"Erro ao processar data {starting_at_str}: {e}")
        if return_datetime:
            # Retorna a data atual como fallback em caso de erro (para evitar quebras no filtro)
            return datetime.now(tz)
        return "Erro de data"

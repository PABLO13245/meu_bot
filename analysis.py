import asyncio
import aiohttp
from datetime import datetime, timezone
import pytz
import random

# Configurações Base
BASE_URL = "https://api.sportmonks.com/v3/football"
STATE_FUTURE_IDS = "1,3" # 1=Awaiting, 3=Scheduled 

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
    return "".join(chr(0x1F1E6 + ord(char) - ord('A')) for char in country_code.upper())


# ----------------------------------------------------------------------
# FUNÇÕES DE BUSCA DA API
# ----------------------------------------------------------------------

async def fetch_upcoming_fixtures(api_token, start_date, per_page=100):
    """Busca jogos futuros na API da SportMonks, filtrando apenas por data e estado (TODAS AS LIGAS)."""
    
    main_filters = f"dates:{start_date};fixtureStates:{STATE_FUTURE_IDS}"
    
    url = (
        f"{BASE_URL}/fixtures"
        f"?api_token={api_token}"
        f"&include=participants;league;season;participants.country;league.country"
        f"&filters={main_filters}"
        f"&per_page={per_page}"
    )
    
    print(f"DEBUG: Buscando jogos de {start_date} em TODAS as ligas.")
    
    try:
        async with aiohttp.ClientSession() as session:
            max_retries = 3
            for attempt in range(max_retries):
                async with session.get(url) as response:
                    if response.status == 200:
                        data = await response.json()
                        fixtures = data.get("data", [])
                        
                        # CORREÇÃO PÓS-PROCESSAMENTO
                        for f in fixtures:
                            league_name = f.get("league", {}).get("name")
                            if league_name in MANUAL_COUNTRY_MAP:
                                country_code = MANUAL_COUNTRY_MAP[league_name]
                                f['league']['country'] = {'code': country_code}
                                for p in f.get('participants', []):
                                    if 'country' not in p or not p['country'].get('code'):
                                        p['country'] = {'code': country_code}

                        print(f"✅ Jogos futuros encontrados (Todas as Ligas): {len(fixtures)}")
                        return fixtures
                    
                    elif response.status == 429 and attempt < max_retries - 1:
                        wait_time = 2 ** attempt 
                        print(f"⚠ Rate Limit atingido (429). Tentando novamente em {wait_time}s...")
                        await asyncio.sleep(wait_time)
                    else:
                        print(f"❌ Erro ao buscar fixtures: {response.status} - {await response.text()}")
                        return []
                        
            return []
                
    except Exception as e:
        print(f"❌ Erro na requisição de fixtures: {e}")
        return []

async def compute_team_metrics(api_token, team_id, last=5):
    """
    Simula a busca e cálculo de métricas de uma equipe, incluindo gols, escanteios e HT.
    """
    await asyncio.sleep(random.uniform(0.1, 0.5)) 
    
    # Simulação: Retornamos dados simulados
    
    if random.random() < 0.05: # 5% de chance de time ruim
        gols_marcados = random.randint(0, 5)
        gols_sofridos = random.randint(5, 10)
        vitorias = random.randint(0, 2)
        escanteios = random.randint(15, 25) # Total em 5 jogos (média 3-5)
        gols_ht = random.randint(0, 3) # Total em 5 jogos
    else: # 95% de chance de time mediano/bom
        gols_marcados = random.randint(7, 12) 
        gols_sofridos = random.randint(3, 8) 
        vitorias = random.randint(3, 5) 
        escanteios = random.randint(30, 45) # Total em 5 jogos (média 6-9)
        gols_ht = random.randint(3, 7) # Total em 5 jogos
        
    return {
        "team_id": team_id,
        "goals_scored": gols_marcados,
        "goals_conceded": gols_sofridos,
        "wins": vitorias,
        "avg_gs": gols_marcados / last,
        "avg_gc": gols_sofridos / last,
        "form_score": (vitorias / last) * 100,
        # NOVAS MÉTRICAS SIMULADAS
        "avg_corners_for": escanteios / last,
        "avg_ht_goals_for": gols_ht / last
    }


# ----------------------------------------------------------------------
# FUNÇÕES DE ANÁLISE E DECISÃO
# ----------------------------------------------------------------------

def decide_best_market(home_metrics, away_metrics):
    """
    Decide a melhor sugestão de aposta e calcula a confiança, analisando múltiplos mercados.
    """
    
    best_suggestion = "Sem sinal forte — evite aposta"
    max_confidence = 50 # Confiança base
    
    
    # --- 1. ANÁLISE GERAL DE GOLS (FULL TIME) ---
    
    # Média de gols total esperado no jogo
    total_avg_goals = home_metrics["avg_gs"] + away_metrics["avg_gc"] + \
                      away_metrics["avg_gs"] + home_metrics["avg_gc"]
                      
    total_avg_goals /= 2 
    
    
    # Avaliação do mercado de gols (Over 1.5, Over 2.5)
    confidence_goals = 50
    suggestion_goals = "Sem sinal"
    
    if total_avg_goals >= 2.8:
        suggestion_goals = "Mais de 2.5 Gols (Over 2.5 FT)"
        confidence_goals += int(min(total_avg_goals * 10, 40)) 
    elif total_avg_goals >= 2.0:
        suggestion_goals = "Mais de 1.5 Gols (Over 1.5 FT)"
        confidence_goals += int(min(total_avg_goals * 10, 30))
        
    if confidence_goals > max_confidence:
        max_confidence = confidence_goals
        best_suggestion = suggestion_goals


    # --- 2. ANÁLISE VENCEDOR (1X2) ---
    
    home_form = home_metrics["form_score"]
    away_form = away_metrics["form_score"]
    form_diff = abs(home_form - away_form)
    
    confidence_winner = 50
    suggestion_winner = "Sem sinal"
    
    if form_diff > 40:
        winner = "Casa" if home_form > away_form else "Fora"
        if winner == "Casa" and home_metrics["avg_gs"] > 2.0:
            suggestion_winner = "Vitória do Time da Casa (ML Home)"
            confidence_winner = max(confidence_winner, 80) 
        elif winner == "Fora" and away_metrics["avg_gs"] > 1.8:
            suggestion_winner = "Vitória do Time Visitante (ML Away)"
            confidence_winner = max(confidence_winner, 80)
            
    if confidence_winner > max_confidence:
        max_confidence = confidence_winner
        best_suggestion = suggestion_winner


    # --- 3. ANÁLISE ESCANTEIOS (CORNERS) ---
    
    # Escanteios For (time que ataca) + Escanteios Against (time que sofre pressão/defende)
    # Aqui vamos usar a média simples dos escanteios marcados por cada um
    total_avg_corners = home_metrics["avg_corners_for"] + away_metrics["avg_corners_for"]
    
    confidence_corners = 50
    suggestion_corners = "Sem sinal"
    
    # Se a soma das médias for alta (ex: 7 + 7 = 14)
    if total_avg_corners >= 10.5:
        suggestion_corners = "Mais de 10.5 Escanteios (Over 10.5 CR)"
        confidence_corners += int(min((total_avg_corners - 10) * 10, 40)) # Aumenta 10% a cada corner extra
    elif total_avg_corners >= 9.0:
        suggestion_corners = "Mais de 9.5 Escanteios (Over 9.5 CR)"
        confidence_corners += int(min((total_avg_corners - 9) * 10, 30))

    if confidence_corners > max_confidence:
        max_confidence = confidence_corners
        best_suggestion = suggestion_corners
        
        
    # --- 4. ANÁLISE GOLS NO PRIMEIRO TEMPO (HT GOALS) ---
    
    # Média de Gols no HT: Somas das médias de Gols no HT marcados por cada time
    total_avg_ht_goals = home_metrics["avg_ht_goals_for"] + away_metrics["avg_ht_goals_for"]
    
    confidence_ht = 50
    suggestion_ht = "Sem sinal"
    
    # Se a média total de Gols no HT for alta (ex: 0.8 + 0.8 = 1.6)
    if total_avg_ht_goals >= 1.5:
        suggestion_ht = "Mais de 1.5 Gols (Over 1.5 HT)"
        # Aumenta confiança se a média for bem alta
        confidence_ht += int(min((total_avg_ht_goals - 1.0) * 20, 40)) 
    elif total_avg_ht_goals >= 0.8:
        suggestion_ht = "Mais de 0.5 Gols (Over 0.5 HT)"
        confidence_ht += int(min((total_avg_ht_goals - 0.5) * 20, 30))

    if confidence_ht > max_confidence:
        max_confidence = confidence_ht
        best_suggestion = suggestion_ht

    # Garante que a confiança fique entre 50% e 99%
    final_confidence = min(99, max(50, max_confidence))

    return best_suggestion, final_confidence

def kickoff_time_local(fixture, tz, return_datetime=False):
    """Converte a string de horário UTC da API para horário local (BRT) e formata."""
    
    starting_at_str = fixture.get("starting_at") 
    
    if not starting_at_str:
        return datetime.now(tz) if return_datetime else "N/A"
        
    try:
        dt_utc = datetime.strptime(starting_at_str, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
        dt_local = dt_utc.astimezone(tz)
        
        if return_datetime:
            return dt_local
        
        now_local = datetime.now(tz).date()
        if dt_local.date() == now_local:
            return dt_local.strftime("%H:%M")
        else:
            return dt_local.strftime("%H:%M — %d/%m")
            
    except Exception as e:
        print(f"Erro ao processar data {starting_at_str}: {e}")
        return datetime.now(tz) if return_datetime else "Erro de data"

import asyncio
import aiohttp
from datetime import datetime, timezone, timedelta
import pytz
import random
import numpy as np # Dependência que precisa estar no requirements.txt

# Configurações Base
BASE_URL = "https://api.sportmonks.com/v3/football"
STATE_FUTURE_IDS = "1,3" # 1=Awaiting, 3=Scheduled 
STATE_FINISHED_ID = "2" # 2=Finished (Para histórico)

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

async def fetch_upcoming_fixtures(api_token, per_page=100):
    """
    Busca jogos futuros na API da SportMonks SEM filtro de data de início, 
    confiando no filtro de 48h do Python para jogos próximos.
    """
    
    # Filtro agora é apenas o estado (Awaiting, Scheduled)
    main_filters = f"fixtureStates:{STATE_FUTURE_IDS}"
    
    # Adicionamos "seasons" para garantir que todos os dados relacionados ao ano estão vindo.
    url = (
        f"{BASE_URL}/fixtures"
        f"?api_token={api_token}"
        f"&include=participants;league;season;participants.country;league.country"
        f"&filters={main_filters}"
        f"&per_page={per_page}"
    )
    
    print(f"DEBUG: Buscando jogos futuros em TODAS as ligas (sem filtro de data).")
    
    try:
        async with aiohttp.ClientSession() as session:
            max_retries = 3
            for attempt in range(max_retries):
                async with session.get(url) as response:
                    if response.status == 200:
                        data = await response.json()
                        fixtures = data.get("data", [])
                        
                        # CORREÇÃO PÓS-PROCESSAMENTO para ligas com dados incompletos
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
    Busca os últimos 'last' jogos do time na API para calcular métricas reais.
    
    Retorna métricas baseadas em 0.0 se o histórico estiver vazio ou falhar.
    """
    
    # Métrica default em caso de falha ou dados ausentes
    DEFAULT_METRICS_ZERO = {
        "avg_gs": 0.0, "avg_gc": 0.0, "form_score": 0.0,
        "avg_corners_for": 0.0, "avg_ht_goals_for": 0.0,
        "games_count": 0
    }

    # Endpoint para fixtures do time, com filtro 'Finished', ordenado por data descendente
    # Inclui 'periods' para garantir que os tempos de jogo (HT) sejam capturados corretamente.
    url = (
        f"{BASE_URL}/fixtures"
        f"?api_token={api_token}"
        f"&filters=teams:{team_id},fixtureStates:{STATE_FINISHED_ID}"
        f"&sort=starting_at:desc"
        f"&per_page={last}"
        f"&include=scores;corners;participants;periods" # Incluir periods para HT score
    )
    
    metrics = {
        "goals_scored": 0,
        "goals_conceded": 0,
        "wins": 0,
        "draws": 0,
        "losses": 0,
        "escanteios": 0,
        "gols_ht": 0,
        "total_games": 0 
    }
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                if response.status != 200:
                    print(f"❌ Erro HTTP {response.status} ao buscar histórico do time {team_id}.")
                    return DEFAULT_METRICS_ZERO

                data = await response.json()
                historical_fixtures = data.get("data", [])
                
                metrics["total_games"] = len(historical_fixtures)
                
                # VERIFICAÇÃO CRÍTICA: Se não houver jogos finalizados para análise
                if metrics["total_games"] == 0:
                    print(f"⚠ Time {team_id} não tem jogos finalizados na base de dados da API.")
                    return DEFAULT_METRICS_ZERO

                for f in historical_fixtures:
                    
                    # 1. Identificar se o time era Home ou Away
                    is_home_game = next((p for p in f.get("participants", []) if p["id"] == team_id and p["meta"]["location"] == "home"), None)
                    
                    # 2. Extrair Scores (FT e HT)
                    scores = f.get("scores", [])
                    
                    ft_score = next((s for s in scores if s["description"] == "FT"), None)
                    
                    # O score HT agora é extraído do array 'periods'
                    ht_period = next((p for p in f.get("periods", []) if p["description"] == "1ST HALF"), None)

                    # --- Análise FT ---
                    if ft_score:
                        if is_home_game:
                            gs = ft_score.get("score", 0)
                            gc = ft_score.get("opponent_score", 0)
                        else: # Jogo Fora (Away)
                            gs = ft_score.get("opponent_score", 0)
                            gc = ft_score.get("score", 0)
                        
                        metrics["goals_scored"] += gs
                        metrics["goals_conceded"] += gc
                        
                        # Contagem de V/E/D
                        if gs > gc:
                            metrics["wins"] += 1
                        elif gs == gc:
                            metrics["draws"] += 1
                        else:
                            metrics["losses"] += 1
                            
                    # --- Análise Gols HT (Usando 'periods') ---
                    if ht_period and ht_period.get("scores"):
                         ht_scores = ht_period.get("scores")
                         if is_home_game:
                             # Gols marcados no HT (score do time)
                             metrics["gols_ht"] += next((s.get("score", 0) for s in ht_scores if s.get("participant_id") == team_id), 0)
                         else: 
                             # Gols marcados no HT (opponent_score do time)
                             metrics["gols_ht"] += next((s.get("score", 0) for s in ht_scores if s.get("participant_id") != team_id), 0)

                    
                    # --- Análise Escanteios ---
                    corners = f.get("corners", [])
                    team_corners = next((c for c in corners if c.get("participant_id") == team_id), None)
                    if team_corners:
                        metrics["escanteios"] += team_corners.get("count", 0)


                # 4. Cálculo final das métricas
                games_count = metrics["total_games"]
                
                final_metrics = {
                    "team_id": team_id,
                    # Gols FT
                    "avg_gs": metrics["goals_scored"] / games_count,
                    "avg_gc": metrics["goals_conceded"] / games_count,
                    # Forma (V/E/D) - 100 * (Vitorias + Empates * 0.5) / Total
                    "form_score": (metrics["wins"] * 100 + metrics["draws"] * 50) / games_count,
                    # Escanteios
                    "avg_corners_for": metrics["escanteios"] / games_count,
                    # Gols HT
                    "avg_ht_goals_for": metrics["gols_ht"] / games_count,
                    "games_count": games_count # Adiciona a contagem real de jogos
                }
                
                print(f"DEBUG: Métricas reais para o Time {team_id} (n={games_count}): GS={final_metrics['avg_gs']:.2f}, Corners={final_metrics['avg_corners_for']:.2f}, HT={final_metrics['avg_ht_goals_for']:.2f}, Form={final_metrics['form_score']:.0f}%")

                return final_metrics
                
    except Exception as e:
        print(f"❌ Erro INESPERADO ao buscar o histórico de times (compute_team_metrics) para o time {team_id}: {e}")
        # Retorna 0 em caso de falha da API
        return DEFAULT_METRICS_ZERO


# ----------------------------------------------------------------------
# FUNÇÕES DE ANÁLISE E DECISÃO
# ----------------------------------------------------------------------

def decide_best_market(home_metrics, away_metrics):
    """
    Decide a melhor sugestão de aposta e calcula a confiança, analisando múltiplos mercados.
    """
    
    best_suggestion = "Sem sinal forte — evite aposta"
    max_confidence = 50 # Confiança base
    
    # VERIFICAÇÃO CRÍTICA: Se algum time não tiver dados, a confiança não pode ser alta.
    # Se total_games for 0 para a casa OU para o fora, a confiança máxima é 50%.
    if home_metrics.get("games_count", 0) == 0 or away_metrics.get("games_count", 0) == 0:
        return "Sem dados históricos de um ou ambos os times", 0
        
    
    # --- 1. ANÁLISE GERAL DE GOLS (FULL TIME) ---
    
    # Média de gols total esperado no jogo
    total_avg_goals = home_metrics["avg_gs"] + away_metrics["avg_gs"]
                      
    
    # Avaliação do mercado de gols (Over 1.5, Over 2.5)
    confidence_goals = 50
    suggestion_goals = "Sem sinal"
    
    # Critérios ajustados para dar mais peso a Over 2.5
    if total_avg_goals >= 2.8:
        suggestion_goals = "Mais de 2.5 Gols (Over 2.5 FT)"
        confidence_goals += int(min(total_avg_goals * 12, 49)) # Máx 99%
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
    
    # Diferença de forma alta (ex: 80% vs 30% -> diff 50)
    if form_diff > 45: 
        winner = "Casa" if home_form > away_form else "Fora"
        # Adiciona verificação de GS para garantir que o time tem poder ofensivo
        if winner == "Casa" and home_metrics["avg_gs"] > 1.8:
            suggestion_winner = "Vitória do Time da Casa (ML Home)"
            confidence_winner = min(99, max(confidence_winner, 60 + int(form_diff / 2))) # Até 85%
        elif winner == "Fora" and away_metrics["avg_gs"] > 1.8:
            suggestion_winner = "Vitória do Time Visitante (ML Away)"
            confidence_winner = min(99, max(confidence_winner, 60 + int(form_diff / 2))) # Até 85%
            
    if confidence_winner > max_confidence:
        max_confidence = confidence_winner
        best_suggestion = suggestion_winner


    # --- 3. ANÁLISE ESCANTEIOS (CORNERS) ---
    
    total_avg_corners = home_metrics["avg_corners_for"] + away_metrics["avg_corners_for"]
    
    confidence_corners = 50
    suggestion_corners = "Sem sinal"
    
    # Se a soma das médias for alta (ex: 5.5 + 5.5 = 11)
    if total_avg_corners >= 10.8:
        suggestion_corners = "Mais de 10.5 Escanteios (Over 10.5 CR)"
        confidence_corners += int(min((total_avg_corners - 10.0) * 8, 49)) # Máx 99%
    elif total_avg_corners >= 9.0:
        suggestion_corners = "Mais de 9.5 Escanteios (Over 9.5 CR)"
        confidence_corners += int(min((total_avg_corners - 8.5) * 8, 35))

    if confidence_corners > max_confidence:
        max_confidence = confidence_corners
        best_suggestion = suggestion_corners
        
        
    # --- 4. ANÁLISE GOLS NO PRIMEIRO TEMPO (HT GOALS) ---
    
    total_avg_ht_goals = home_metrics["avg_ht_goals_for"] + away_metrics["avg_ht_goals_for"]
    
    confidence_ht = 50
    suggestion_ht = "Sem sinal"
    
    # Se a média total de Gols no HT for alta (ex: 0.8 + 0.8 = 1.6)
    if total_avg_ht_goals >= 1.5:
        suggestion_ht = "Mais de 1.5 Gols (Over 1.5 HT)"
        confidence_ht += int(min((total_avg_ht_goals - 1.0) * 25, 49)) # Máx 99%
    elif total_avg_ht_goals >= 0.8:
        suggestion_ht = "Mais de 0.5 Gols (Over 0.5 HT)"
        confidence_ht += int(min((total_avg_ht_goals - 0.5) * 20, 30))

    if confidence_ht > max_confidence:
        max_confidence = confidence_ht
        best_suggestion = suggestion_ht

    # Garante que a confiança fique entre 0% e 99%
    final_confidence = min(99, max(0, max_confidence)) 

    return best_suggestion, final_confidence

def kickoff_time_local(fixture, tz, return_datetime=False):
    """
    Converte a string de horário UTC da API para horário local (BRT) e formata.
    CORRIGIDO: Força o reconhecimento do 'starting_at' como UTC.
    """
    
    starting_at_str = fixture.get("starting_at") 
    
    if not starting_at_str:
        return datetime.now(tz) if return_datetime else "N/A"
        
    try:
        # A SportMonks v3 usa o formato ISO 8601, que é tratado por 'fromisoformat' (Python 3.7+).
        # Para garantir compatibilidade em ambientes mais antigos ou formatos variados da V3:

        # 1. Limpeza da string: Remove 'Z' e qualquer milissegundo após o ponto (se houver)
        if starting_at_str.endswith('Z'):
            starting_at_str = starting_at_str[:-1]
        if '.' in starting_at_str:
            starting_at_str = starting_at_str.split('.')[0]

        # 2. Tenta fazer o parse usando formatos comuns, garantindo que o fuso horário seja UTC
        # Tenta o formato ISO 8601 completo (com 'T')
        try:
            dt_utc = datetime.strptime(starting_at_str, "%Y-%m-%dT%H:%M:%S").replace(tzinfo=timezone.utc)
        except ValueError:
            # Se falhar, tenta o formato com espaço (sem 'T')
            dt_utc = datetime.strptime(starting_at_str, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
            
        # 3. Conversão para o fuso horário local (BRT)
        dt_local = dt_utc.astimezone(tz)
        
        if return_datetime:
            return dt_local
        
        now_local = datetime.now(tz).date()
        if dt_local.date() == now_local:
            return dt_local.strftime("%H:%M")
        else:
            return dt_local.strftime("%H:%M — %d/%m")
            
    except Exception as e:
        # Imprime o horário da API para depuração
        print(f"❌ Erro ao processar data '{starting_at_str}' para timezone: {e}") 
        # Retorna a data atual como um datetime local para garantir que o filtro não quebre
        # Se for para retornar string, retorna erro
        return datetime.now(tz) if return_datetime else "Erro de data"

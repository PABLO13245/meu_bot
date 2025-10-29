# Importações necessárias para operações assíncronas e análise
import asyncio
import aiohttp
import numpy as np
import pytz 
from datetime import datetime, timedelta, timezone
# GARANTINDO A IMPORTAÇÃO DE TODOS OS TIPOS USADOS
from typing import Dict, Any, List, Tuple, Optional 

# Configurações da API football-data.org
BASE_URL = "https://api.football-data.org/v4"
STATE_FINISHED_ID = "FINISHED"

# ----------------------------------------------------------------------
# 🌍 NOVO: MAPEAMENTO GLOBAL DE LIGAS (Ligas e Copas incluídas)
# ----------------------------------------------------------------------
# Chave: Código curto | Valor: ID numérico na API (football-data.org) e código de país/área
# IMPORTANTE: A API v4 usa o endpoint /competitions/{id}/matches
LEAGUE_MAP: Dict[str, Dict[str, Any]] = {
    # Chave | ID numérico | Código de Área/País
    "WC": {"id": 2000, "name": "FIFA World Cup", "area": "WORLD", "country_code": "WW"},
    "CL": {"id": 2001, "name": "UEFA Champions League", "area": "EUR", "country_code": "EU"},
    "BL1": {"id": 2002, "name": "Bundesliga", "area": "GER", "country_code": "DE"},
    "DED": {"id": 2003, "name": "Eredivisie", "area": "NLD", "country_code": "NL"},
    "PD": {"id": 2014, "name": "Primera Division (La Liga)", "area": "ESP", "country_code": "ES"},
    "FL1": {"id": 2015, "name": "Ligue 1", "area": "FRA", "country_code": "FR"},
    "ELC": {"id": 2016, "name": "Championship", "area": "ENG", "country_code": "GB"}, # Inglaterra 2ª Divisão
    "PPL": {"id": 2017, "name": "Primeira Liga (Portugal)", "area": "POR", "country_code": "PT"},
    "EC": {"id": 2018, "name": "European Championship", "area": "EUR", "country_code": "EU"},
    "SA": {"id": 2019, "name": "Serie A (Itália)", "area": "ITA", "country_code": "IT"},
    "PL": {"id": 2021, "name": "Premier League (Inglaterra)", "area": "ENG", "country_code": "GB"},
    # Ligas que precisam ser adicionadas manualmente se não estiverem no plano (BSA é a principal)
    "BSA": {"id": 2013, "name": "Campeonato Brasileiro Série A", "area": "BRA", "country_code": "BR"},
    # Nota: IDs são exemplos, você deve CONFIRMAR os IDs exatos no seu plano da API.
}

# Lista de IDs que serão buscados no fetch_upcoming_fixtures
COMPETITION_IDS = [data["id"] for data in LEAGUE_MAP.values()]

# Mapeamento de códigos de área (Atualizado para incluir 'WW' e 'EU')
AREA_CODE_MAP = {
    "ENG": "GB", "ESP": "ES", "ITA": "IT", "DEU": "DE", "GER": "DE", 
    "POR": "PT", "BRA": "BR", "FRA": "FR", "NLD": "NL", "BEL": "BE", 
    "GBR": "GB", "WORLD": "WW", "EUR": "EU",
}

# ======================================================================
# FUNÇÕES DE UTILIDADE E CONFIGURAÇÃO
# ======================================================================

def get_flag_emoji(country_code: str) -> str:
    """Converte o código de país em emoji de bandeira."""
    if not country_code:
        return "🌎"
        
    code = country_code.upper()
    # O código pode vir da API como 3 letras (e.g., GER) ou como código de competição (e.g., EU)
    # A prioridade é mapear para o código de 2 letras da bandeira (e.g., DE)
    if len(code) == 3 or code in ["WORLD", "EUR"]:
        code = AREA_CODE_MAP.get(code, "WW")
        
    if len(code) != 2:
        return "🌎"
        
    # Converte código de 2 letras (ISO 3166-1 alpha-2) para emoji de bandeira
    return "".join(chr(0x1F1E6 + ord(char) - ord('A')) for char in code)


async def fetch_with_retry(session: aiohttp.ClientSession, url: str, api_token: str) -> Optional[Dict[str, Any]]:
    """
    Realiza uma chamada HTTP GET assíncrona com lógica de Exponential Backoff para reenvio.
    """
    max_retries = 3
    initial_delay = 1

    headers = {
        'X-Auth-Token': api_token,
        'Content-Type': 'application/json'
    }

    for attempt in range(max_retries):
        delay = initial_delay * (2 ** attempt)

        try:
            async with session.get(url, headers=headers) as response:
                if response.status == 200:
                    return await response.json()
                elif response.status == 429 and attempt < max_retries - 1:
                    print(f"⚠ Rate Limit atingido (429). Tentando novamente em {delay}s...")
                    await asyncio.sleep(delay)
                elif response.status >= 400 and response.status < 500:
                    error_text = await response.text()
                    print(f"❌ Erro irrecuperável HTTP {response.status}: {error_text}")
                    return None
                elif response.status >= 500 and attempt < max_retries - 1:
                    print(f"❌ Erro do Servidor HTTP {response.status}. Tentando novamente em {delay}s...")
                    await asyncio.sleep(delay)
                else:
                    print(f"❌ Erro HTTP {response.status} na requisição: {url}")
                    return None

        except aiohttp.ClientConnectorError as e:
            print(f"❌ Erro de Conexão: {e}")
            if attempt < max_retries - 1:
                print(f"   -> Reenvio em {delay}s...")
                await asyncio.sleep(delay)
            else:
                return None
        except Exception as e:
            print(f"❌ Erro inesperado no fetch: {e}")
            return None
            
    return None

# ======================================================================
# FUNÇÕES DE BUSCA DE FIXTURES E MÉTRICAS
# ======================================================================

# ATUALIZADO: Agora recebe league_ids para buscar Múltiplas Ligas
async def fetch_upcoming_fixtures(api_token: str, league_ids: Optional[List[int]] = None, per_page: int = 200) -> List[Dict[str, Any]]:
    """
    Busca jogos futuros na API do football-data.org usando IDs de competição.
    """
    now_utc = datetime.now(timezone.utc)
    date_from = now_utc.strftime("%Y-%m-%d")
    date_to = (now_utc + timedelta(days=1)).strftime("%Y-%m-%d")

    # Se league_ids não for passado, usa a lista padrão de IDs que definimos
    if league_ids is None:
        league_ids = COMPETITION_IDS

    all_fixtures: List[Dict[str, Any]] = []

    async with aiohttp.ClientSession() as session:
        
        # Faz uma chamada para CADA ID de competição
        for comp_id in league_ids:
            url = (
                f"{BASE_URL}/competitions/{comp_id}/matches"
                f"?dateFrom={date_from}&dateTo={date_to}"
                f"&status=SCHEDULED,IN_PLAY,PAUSED" 
            )
            
            data = await fetch_with_retry(session, url, api_token)
            
            if data and data.get("matches"):
                # Filtra o mapeamento para obter o código de país da liga
                comp_info = next((info for info in LEAGUE_MAP.values() if info["id"] == comp_id), None)
                country_code = comp_info.get("country_code", "WW") if comp_info else "WW"
                comp_name = comp_info.get("name", "Desconhecida") if comp_info else "Desconhecida"
                
                print(f"DEBUG: Buscando jogos da liga ID {comp_id} ({comp_name})...")

                for m in data["matches"]:
                    if m.get('status') in ['FINISHED', 'POSTPONED', 'CANCELED']:
                        continue
                        
                    # Usa o código de país do mapeamento para consistência com get_flag_emoji
                    # Nota: Mapeei o country_code (2 letras) para a bandeira
                    
                    mapped_fixture = {
                        "id": m.get("id"),
                        "starting_at": m.get("utcDate"), 
                        "league": {
                            "name": comp_name, # Usa o nome do mapeamento global para consistência
                            "country": {"code": country_code} 
                        },
                        "participants": [
                            {"id": m["homeTeam"]["id"], "name": m["homeTeam"]["name"], "meta": {"location": "home"}, "country": {"code": country_code}},
                            {"id": m["awayTeam"]["id"], "name": m["awayTeam"]["name"], "meta": {"location": "away"}, "country": {"code": country_code}}
                        ]
                    }
                    all_fixtures.append(mapped_fixture)
            
            # ATENÇÃO: Adicione um delay se o seu plano GRATUITO for muito restrito
            # await asyncio.sleep(0.5)

    print(f"✅ Jogos futuros encontrados (Total de jogos únicos): {len(all_fixtures)}")
    return all_fixtures


async def compute_team_metrics(api_token: str, team_id: int, last: int = 5) -> Dict[str, Any]:
    """
    Busca os últimos 'last' jogos do time na API para calcular métricas reais.
    (Nenhuma mudança nessa função, pois ela depende apenas do ID do time.)
    """
    
    DEFAULT_METRICS_ZERO = {
        "avg_gs": 0.0, "avg_gc": 0.0, "form_score": 0.0,
        "avg_corners_for": 0.0, "avg_ht_goals_for": 0.0, 
        "btts_count": 0, "total_games": 0 
    }
    
    url = f"{BASE_URL}/teams/{team_id}/matches?status={STATE_FINISHED_ID}&limit={last}"
    
    metrics = {
        "goals_scored": 0, "goals_conceded": 0, "wins": 0, "draws": 0, 
        "losses": 0, "corners": 0, "ht_goals_for": 0, "total_games": 0,
        "btts_sim": 0 
    }
    
    async with aiohttp.ClientSession() as session:
        data = await fetch_with_retry(session, url, api_token)
        
        if not data or not data.get("matches"):
            return DEFAULT_METRICS_ZERO

        historical_fixtures = data.get("matches", [])
        metrics["total_games"] = len(historical_fixtures)

        for m in historical_fixtures:
            score = m.get("score", {})
            ft_score = score.get("fullTime", {})
            ht_score = score.get("halfTime", {}) 
            
            home_id = m.get("homeTeam", {}).get("id")
            is_home_game = (home_id == team_id)

            gs, gc, gols_ht = 0, 0, 0
            
            # --- Análise FT ---
            if ft_score and ft_score.get("home") is not None and ft_score.get("away") is not None:
                home_g, away_g = ft_score["home"], ft_score["away"]
                
                if is_home_game: gs, gc = home_g, away_g
                else: gs, gc = away_g, home_g
                
                metrics["goals_scored"] += gs
                metrics["goals_conceded"] += gc
                
                if gs > gc: metrics["wins"] += 1
                elif gs == gc: metrics["draws"] += 1
                else: metrics["losses"] += 1
                
                if home_g > 0 and away_g > 0: metrics["btts_sim"] += 1
                
            # --- Análise Gols HT ---
            if ht_score and ht_score.get("home") is not None and ht_score.get("away") is not None:
                home_ht_g, away_ht_g = ht_score["home"], ht_score["away"]
                if is_home_game: gols_ht = home_ht_g
                else: gols_ht = away_ht_g

                metrics["ht_goals_for"] += gols_ht
                
            metrics["corners"] += 5 # Simulado


        games_count = metrics["total_games"]
        
        final_metrics = {
            "team_id": team_id,
            "avg_gs": metrics["goals_scored"] / games_count if games_count > 0 else 0.0,
            "avg_gc": metrics["goals_conceded"] / games_count if games_count > 0 else 0.0,
            "form_score": (metrics["wins"] * 100 + metrics["draws"] * 50) / games_count if games_count > 0 else 0.0,
            "avg_corners_for": metrics["corners"] / games_count if games_count > 0 else 0.0,
            "avg_ht_goals_for": metrics["ht_goals_for"] / games_count if games_count > 0 else 0.0,
            "btts_count": metrics["btts_sim"],
            "total_games": games_count
        }
        
        return final_metrics


# ======================================================================
# FUNÇÕES DE ANÁLISE E DECISÃO (COM DC e AH 0.0)
# ======================================================================

def decide_best_market(home_metrics: Dict[str, Any], away_metrics: Dict[str, Any]) -> Tuple[str, int]:
    """
    Decide a melhor sugestão de aposta, analisando múltiplos mercados e retornando o de maior confiança.
    (Nenhuma mudança nesta função)
    """
    
    suggestions: List[Tuple[str, int]] = []
    
    # Mínimo de 3 jogos para análise
    if home_metrics.get("total_games", 0) < 3 or away_metrics.get("total_games", 0) < 3:
        return "Sem dados históricos suficientes (mín. 3 jogos)", 0
        
    
    home_form = home_metrics["form_score"]
    away_form = away_metrics["form_score"]
    form_diff = abs(home_form - away_form)
    total_avg_goals = home_metrics["avg_gs"] + away_metrics["avg_gc"]
    total_avg_ht_goals = home_metrics["avg_ht_goals_for"] + away_metrics["avg_ht_goals_for"]
    
    
    # --- 1. Gols FT (Over/Under) ---
                      
    confidence_goals = 50
    if total_avg_goals >= 2.8:
        suggestion_goals = "Mais de 2.5 Gols (Over 2.5 FT)"
        confidence_goals += int(min((total_avg_goals - 2.8) * 15 + 15, 49)) 
        suggestions.append((suggestion_goals, confidence_goals))
    elif total_avg_goals >= 2.0:
        suggestion_goals = "Mais de 1.5 Gols (Over 1.5 FT)"
        confidence_goals += int(min((total_avg_goals - 2.0) * 10 + 10, 35))
        suggestions.append((suggestion_goals, confidence_goals))
    elif total_avg_goals <= 1.8:
        suggestion_goals = "Menos de 2.5 Gols (Under 2.5 FT)"
        confidence_goals += int(min((2.5 - total_avg_goals) * 15 + 10, 30))
        suggestions.append((suggestion_goals, confidence_goals))


    # --- 2. Vencedor (ML) ---
    
    confidence_winner = 50
    if form_diff > 50: 
        winner = "Casa" if home_form > away_form else "Fora"
        if winner == "Casa" and home_metrics["avg_gs"] > 2.0: 
            suggestion_winner = "Vitória do Time da Casa (ML Home)"
            confidence_winner = min(99, max(confidence_winner, 65 + int(form_diff / 2)))
            suggestions.append((suggestion_winner, confidence_winner))
        elif winner == "Fora" and away_metrics["avg_gs"] > 2.0:
            suggestion_winner = "Vitória do Time Visitante (ML Away)"
            confidence_winner = min(99, max(confidence_winner, 65 + int(form_diff / 2)))
            suggestions.append((suggestion_winner, confidence_winner))
            
    
    # --- 3. Dupla Chance (DC) e Handicap Asiático (AH 0.0) ---
    
    confidence_dc = 55

    if form_diff > 35:
        winner_favored = "Casa" if home_form > away_form else "Fora"
        
        # Dupla Chance (1X ou X2)
        if winner_favored == "Casa" and home_metrics["avg_gs"] > 1.5:
            suggestion_dc = "Dupla Chance: Casa ou Empate (1X)"
            confidence = min(95, confidence_dc + int(form_diff / 3) + 10)
            suggestions.append((suggestion_dc, confidence))
            
            if home_metrics["avg_gs"] > 1.8: # Mais agressivo
                suggestion_ah = "Handicap Asiático: Casa (0.0)"
                confidence_ah = min(99, confidence + 5) 
                suggestions.append((suggestion_ah, confidence_ah))
                    
        elif winner_favored == "Fora" and away_metrics["avg_gs"] > 1.5:
            suggestion_dc = "Dupla Chance: Fora ou Empate (X2)"
            confidence = min(95, confidence_dc + int(form_diff / 3) + 10)
            suggestions.append((suggestion_dc, confidence))

            if away_metrics["avg_gs"] > 1.8: # Mais agressivo
                suggestion_ah = "Handicap Asiático: Fora (0.0)"
                confidence_ah = min(99, confidence + 5)
                suggestions.append((suggestion_ah, confidence_ah))


    # --- 4. Ambos Marcam (BTTS) ---
    
    total_games = home_metrics["total_games"]
    home_btts_rate = home_metrics["btts_count"] / total_games
    away_btts_rate = away_metrics["btts_count"] / total_games
    avg_btts_rate = (home_btts_rate + away_btts_rate) / 2 
    
    confidence_btts = 50
    
    if avg_btts_rate >= 0.70 and total_avg_goals >= 2.5:
        suggestion_btts = "Ambas Marcam: SIM (BTTS Yes)"
        confidence_btts += int(min((avg_btts_rate - 0.70) * 100 + 15, 49)) 
        suggestions.append((suggestion_btts, confidence_btts))
    elif avg_btts_rate <= 0.30 and total_avg_goals < 1.8:
        suggestion_btts = "Ambas Marcam: NÃO (BTTS No)"
        confidence_btts += int(min((0.30 - avg_btts_rate) * 100 + 10, 35))
        suggestions.append((suggestion_btts, confidence_btts))


    # --- 5. Escanteios (Simulado) ---
    
    total_avg_corners = home_metrics["avg_corners_for"] + away_metrics["avg_corners_for"]
    confidence_corners = 50
    
    if total_avg_corners >= 10.8:
        suggestion_corners = "Mais de 10.5 Escanteios (Over 10.5 CR)"
        confidence_corners += int(min((total_avg_corners - 10.0) * 8, 49)) 
        suggestions.append((suggestion_corners, confidence_corners))
    elif total_avg_corners >= 9.0:
        suggestion_corners = "Mais de 9.5 Escanteios (Over 9.5 CR)"
        confidence_corners += int(min((total_avg_corners - 8.5) * 8, 35))
        suggestions.append((suggestion_corners, confidence_corners))
        
        
    # --- 6. Gols no Primeiro Tempo (HT Goals) ---
    
    confidence_ht = 50
    
    if total_avg_ht_goals >= 1.5:
        suggestion_ht = "Mais de 1.5 Gols (Over 1.5 HT)"
        confidence_ht += int(min((total_avg_ht_goals - 1.0) * 25, 49)) 
        suggestions.append((suggestion_ht, confidence_ht))
    elif total_avg_ht_goals >= 0.8:
        suggestion_ht = "Mais de 0.5 Gols (Over 0.5 HT)"
        confidence_ht += int(min((total_avg_ht_goals - 0.5) * 20, 30))
        suggestions.append((suggestion_ht, confidence_ht))

    # --- 7. Seleção da Melhor Aposta ---
    
    if suggestions:
        suggestions.sort(key=lambda x: x[1], reverse=True)
        best_suggestion, max_confidence = suggestions[0]
    else:
        best_suggestion = "Sem sinal forte — evite aposta"
        max_confidence = 50
        
    final_confidence = min(99, max(0, max_confidence)) 

    return best_suggestion, final_confidence


def kickoff_time_local(fixture: Dict[str, Any], tz: pytz.BaseTzInfo, return_datetime: bool = False) -> Any:
    """
    Converte a string de horário UTC da API para horário local (BRT) e formata.
    (Nenhuma mudança nesta função)
    """
    
    starting_at_str = fixture.get("starting_at") 
    
    if not starting_at_str:
        return datetime.now(tz) if return_datetime else "N/A"
        
    try:
        dt_utc = datetime.fromisoformat(starting_at_str.replace('Z', '+00:00'))
        dt_local = dt_utc.astimezone(tz)
        
        if return_datetime:
            return dt_local
        
        now_local = datetime.now(tz).date()
        if dt_local.date() == now_local:
            return dt_local.strftime("%H:%M")
        else:
            return dt_local.strftime("%H:%M — %d/%m")
            
    except Exception as e:
        print(f"❌ Erro ao processar data '{starting_at_str}' para timezone: {e}") 
        return datetime.now(tz) if return_datetime else "Erro de data"

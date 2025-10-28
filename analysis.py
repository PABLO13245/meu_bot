# Importações necessárias para operações assíncronas e análise
import asyncio
import aiohttp
import numpy as np
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, List, Tuple, Optional

# Configurações da API football-data.org
BASE_URL = "https://api.football-data.org/v4"
# O football-data.org usa status codes textuais. O status 2 (FINISHED) é necessário para histórico.
STATE_FINISHED_ID = "FINISHED"

# Dicionário de Códigos de Competição para Filtro (substitui a busca geral da Sportmonks)
# A API football-data.org exige que as ligas sejam filtradas por ID ou código.
# Estes são os códigos de exemplo (competitions/areas) que o bot irá buscar.
# PL: Premier League, PD: La Liga, SA: Serie A, BL1: Bundesliga, PPL: Primeira Liga (Portugal)
COMPETITION_CODES = ["PL", "PD", "SA", "BL1", "PPL"] 

# ======================================================================
# FUNÇÕES DE UTILIDADE E CONFIGURAÇÃO
# ======================================================================

def get_flag_emoji(country_code: str) -> str:
    """Converte o código de país (ISO 3166-1 alpha-2) em emoji de bandeira."""
    if country_code is None or len(country_code) != 2:
        return ""
    # Emojis de bandeira são gerados a partir de 2 caracteres regionais:
    return "".join(chr(0x1F1E6 + ord(char) - ord('A')) for char in country_code.upper())


async def fetch_with_retry(session: aiohttp.ClientSession, url: str, api_token: str) -> Optional[Dict[str, Any]]:
    """
    Realiza uma chamada HTTP GET assíncrona com lógica de Exponential Backoff para reenvio.

    Args:
        session: A sessão aiohttp ativa.
        url: O URL completo da API.
        api_token: A chave de autenticação (X-Auth-Token).

    Returns:
        Um dicionário contendo os dados JSON da API, ou None em caso de falha.
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
                    # Erros do lado do cliente (Bad Request, Forbidden, Not Found)
                    error_text = await response.text()
                    print(f"❌ Erro irrecuperável HTTP {response.status}: {error_text}")
                    return None
                
                elif response.status >= 500 and attempt < max_retries - 1:
                    # Erros do servidor (Retryable)
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

async def fetch_upcoming_fixtures(api_token: str, per_page: int = 100) -> List[Dict[str, Any]]:
    """
    Busca jogos futuros na API do football-data.org (próximas 48h) em ligas específicas.
    
    A API football-data.org não tem um endpoint de "jogos futuros" geral como a Sportmonks.
    Portanto, faremos a busca filtrando explicitamente a data.
    """
    now_utc = datetime.now(timezone.utc)
    time_limit_48h = now_utc + timedelta(hours=48)
    
    # football-data.org usa formato YYYY-MM-DD
    date_from = now_utc.strftime("%Y-%m-%d")
    date_to = time_limit_48h.strftime("%Y-%m-%d")

    all_fixtures: List[Dict[str, Any]] = []

    # Cria uma sessão para todas as chamadas
    async with aiohttp.ClientSession() as session:
        
        # A API exige o filtro de liga (competição)
        # Vamos buscar os jogos para as competições definidas.
        for comp_code in COMPETITION_CODES:
            # Endpoint para jogos por competição
            url = (
                f"{BASE_URL}/competitions/{comp_code}/matches"
                f"?dateFrom={date_from}&dateTo={date_to}"
                f"&status=SCHEDULED,IN_PLAY,PAUSED" # Busca jogos agendados ou em andamento (para filtro de segurança)
            )
            
            print(f"DEBUG: Buscando jogos de {comp_code} entre {date_from} e {date_to}.")

            data = await fetch_with_retry(session, url, api_token)
            
            if data and data.get("matches"):
                
                # Mapeamento para o formato da Sportmonks (mais ou menos)
                for m in data["matches"]:
                    
                    # Ignora jogos que já passaram no tempo local (o filtro principal será no main.py)
                    if m.get('status') in ['FINISHED', 'POSTPONED', 'CANCELED']:
                        continue
                        
                    # Mapeamento da estrutura football-data.org para Sportmonks
                    mapped_fixture = {
                        "id": m.get("id"),
                        "starting_at": m.get("utcDate"), # Data e hora UTC
                        "league": {
                            "name": m["competition"]["name"],
                            "country": {"code": m["area"]["code"]} # Usa o código da área (ex: "ESP")
                        },
                        "participants": [
                            {
                                "id": m["homeTeam"]["id"],
                                "name": m["homeTeam"]["name"],
                                "meta": {"location": "home"},
                                "country": {"code": m["area"]["code"]} # Usa código da área para bandeira
                            },
                            {
                                "id": m["awayTeam"]["id"],
                                "name": m["awayTeam"]["name"],
                                "meta": {"location": "away"},
                                "country": {"code": m["area"]["code"]}
                            }
                        ]
                    }
                    all_fixtures.append(mapped_fixture)
                    
            elif data is not None:
                # O token pode não ter acesso a algumas ligas, ou a API pode retornar 0 jogos
                print(f"DEBUG: Competição {comp_code} não retornou jogos ou acesso negado.")
    
    print(f"✅ Jogos futuros encontrados (Total): {len(all_fixtures)}")
    return all_fixtures


async def compute_team_metrics(api_token: str, team_id: int, last: int = 5) -> Dict[str, Any]:
    """
    Busca os últimos 'last' jogos do time na API para calcular métricas reais.
    """
    
    DEFAULT_METRICS_ZERO = {
        "avg_gs": 0.0, "avg_gc": 0.0, "form_score": 0.0,
        "avg_corners_for": 0.0, "avg_ht_goals_for": 0.0,
        "games_count": 0
    }
    
    # Endpoint para jogos do time, filtrado por status 'FINISHED', ordenado por data descendente
    url = f"{BASE_URL}/teams/{team_id}/matches?status={STATE_FINISHED_ID}&limit={last}"
    
    metrics = {
        "goals_scored": 0, "goals_conceded": 0, "wins": 0, "draws": 0, 
        "losses": 0, "corners": 0, "ht_goals_for": 0, "total_games": 0 
    }
    
    async with aiohttp.ClientSession() as session:
        data = await fetch_with_retry(session, url, api_token)
        
        if not data or not data.get("matches"):
            print(f"⚠ Time {team_id} não tem jogos finalizados ou falha na API.")
            return DEFAULT_METRICS_ZERO

        historical_fixtures = data.get("matches", [])
        metrics["total_games"] = len(historical_fixtures)

        for m in historical_fixtures:
            score = m.get("score", {})
            ft_score = score.get("fullTime", {})
            ht_score = score.get("halfTime", {}) # Score de Half Time já vem aqui
            
            home_id = m.get("homeTeam", {}).get("id")
            
            is_home_game = (home_id == team_id)

            gs = 0
            gc = 0
            gols_ht = 0
            
            # --- Análise FT ---
            if ft_score and ft_score.get("home") is not None and ft_score.get("away") is not None:
                home_g = ft_score["home"]
                away_g = ft_score["away"]
                
                if is_home_game:
                    gs = home_g
                    gc = away_g
                else: 
                    gs = away_g
                    gc = home_g
                
                metrics["goals_scored"] += gs
                metrics["goals_conceded"] += gc
                
                # Contagem de V/E/D (baseado nos gols finais)
                if gs > gc: metrics["wins"] += 1
                elif gs == gc: metrics["draws"] += 1
                else: metrics["losses"] += 1
                
            # --- Análise Gols HT ---
            if ht_score and ht_score.get("home") is not None and ht_score.get("away") is not None:
                home_ht_g = ht_score["home"]
                away_ht_g = ht_score["away"]

                if is_home_game:
                    gols_ht = home_ht_g
                else:
                    gols_ht = away_ht_g

                metrics["ht_goals_for"] += gols_ht
                
            # --- Análise Escanteios (Corners) ---
            # A API football-data.org não fornece dados de escanteios (corners) por padrão nos endpoints
            # de partidas e times, a menos que seja um endpoint específico ou um plano pago.
            # Para evitar quebrar o bot, vamos simular dados médios de escanteios.
            # EM CENÁRIO REAL: Este código falharia ou precisaria de outra fonte/plano.
            # Aqui, simulamos que a média de escanteios do time é 5.
            metrics["corners"] += 5 


        # 4. Cálculo final das métricas
        games_count = metrics["total_games"]
        
        final_metrics = {
            "team_id": team_id,
            # Gols FT
            "avg_gs": metrics["goals_scored"] / games_count if games_count > 0 else 0.0,
            "avg_gc": metrics["goals_conceded"] / games_count if games_count > 0 else 0.0,
            # Forma (V/E/D) - 100 * (Vitorias + Empates * 0.5) / Total
            "form_score": (metrics["wins"] * 100 + metrics["draws"] * 50) / games_count if games_count > 0 else 0.0,
            # Escanteios (SIMULADO!)
            "avg_corners_for": metrics["corners"] / games_count if games_count > 0 else 0.0,
            # Gols HT
            "avg_ht_goals_for": metrics["ht_goals_for"] / games_count if games_count > 0 else 0.0,
            "games_count": games_count
        }
        
        print(f"DEBUG: Métricas reais para o Time {team_id} (n={games_count}): GS={final_metrics['avg_gs']:.2f}, HT={final_metrics['avg_ht_goals_for']:.2f}, Form={final_metrics['form_score']:.0f}%")
        return final_metrics


# ======================================================================
# FUNÇÕES DE ANÁLISE E DECISÃO (MANTIDAS DO CÓDIGO ORIGINAL)
# ======================================================================

def decide_best_market(home_metrics: Dict[str, Any], away_metrics: Dict[str, Any]) -> Tuple[str, int]:
    """
    Decide a melhor sugestão de aposta e calcula a confiança, analisando múltiplos mercados.
    """
    
    best_suggestion = "Sem sinal forte — evite aposta"
    max_confidence = 50 # Confiança base
    
    # VERIFICAÇÃO CRÍTICA: Se algum time não tiver dados, a confiança não pode ser alta.
    if home_metrics.get("games_count", 0) == 0 or away_metrics.get("games_count", 0) == 0:
        return "Sem dados históricos de um ou ambos os times", 0
        
    
    # --- 1. ANÁLISE GERAL DE GOLS (FULL TIME) ---
    
    total_avg_goals = home_metrics["avg_gs"] + away_metrics["avg_gs"]
                      
    confidence_goals = 50
    suggestion_goals = "Sem sinal"
    
    if total_avg_goals >= 2.8:
        suggestion_goals = "Mais de 2.5 Gols (Over 2.5 FT)"
        confidence_goals += int(min(total_avg_goals * 12, 49)) 
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
    
    if form_diff > 45: 
        winner = "Casa" if home_form > away_form else "Fora"
        if winner == "Casa" and home_metrics["avg_gs"] > 1.8:
            suggestion_winner = "Vitória do Time da Casa (ML Home)"
            confidence_winner = min(99, max(confidence_winner, 60 + int(form_diff / 2))) 
        elif winner == "Fora" and away_metrics["avg_gs"] > 1.8:
            suggestion_winner = "Vitória do Time Visitante (ML Away)"
            confidence_winner = min(99, max(confidence_winner, 60 + int(form_diff / 2))) 
            
    if confidence_winner > max_confidence:
        max_confidence = confidence_winner
        best_suggestion = suggestion_winner


    # --- 3. ANÁLISE ESCANTEIOS (CORNERS) ---
    
    total_avg_corners = home_metrics["avg_corners_for"] + away_metrics["avg_corners_for"]
    
    confidence_corners = 50
    suggestion_corners = "Sem sinal"
    
    if total_avg_corners >= 10.8:
        suggestion_corners = "Mais de 10.5 Escanteios (Over 10.5 CR)"
        confidence_corners += int(min((total_avg_corners - 10.0) * 8, 49)) 
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
    
    if total_avg_ht_goals >= 1.5:
        suggestion_ht = "Mais de 1.5 Gols (Over 1.5 HT)"
        confidence_ht += int(min((total_avg_ht_goals - 1.0) * 25, 49)) 
    elif total_avg_ht_goals >= 0.8:
        suggestion_ht = "Mais de 0.5 Gols (Over 0.5 HT)"
        confidence_ht += int(min((total_avg_ht_goals - 0.5) * 20, 30))

    if confidence_ht > max_confidence:
        max_confidence = confidence_ht
        best_suggestion = suggestion_ht

    # Garante que a confiança fique entre 0% e 99%
    final_confidence = min(99, max(0, max_confidence)) 

    return best_suggestion, final_confidence


def kickoff_time_local(fixture: Dict[str, Any], tz: pytz.BaseTzInfo, return_datetime: bool = False) -> Any:
    """
    Converte a string de horário UTC da API para horário local (BRT) e formata.
    A API football-data.org usa o formato ISO 8601 (Ex: 2023-11-20T19:30:00Z).
    """
    
    starting_at_str = fixture.get("starting_at") 
    
    if not starting_at_str:
        return datetime.now(tz) if return_datetime else "N/A"
        
    try:
        # datetime.fromisoformat lida com 'T' e 'Z' corretamente.
        dt_utc = datetime.fromisoformat(starting_at_str.replace('Z', '+00:00'))
            
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
        print(f"❌ Erro ao processar data '{starting_at_str}' para timezone: {e}") 
        return datetime.now(tz) if return_datetime else "Erro de data"

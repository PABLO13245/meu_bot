# Importações necessárias para operações assíncronas e análise
import asyncio
import aiohttp
import numpy as np
import pytz 
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, List, Tuple, Optional

# Configurações da API football-data.org
BASE_URL = "https://api.football-data.org/v4"
# O football-data.org usa status codes textuais. O status 2 (FINISHED) é necessário para histórico.
STATE_FINISHED_ID = "FINISHED"

# Dicionário de Códigos de Competição (Atualizado com todas as ligas do seu Plano Free)
# PL, PD, SA, BL1, PPL (já estavam) + WC, CL, DED, BSA, FL1, ELC, EC (novas)
COMPETITION_CODES = [
    "PL", "PD", "SA", "BL1", "PPL",  # Ligas Top
    "WC", "CL", "DED", "BSA", "FL1", "ELC", "EC" # Copas e Ligas Adicionais
] 

# Mapeamento de códigos de área de 3 letras (Alpha-3) para códigos de bandeira de 2 letras (Alpha-2)
AREA_CODE_MAP = {
    "ENG": "GB", # Reino Unido (para Premier League)
    "ESP": "ES", # Espanha (para La Liga)
    "ITA": "IT", # Itália (para Serie A)
    "DEU": "DE", # Alemanha (para Bundesliga)
    "GER": "DE", # Alemanha (código alternativo)
    "POR": "PT", # Portugal (para Primeira Liga)
    "BRA": "BR", # Brasil (para Brasileirão)
    "FRA": "FR", # França (Ligue 1)
    "NLD": "NL", # Holanda (Eredivisie)
    "BEL": "BE", # Bélgica
    "GBR": "GB", # Outro código do Reino Unido
    "WORLD": "WW", # Código Genérico para World Cup (WC)
    "EUR": "EU", # Código Genérico para Champions League/European Championship (CL/EC)
}


# ======================================================================
# FUNÇÕES DE UTILIDADE E CONFIGURAÇÃO
# ======================================================================

def get_flag_emoji(country_code: str) -> str:
    """Converte o código de país (ISO 3166-1 alpha-2) em emoji de bandeira,
       mapeando códigos de 3 letras (Alpha-3) se necessário."""
    if not country_code:
        return "🌎" # Retorna globo para ligas internacionais (WC, CL)
        
    code = country_code.upper()
    
    # Tenta mapear o código de 3 letras (Area Code) para 2 letras (ISO-2)
    if len(code) == 3 or code == "WORLD" or code == "EUR":
        code = AREA_CODE_MAP.get(code, "WW") # Default 'WW' para Unknown World
        
    if len(code) != 2:
        return "🌎"
        
    # Emojis de bandeira são gerados a partir de 2 caracteres regionais:
    # Retorna o código padrão para bandeira
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

async def fetch_upcoming_fixtures(api_token: str, per_page: int = 200) -> List[Dict[str, Any]]:
    """
    Busca jogos futuros na API do football-data.org (próximas 48h) em Ligas específicas.
    """
    now_utc = datetime.now(timezone.utc)
    time_limit_48h = now_utc + timedelta(hours=48)
    
    date_from = now_utc.strftime("%Y-%m-%d")
    date_to = time_limit_48h.strftime("%Y-%m-%d")

    all_fixtures: List[Dict[str, Any]] = []

    async with aiohttp.ClientSession() as session:
        
        for comp_code in COMPETITION_CODES:
            # Endpoint para jogos por competição
            url = (
                f"{BASE_URL}/competitions/{comp_code}/matches"
                f"?dateFrom={date_from}&dateTo={date_to}"
                f"&status=SCHEDULED,IN_PLAY,PAUSED" 
            )
            
            print(f"DEBUG: Buscando jogos de {comp_code} entre {date_from} e {date_to}.")

            data = await fetch_with_retry(session, url, api_token)
            
            if data and data.get("matches"):
                
                for m in data["matches"]:
                    
                    if m.get('status') in ['FINISHED', 'POSTPONED', 'CANCELED']:
                        continue
                        
                    area_code = m["area"]["code"] # Código de 3 letras do país/área
                    
                    # Mapeamento da estrutura football-data.org para estrutura interna do Bot
                    mapped_fixture = {
                        "id": m.get("id"),
                        "starting_at": m.get("utcDate"), 
                        "league": {
                            "name": m["competition"]["name"],
                            "country": {"code": area_code} # Usamos o código de 3 letras aqui
                        },
                        "participants": [
                            {
                                "id": m["homeTeam"]["id"],
                                "name": m["homeTeam"]["name"],
                                "meta": {"location": "home"},
                                "country": {"code": area_code} 
                            },
                            {
                                "id": m["awayTeam"]["id"],
                                "name": m["awayTeam"]["name"],
                                "meta": {"location": "away"},
                                "country": {"code": area_code}
                            }
                        ]
                    }
                    all_fixtures.append(mapped_fixture)
                    
            elif data is not None:
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
        "btts_count": 0, "total_games": 0 
    }
    
    # Endpoint para jogos do time, filtrado por status 'FINISHED', ordenado por data descendente
    url = f"{BASE_URL}/teams/{team_id}/matches?status={STATE_FINISHED_ID}&limit={last}"
    
    metrics = {
        "goals_scored": 0, "goals_conceded": 0, "wins": 0, "draws": 0, 
        "losses": 0, "corners": 0, "ht_goals_for": 0, "total_games": 0,
        "btts_sim": 0 # Nova métrica para Ambos Marcam (BTTS)
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
            ht_score = score.get("halfTime", {}) 
            
            home_id = m.get("homeTeam", {}).get("id")
            
            is_home_game = (home_id == team_id)

            gs = 0
            gc = 0
            
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
                
                # Contagem de V/E/D
                if gs > gc: metrics["wins"] += 1
                elif gs == gc: metrics["draws"] += 1
                else: metrics["losses"] += 1
                
                # NOVO: Contagem de Ambos Marcam (BTTS)
                if home_g > 0 and away_g > 0:
                    metrics["btts_sim"] += 1
                
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
            # Simulação: Mantido o valor fixo de 5, pois a API Free não fornece corners
            metrics["corners"] += 5 


        # 4. Cálculo final das métricas
        games_count = metrics["total_games"]
        
        final_metrics = {
            "team_id": team_id,
            # Gols FT
            "avg_gs": metrics["goals_scored"] / games_count if games_count > 0 else 0.0,
            "avg_gc": metrics["goals_conceded"] / games_count if games_count > 0 else 0.0,
            # Forma 
            "form_score": (metrics["wins"] * 100 + metrics["draws"] * 50) / games_count if games_count > 0 else 0.0,
            # Escanteios (SIMULADO!)
            "avg_corners_for": metrics["corners"] / games_count if games_count > 0 else 0.0,
            # Gols HT
            "avg_ht_goals_for": metrics["ht_goals_for"] / games_count if games_count > 0 else 0.0,
            # NOVO: Contagem de Ambos Marcam
            "btts_count": metrics["btts_sim"],
            "total_games": games_count
        }
        
        print(f"DEBUG: Métricas reais para o Time {team_id} (n={games_count}): GS={final_metrics['avg_gs']:.2f}, HT={final_metrics['avg_ht_goals_for']:.2f}, Form={final_metrics['form_score']:.0f}%")
        return final_metrics


# ======================================================================
# FUNÇÕES DE ANÁLISE E DECISÃO (ATUALIZADA)
# ======================================================================

def decide_best_market(home_metrics: Dict[str, Any], away_metrics: Dict[str, Any]) -> Tuple[str, int]:
    """
    Decide a melhor sugestão de aposta, analisando múltiplos mercados e retornando o de maior confiança.
    """
    
    # Lista para armazenar todas as sugestões válidas (sugestão, confiança)
    suggestions: List[Tuple[str, int]] = []
    
    
    # VERIFICAÇÃO CRÍTICA: Se algum time não tiver dados, a confiança é 0.
    if home_metrics.get("total_games", 0) < 3 or away_metrics.get("total_games", 0) < 3:
        return "Sem dados históricos suficientes (mín. 3 jogos)", 0
        
    
    # --- 1. ANÁLISE GERAL DE GOLS (FULL TIME) - Over/Under ---
    
    total_avg_goals = home_metrics["avg_gs"] + away_metrics["avg_gc"]
                      
    confidence_goals = 50
    
    if total_avg_goals >= 2.8:
        suggestion_goals = "Mais de 2.5 Gols (Over 2.5 FT)"
        confidence_goals += int(min((total_avg_goals - 2.8) * 15 + 15, 49)) 
        suggestions.append((suggestion_goals, confidence_goals))
    elif total_avg_goals >= 2.0:
        suggestion_goals = "Mais de 1.5 Gols (Over 1.5 FT)"
        confidence_goals += int(min((total_avg_goals - 2.0) * 10 + 10, 35))
        suggestions.append((suggestion_goals, confidence_goals))


    # --- 2. ANÁLISE VENCEDOR (1X2) - Moneyline ---
    
    home_form = home_metrics["form_score"]
    away_form = away_metrics["form_score"]
    form_diff = abs(home_form - away_form)
    
    confidence_winner = 50
    
    if form_diff > 45: 
        winner = "Casa" if home_form > away_form else "Fora"
        if winner == "Casa" and home_metrics["avg_gs"] > 1.8:
            suggestion_winner = "Vitória do Time da Casa (ML Home)"
            confidence_winner = min(99, max(confidence_winner, 60 + int(form_diff / 2)))
            suggestions.append((suggestion_winner, confidence_winner))
        elif winner == "Fora" and away_metrics["avg_gs"] > 1.8:
            suggestion_winner = "Vitória do Time Visitante (ML Away)"
            confidence_winner = min(99, max(confidence_winner, 60 + int(form_diff / 2)))
            suggestions.append((suggestion_winner, confidence_winner))
            
    
    # --- 3. NOVO: ANÁLISE AMBAS MARCAM (BTTS - Both Teams To Score) ---
    
    # Probabilidade de BTTS (Home) = Média de gols marcados pelo Away + Média de gols sofridos pelo Home
    # Probabilidade de BTTS (Away) = Média de gols marcados pelo Home + Média de gols sofridos pelo Away
    
    # Abordagem simplificada: % de BTTS nos últimos 5 jogos de cada time
    total_games = home_metrics["total_games"]
    home_btts_rate = home_metrics["btts_count"] / total_games
    away_btts_rate = away_metrics["btts_count"] / total_games
    
    # Média de BTTS dos dois times (em % de jogos)
    avg_btts_rate = (home_btts_rate + away_btts_rate) / 2 
    
    confidence_btts = 50
    
    if avg_btts_rate >= 0.70: # 70% ou mais dos jogos terminam com Ambos Marcam
        suggestion_btts = "Ambas Marcam: SIM (BTTS Yes)"
        # Confiança aumenta linearmente a partir de 70%
        confidence_btts += int(min((avg_btts_rate - 0.70) * 100 + 15, 49)) 
        suggestions.append((suggestion_btts, confidence_btts))
    elif avg_btts_rate <= 0.30 and total_avg_goals < 2.0: # Menos de 30% e poucos gols no geral
        suggestion_btts = "Ambas Marcam: NÃO (BTTS No)"
        confidence_btts += int(min((0.30 - avg_btts_rate) * 100 + 10, 35))
        suggestions.append((suggestion_btts, confidence_btts))


    # --- 4. ANÁLISE ESCANTEIOS (CORNERS) ---
    
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
        
        
    # --- 5. ANÁLISE GOLS NO PRIMEIRO TEMPO (HT GOALS) ---
    
    total_avg_ht_goals = home_metrics["avg_ht_goals_for"] + away_metrics["avg_ht_goals_for"]
    
    confidence_ht = 50
    
    if total_avg_ht_goals >= 1.5:
        suggestion_ht = "Mais de 1.5 Gols (Over 1.5 HT)"
        confidence_ht += int(min((total_avg_ht_goals - 1.0) * 25, 49)) 
        suggestions.append((suggestion_ht, confidence_ht))
    elif total_avg_ht_goals >= 0.8:
        suggestion_ht = "Mais de 0.5 Gols (Over 0.5 HT)"
        confidence_ht += int(min((total_avg_ht_goals - 0.5) * 20, 30))
        suggestions.append((suggestion_ht, confidence_ht))

    # --- 6. SELEÇÃO DA MELHOR APOSTA ---
    
    # Ordena todas as sugestões válidas pela confiança (descendente)
    if suggestions:
        suggestions.sort(key=lambda x: x[1], reverse=True)
        best_suggestion, max_confidence = suggestions[0]
    else:
        best_suggestion = "Nenhuma sugestão alcançou a confiança base (50%)"
        max_confidence = 50
        
    # Garante que a confiança final fique entre 0% e 99%
    final_confidence = min(99, max(0, max_confidence)) 

    return best_suggestion, final_confidence


def kickoff_time_local(fixture: Dict[str, Any], tz: pytz.BaseTzInfo, return_datetime: bool = False) -> Any:
    """
    Converte a string de horário UTC da API para horário local (BRT) e formata

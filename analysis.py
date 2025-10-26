import aiohttp
from datetime import datetime, timezone
import pytz
import random

# ========== CONFIGURAÇÕES ==========
BASE_URL = "https://api.sportmonks.com/v3/football"
TZ = pytz.timezone("America/Sao_Paulo")

# IMPORTANTE: LEAGUE_IDS agora é None. Ele será definido e passado
# pelo main.py para cada análise individual.
LEAGUE_IDS = None 

# ===================================
# BUSCAR PARTIDAS FUTURAS
# ===================================
# A função agora aceita 'league_ids' como um argumento (que virá do main.py)
async def fetch_upcoming_fixtures(api_token, start_str, end_str, league_ids=None):
    # CORREÇÃO CRÍTICA: Adiciona o filtro '&states=1' para buscar apenas jogos AGENDADOS
    url = (
        f"{BASE_URL}/fixtures/between/{start_str}/{end_str}"
        f"?api_token={api_token}"
        f"&include=participants;league;season"
        f"&per_page=200"
        f"&states=1"
    )
    
    # Adiciona o filtro de ligas (agora vindo do argumento da função)
    if league_ids:
        url += f"&leagues={league_ids}"
        
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                if response.status != 200:
                    print(f"❌ Erro ao buscar fixtures: {response.status} - {await response.text()}")
                    return []
                
                data = (await response.json()).get("data", [])
                upcoming = []
                
                # CORREÇÃO FINAL: Define 'now' como aware (UTC)
                now_aware_utc = datetime.now(timezone.utc)
                
                # PRINTS DE DEBUG (Mantidos para diagnóstico se o problema de 0 persistir)
                print(f"DEBUG: Horário de Execução (UTC): {now_aware_utc.strftime('%Y-%m-%d %H:%M:%S')}")
                if data:
                    print(f"DEBUG: Primeiro Jogo Encontrado na API: {data[0].get('starting_at')}")
                    print(f"DEBUG: Jogos totais recebidos da API (com states=1): {len(data)}")
                else:
                    print("DEBUG: Array de dados (data) da API está VAZIO. O problema é o TOKEN ou a COBERTURA.")
                # FIM DOS PRINTS DE DEBUG
                
                for f in data:
                    try:
                        # 1. Cria o objeto datetime (naive) usando o formato exato da string da API
                        start_time_naive = datetime.strptime(
                            f["starting_at"], 
                            "%Y-%m-%d %H:%M:%S"
                        )
                        
                        # 2. Força o objeto a ser AWARE (UTC) para comparação
                        start_time_aware_utc = start_time_naive.replace(tzinfo=timezone.utc)
                        
                        # Filtra apenas partidas futuras, comparando dois objetos AWARE em UTC
                        if start_time_aware_utc > now_aware_utc:
                            upcoming.append(f)
                    except Exception as e:
                        print(f"Erro ao processar horário do fixture {f.get('id', 'N/A')}: {e}")
                        continue
                        
                print(f"✅ Jogos futuros encontrados: {len(upcoming)}")
                return upcoming
    except Exception as e:
        print(f"⚠ Erro na requisição de partidas: {e}")
        return []

# ===================================
# MÉTRICAS DO TIME (Simuladas)
# ===================================
async def compute_team_metrics(api_token, team_id, last=2):
    # Esta função continua GERANDO DADOS ALEATÓRIOS (Simulação)
    goals_for_avg = random.uniform(0.8, 1.8)
    goals_against_avg = random.uniform(0.8, 1.8)
    win_rate = random.uniform(0.3, 0.7)
    confidence = int(win_rate * 100)
    return {
        "avg_goals_for": goals_for_avg,
        "avg_goals_against": goals_against_avg,
        "win_rate": win_rate,
        "confidence": max(confidence, 10)
    }

# ===================================
# DECIDIR MELHOR MERCADO
# ===================================
def decide_best_market(home_metrics, away_metrics):
    goals_sum = home_metrics["avg_goals_for"] + away_metrics["avg_goals_for"]
    win_diff = home_metrics["win_rate"] - away_metrics["win_rate"]

    options = []

    # Gols
    if goals_sum >= 2.8:
        options.append(("⚽ +2.5 Gols", "blue"))
    elif goals_sum >= 2.0:
        options.append(("⚽ +1.5 Gols", "blue"))
    else:
        if abs(win_diff) < 0.3:
             options.append(("💚 Ambas Marcam", "green"))
        else:
             options.append(("⚽ +1.5 Gols", "blue"))

    # Vitória
    if win_diff >= 0.35:
        options.append(("🏆 Vitória da Casa", "yellow"))
    elif win_diff <= -0.35:
        options.append(("🏆 Vitória do Visitante", "yellow"))

    # Escanteios (Simulado)
    options.append(("⚡ Mais de 8 Escanteios", "purple"))

    suggestion, color = random.choice(options) 
    confidence = min(home_metrics["confidence"], away_metrics["confidence"])
    
    return suggestion, confidence

# ===================================
# HORÁRIO LOCAL
# ===================================
def kickoff_time_local(fixture, tz=TZ):
    try:
        # Lógica para mostrar horário no fuso horário do Brasil
        dt_naive = datetime.strptime(fixture["starting_at"], "%Y-%m-%d %H:%M:%S")
        dt_utc = dt_naive.replace(tzinfo=timezone.utc)
        
        dt_local = dt_utc.astimezone(tz)
        
        now_local = datetime.now(tz)
        
        if dt_local.date() != now_local.date():
            return dt_local.strftime("%H:%M — %d/%m")
        return dt_local.strftime("%H:%M")
    except Exception:
        return "Horário indefinido"

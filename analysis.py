import aiohttp
from datetime import datetime, timezone
import pytz
import random

# ========== CONFIGURAÇÕES ==========
BASE_URL = "https://api.sportmonks.com/v3/football"
TZ = pytz.timezone("America/Sao_Paulo")

# Adicione os IDs das ligas que você deseja filtrar aqui, separados por vírgula.
# Ex: Brasileirão (24), Premier League (2), La Liga (5).
# Por padrão, está vazio para buscar todos os jogos.
LEAGUE_IDS = "" 

# ===================================
# BUSCAR PARTIDAS FUTURAS
# ===================================
async def fetch_upcoming_fixtures(api_token, start_str, end_str):
    url = (
        f"{BASE_URL}/fixtures/between/{start_str}/{end_str}"
        f"?api_token={api_token}"
        f"&include=participants;league;season"
        f"&per_page=200"
    )
    
    # Adiciona o filtro de ligas, se a lista não estiver vazia
    if LEAGUE_IDS:
        url += f"&leagues={LEAGUE_IDS}"
        
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                if response.status != 200:
                    print(f"❌ Erro ao buscar fixtures: {response.status} - {await response.text()}")
                    return []
                
                data = (await response.json()).get("data", [])
                upcoming = []
                
                # CORREÇÃO CRUCIAL V3: Para comparação direta, usamos datetime.now() (naive)
                # O servidor Render geralmente usa UTC como fuso horário padrão do sistema
                now_naive = datetime.now()
                
                for f in data:
                    try:
                        # 1. Cria o objeto datetime (naive) usando o formato exato da string da API
                        start_time_naive = datetime.strptime(
                            f["starting_at"], 
                            "%Y-%m-%d %H:%M:%S"
                        )
                        
                        # Filtra apenas partidas futuras fazendo a comparação de objetos NAIVE.
                        # Isso garante que a comparação não seja afetada pela manipulação incorreta de TZ.
                        if start_time_naive > now_naive:
                            upcoming.append(f)
                    except Exception as e:
                        # Ignora fixtures com formato de horário inválido
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
# *IMPORTANTE:* Esta função continua GERANDO DADOS ALEATÓRIOS para a confiança.
async def compute_team_metrics(api_token, team_id, last=2):
    # Gera métricas padrões se não houver histórico (SIMULAÇÃO)
    goals_for_avg = random.uniform(0.8, 1.8)
    goals_against_avg = random.uniform(0.8, 1.8)
    win_rate = random.uniform(0.3, 0.7)
    confidence = int(win_rate * 100)
    return {
        "avg_goals_for": goals_for_avg,
        "avg_goals_against": goals_against_avg,
        "win_rate": win_rate,
        "confidence": max(confidence, 10) # Garante confiança mínima de 10%
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
        # Se as médias não apontam para muitos gols, sugere Ambas Marcam (se houver equilíbrio)
        if abs(win_diff) < 0.3:
             options.append(("💚 Ambas Marcam", "green"))
        else:
             options.append(("⚽ +1.5 Gols", "blue"))

    # Vitória
    if win_diff >= 0.35:
        options.append(("🏆 Vitória da Casa", "yellow"))
    elif win_diff <= -0.35:
        options.append(("🏆 Vitória do Visitante", "yellow"))

    # Escanteios (Simulado, pois não usa métricas reais)
    options.append(("⚡ Mais de 8 Escanteios", "purple"))

    # Escolhe a sugestão de forma aleatória entre as opções válidas
    suggestion, color = random.choice(options) 
    
    # A confiança é baseada na menor confiança entre os dois times
    confidence = min(home_metrics["confidence"], away_metrics["confidence"])
    
    return suggestion, confidence

# ===================================
# HORÁRIO LOCAL
# ===================================
def kickoff_time_local(fixture, tz=TZ):
    try:
        # 1. Cria o objeto datetime (naive) a partir da string da API
        dt_naive = datetime.strptime(fixture["starting_at"], "%Y-%m-%d %H:%M:%S")
        
        # 2. ANEXA a informação de fuso horário UTC (ASSUMINDO que a API retornou o tempo em UTC)
        # Este é o ponto onde o fuso é forçado para permitir a conversão para BRT.
        dt_utc = dt_naive.replace(tzinfo=timezone.utc)
        
        # 3. Converte para o fuso horário local (TZ)
        dt_local = dt_utc.astimezone(tz)
        
        now_local = datetime.now(tz)
        
        # Verifica se o jogo é no mesmo dia
        if dt_local.date() != now_local.date():
            return dt_local.strftime("%H:%M — %d/%m")
        return dt_local.strftime("%H:%M")
    except Exception:
        return "Horário indefinido"

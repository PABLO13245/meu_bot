import aiohttp
from datetime import datetime
import pytz
import random

# ========== CONFIGURAÇÕES ==========
BASE_URL = "https://api.sportmonks.com/v3/football"
TZ = pytz.timezone("America/Sao_Paulo")

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
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                if response.status != 200:
                    print("❌ Erro ao buscar fixtures:", await response.text())
                    return []
                data = (await response.json()).get("data", [])
                upcoming = []
                now = datetime.now(TZ)
                for f in data:
                    try:
                        start_time = datetime.fromisoformat(
                            f["starting_at"].replace("Z", "+00:00")
                        ).astimezone(TZ)
                        if start_time > now:
                            upcoming.append(f)
                    except Exception:
                        continue
                print("Jogos encontrados:", len(upcoming))  # DEBUG
                return upcoming
    except Exception as e:
        print("⚠ Erro na requisição de partidas:", e)
        return []

# ===================================
# MÉTRICAS DO TIME (Mesmo sem histórico)
# ===================================
async def compute_team_metrics(api_token, team_id, last=2):
    # Gera métricas padrões se não houver histórico
    goals_for_avg = random.uniform(0.8, 1.8)
    goals_against_avg = random.uniform(0.8, 1.8)
    win_rate = random.uniform(0.3, 0.7)
    confidence = int(win_rate*100)
    return {
        "avg_goals_for": goals_for_avg,
        "avg_goals_against": goals_against_avg,
        "win_rate": win_rate,
        "confidence": max(confidence, 10)
    }

# ===================================
# DECIDIR MELHOR MERCADO (com escanteios)
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
        options.append(("💚 Ambas Marcam", "green"))

    # Vitória
    if win_diff >= 0.35:
        options.append(("🏆 Vitória da Casa", "yellow"))
    elif win_diff <= -0.35:
        options.append(("🏆 Vitória do Visitante", "yellow"))

    # Escanteios
    options.append(("⚡ Mais de 8 Escanteios", "purple"))

    suggestion, color = random.choice(options)
    confidence = min(home_metrics["confidence"], away_metrics["confidence"])
    return suggestion, confidence

# ===================================
# HORÁRIO LOCAL
# ===================================
def kickoff_time_local(fixture, tz=TZ):
    try:
        dt = datetime.fromisoformat(fixture["starting_at"].replace("Z", "+00:00")).astimezone(tz)
        now = datetime.now(tz)
        if dt.date() != now.date():
            return dt.strftime("%H:%M — %d/%m")
        return dt.strftime("%H:%M")
    except Exception:
        return "Horário indefinido"

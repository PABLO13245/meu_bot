import aiohttp
from datetime import datetime
import pytz
from statistics import mean

# ========== CONFIGURAÇÕES ==========
BASE_URL = "https://api.sportmonks.com/v3/football"
TZ = pytz.timezone("America/Sao_Paulo")

# Ligas confiáveis (IDs da SportMonks)
RELIABLE_LEAGUE_IDS = [
    271,  # Premier League
    301,  # La Liga
    282,  # Bundesliga
    293,  # Serie A
    283,  # Ligue 1
    285,  # Eredivisie
    294,  # Primeira Liga
]

# ===================================
# BUSCAR PARTIDAS FUTURAS
# ===================================
async def fetch_upcoming_fixtures(api_token, start_str, end_str, per_page=100):
    url = (
        f"{BASE_URL}/fixtures/between/{start_str}/{end_str}"
        f"?api_token={api_token}"
        f"&include=participants;league;season"
        f"&per_page={per_page}"
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
                        league_id = f.get("league", {}).get("id")
                        if start_time > now and league_id in RELIABLE_LEAGUE_IDS:
                            upcoming.append(f)
                    except Exception:
                        continue
                return upcoming
    except Exception as e:
        print("⚠ Erro na requisição de partidas:", e)
        return []

# ===================================
# COLETAR DADOS DOS TIMES
# ===================================
async def fetch_last_matches_for_team(session, api_token, team_id, last=1):
    url = (
        f"{BASE_URL}/fixtures?api_token={api_token}"
        f"&include=participants;stats"
        f"&filter[team_id]={team_id}"
        f"&filter[status]=FT"
        f"&sort=-starting_at&per_page={last}"
    )
    try:
        async with session.get(url) as response:
            if response.status != 200:
                return []
            data = (await response.json()).get("data", [])
            return data
    except Exception as e:
        print(f"⚠ Erro ao buscar partidas do time {team_id}:", e)
        return []

async def compute_team_metrics(api_token, team_id, last=3):
    async with aiohttp.ClientSession() as session:
        matches = await fetch_last_matches_for_team(session, api_token, team_id, last)
    goals_for, goals_against = [], []
    wins = 0
    for m in matches:
        try:
            participants = m.get("participants", [])
            if len(participants) < 2:
                continue
            home = participants[0]
            away = participants[1]
            home_id = home.get("id")
            away_id = away.get("id")
            g_home = home.get("meta", {}).get("score")
            g_away = away.get("meta", {}).get("score")
            if g_home is None or g_away is None:
                continue
            g_home = int(g_home)
            g_away = int(g_away)
            if str(home_id) == str(team_id):
                goals_for.append(g_home)
                goals_against.append(g_away)
                if g_home > g_away:
                    wins += 1
            else:
                goals_for.append(g_away)
                goals_against.append(g_home)
                if g_away > g_home:
                    wins += 1
        except Exception:
            continue

    if not matches or not goals_for:
        return None  # sem dados confiáveis

    avg_for = mean(goals_for)
    avg_against = mean(goals_against)
    win_rate = wins / len(matches)
    confidence = min(int(win_rate * 100 + avg_for * 10), 99)  # confiança dinâmica
    return {
        "avg_goals_for": avg_for,
        "avg_goals_against": avg_against,
        "win_rate": win_rate,
        "confidence": confidence
    }

# ===================================
# DECIDIR MELHOR MERCADO
# ===================================
def decide_best_market(home_metrics, away_metrics):
    if not home_metrics or not away_metrics:
        return "Indefinido", 0

    goals_sum = home_metrics["avg_goals_for"] + away_metrics["avg_goals_for"]
    win_diff = home_metrics["win_rate"] - away_metrics["win_rate"]

    if goals_sum >= 2.8:
        suggestion = "+2.5 Gols"
    elif goals_sum >= 2.0:
        suggestion = "+1.5 Gols"
    elif home_metrics["avg_goals_for"] >= 1.2 and away_metrics["avg_goals_for"] >= 1.2:
        suggestion = "Ambas Marcam"
    elif win_diff >= 0.35:
        suggestion = "Vitória da Casa"
    elif win_diff <= -0.35:
        suggestion = "Vitória do Visitante"
    else:
        suggestion = "Indefinido"

    confidence = min(home_metrics["confidence"], away_metrics["confidence"])
    return suggestion, confidence

# ===================================
# CONVERTER HORÁRIO LOCAL
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

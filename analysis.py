import requests
from datetime import datetime
from statistics import mean
import pytz

BASE_URL = "https://api.sportmonks.com/v3/football"


# =====================================================
# Função genérica para buscar dados
# =====================================================
def get_json(url):
    try:
        r = requests.get(url)
        if r.status_code != 200:
            print("Erro API:", r.text)
            return None
        return r.json()
    except Exception as e:
        print("Erro na requisição:", e)
        return None


# =====================================================
# Buscar partidas futuras (próximas 48h)
# =====================================================
def fetch_upcoming_fixtures(api_token, start_str, end_str, per_page=50):
    url = (
        f"{BASE_URL}/fixtures/between/{start_str}/{end_str}"
        f"?api_token={api_token}"
        f"&include=participants;league"
        f"&per_page={per_page}"
    )
    data = get_json(url)
    if not data or "data" not in data:
        return []
    return data["data"]


# =====================================================
# Buscar últimos jogos de um time
# =====================================================
def fetch_last_matches(api_token, team_id, last=5):
    url = (
        f"{BASE_URL}/fixtures"
        f"?api_token={api_token}"
        f"&filter[team_id]={team_id}"
        f"&filter[status]=FT"
        f"&include=participants;stats"
        f"&sort=-starting_at"
        f"&per_page={last}"
    )
    data = get_json(url)
    if not data or "data" not in data:
        return []
    return data["data"]


# =====================================================
# Calcular médias do time (gols, escanteios, vitórias)
# =====================================================
def compute_team_metrics(api_token, team_id, last=5):
    matches = fetch_last_matches(api_token, team_id, last)
    goals_for, goals_against, corners_for = [], [], []
    wins = 0

    for m in matches:
        try:
            home = m["participants"][0]
            away = m["participants"][1]
            home_id = home["id"]
            away_id = away["id"]

            g_home = int(home.get("meta", {}).get("score", 0))
            g_away = int(away.get("meta", {}).get("score", 0))

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

            # escanteios
            stats = m.get("stats", [])
            for s in stats:
                if str(s.get("team_id")) == str(team_id):
                    corners = s.get("corners", 0)
                    if corners:
                        corners_for.append(int(corners))
        except Exception:
            continue

    avg_for = mean(goals_for) if goals_for else 0.0
    avg_against = mean(goals_against) if goals_against else 0.0
    avg_corners = mean(corners_for) if corners_for else 0.0
    win_rate = wins / len(matches) if matches else 0.0

    return {
        "avg_goals_for": avg_for,
        "avg_goals_against": avg_against,
        "avg_corners": avg_corners,
        "win_rate": win_rate,
    }


# =====================================================
# Decidir o melhor mercado de aposta
# =====================================================
def decide_best_market(home_metrics, away_metrics):
    goals_sum = home_metrics["avg_goals_for"] + away_metrics["avg_goals_for"]
    corners_sum = home_metrics["avg_corners"] + away_metrics["avg_corners"]
    win_delta = home_metrics["win_rate"] - away_metrics["win_rate"]

    # Pontuação interna pra definir o melhor mercado
    score_gols = goals_sum * 10
    score_ambas = (home_metrics["avg_goals_for"] > 1 and away_metrics["avg_goals_for"] > 1) * 15
    score_corners = (corners_sum / 10) * 12
    score_vitoria = abs(win_delta) * 20

    scores = {
        "+2.5 Gols": score_gols,
        "Ambas Marcam": score_ambas,
        "+8 Escanteios": score_corners,
        "Vitória de uma equipe": score_vitoria,
    }

    # Escolhe o mercado com maior pontuação
    best_market = max(scores, key=scores.get)
    confidence = min(99, round(scores[best_market] * 2))

    return best_market, confidence


# =====================================================
# Converter horário para local
# =====================================================
def kickoff_time_local(fixture, tz):
    try:
        start_utc = datetime.fromisoformat(fixture["starting_at"].replace("Z", "+00:00"))
        kickoff_local = start_utc.astimezone(tz)
        return kickoff_local.strftime("%H:%M")
    except Exception:
        return "?"

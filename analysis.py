# analysis.py
import requests
from datetime import datetime
import pytz
from statistics import mean

# ========== CONFIGURAÇÕES ==========
BASE_URL = "https://api.sportmonks.com/v3/football"
TZ = pytz.timezone("America/Sao_Paulo")

# ===================================
# BUSCAR PARTIDAS FUTURAS
# ===================================
def fetch_upcoming_fixtures(api_token, start_str, end_str, per_page=100):
    url = (
        f"{BASE_URL}/fixtures/between/{start_str}/{end_str}"
        f"?api_token={api_token}"
        f"&include=participants;league;season"
        f"&per_page={per_page}"
    )
    try:
        response = requests.get(url)
        if response.status_code != 200:
            print("❌ Erro ao buscar fixtures:", response.text)
            return []
        data = response.json().get("data", [])
        # só jogos futuros
        upcoming = []
        for f in data:
            try:
                start_time = datetime.fromisoformat(
                    f["starting_at"].replace("Z", "+00:00")
                ).astimezone(TZ)
                if start_time > datetime.now(TZ):
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
def fetch_last_matches_for_team(api_token, team_id, last=5):
    url = (
        f"{BASE_URL}/fixtures?api_token={api_token}"
        f"&include=participants;stats"
        f"&filter[team_id]={team_id}"
        f"&filter[status]=FT"
        f"&sort=-starting_at&per_page={last}"
    )
    try:
        response = requests.get(url)
        if response.status_code != 200:
            return []
        data = response.json().get("data", [])
        return data
    except Exception as e:
        print("⚠ Erro ao buscar partidas do time:", e)
        return []

def compute_team_metrics(api_token, team_id, last=5):
    matches = fetch_last_matches_for_team(api_token, team_id, last)
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
        except Exception:
            continue
    avg_for = mean(goals_for) if goals_for else 0.0
    avg_against = mean(goals_against) if goals_against else 0.0
    win_rate = wins / len(matches) if matches else 0.0
    return {
        "avg_goals_for": avg_for,
        "avg_goals_against": avg_against,
        "win_rate": win_rate,
    }

# ===================================
# DECIDIR MELHOR MERCADO
# ===================================
def decide_best_market(home_metrics, away_metrics):
    goals_sum = home_metrics["avg_goals_for"] + away_metrics["avg_goals_for"]
    win_diff = home_metrics["win_rate"] - away_metrics["win_rate"]

    # lógica ajustada: pega o melhor tipo de aposta
    if goals_sum >= 2.8:
        suggestion = "+2.5 Gols"
    elif goals_sum >= 2.0:
        suggestion = "+1.5 Gols"
    elif home_metrics["avg_goals_for"] >= 1.1 and away_metrics["avg_goals_for"] >= 1.1:
        suggestion = "Ambas Marcam"
    elif win_diff >= 0.35:
        suggestion = "Vitória da Casa"
    elif win_diff <= -0.35:
        suggestion = "Vitória do Visitante"
    else:
        suggestion = "Sem sinal forte — evite aposta"

    confidence = 87  # fixo, como você pediu
    return suggestion, confidence

# ===================================
# CONVERTER HORÁRIO LOCAL
# ===================================
def kickoff_time_local(fixture, tz=TZ):
    try:
        dt = datetime.fromisoformat(fixture["starting_at"].replace("Z", "+00:00")).astimezone(tz)
        now = datetime.now(tz)
        # se o jogo for outro dia, mostra data também
        if dt.date() != now.date():
            return dt.strftime("%H:%M — %d/%m")
        return dt.strftime("%H:%M")
    except Exception:
        return "Horário indefinido"

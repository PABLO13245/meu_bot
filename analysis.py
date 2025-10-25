import requests
from statistics import mean

# ===================================
# BUSCAR PARTIDAS FUTURAS (API V3)
# ===================================
def fetch_upcoming_fixtures(API_TOKEN, start_str, end_str):
    """
    Busca partidas futuras entre duas datas.
    """
    print(f"🔍 Buscando partidas entre {start_str} e {end_str}...")

    url = (
        f"https://api.sportmonks.com/v3/football/fixtures/between/{start_str}/{end_str}"
        f"?api_token={API_TOKEN}"
        f"&include=participants;participants.country;league;season"
    )

    try:
        response = requests.get(url)
        print("🌍 Código de status:", response.status_code)

        if response.status_code != 200:
            print("❌ Erro da API:", response.text)
            return None

        data = response.json()
        return data.get("data", [])

    except Exception as e:
        print("⚠ Erro ao buscar partidas:", e)
        return None


# ===================================
# COLETAR DADOS DOS TIMES
# ===================================
def fetch_last_matches_for_team(API_TOKEN, team_id, last=5):
    """
    Busca os últimos jogos de um time.
    """
    url = (
        f"https://api.sportmonks.com/v3/football/fixtures"
        f"?api_token={API_TOKEN}"
        f"&include=participants;stats"
        f"&filter[team_id]={team_id}"
        f"&filter[status]=FT"
        f"&sort=-starting_at"
        f"&per_page={last}"
    )

    try:
        response = requests.get(url)
        if response.status_code != 200:
            print(f"⚠ Erro ao buscar jogos do time {team_id}: {response.text}")
            return []

        data = response.json()
        return data.get("data", [])
    except Exception as e:
        print(f"❌ Erro ao buscar partidas do time {team_id}: {e}")
        return []


def compute_team_metrics(API_TOKEN, team_id):
    """
    Calcula métricas médias de gols, escanteios e vitórias.
    """
    matches = fetch_last_matches_for_team(API_TOKEN, team_id, last=5)
    goals_for, goals_against, corners_for = [], [], []
    wins = 0

    for m in matches:
        try:
            home = m["participants"][0]
            away = m["participants"][1]
            home_id = home["id"]
            away_id = away["id"]

# main.py — Bot Análise Futebol (API-Football)
import os
import asyncio
import requests
from datetime import datetime, timedelta
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from telegram import Bot
import pytz
from statistics import mean

# ==============================
# CONFIGURAÇÃO (API, BOT, CHAT)
# ==============================
API_KEY = "f8270c3b6c8ef0c1e9d3aea73b38b719"  # sua chave API-FOOTBALL
BOT_TOKEN = "8444936746:AAE5JjO5vhrqb-HL7wWr-8kGpOjaCQybmgE"
CHAT_ID = "5245918045"

TZ = pytz.timezone("America/Sao_Paulo")
bot = Bot(token=BOT_TOKEN)

HEADERS = {"x-apisports-key": API_KEY}


# ==============================
# FUNÇÕES DE BUSCA DE DADOS
# ==============================
def get_json(url, params=None):
    """Requisição segura, retorna JSON ou None"""
    try:
        r = requests.get(url, headers=HEADERS, params=params, timeout=15)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        print(f"Erro HTTP: {e}")
        return None


def fetch_fixtures_next(hours_ahead=48):
    """Busca partidas até X horas à frente"""
    now = datetime.utcnow()
    end = now + timedelta(hours=hours_ahead)

    url = "https://v3.football.api-sports.io/fixtures"
    params = {"from": now.strftime("%Y-%m-%d"), "to": end.strftime("%Y-%m-%d")}

    try:
        r = requests.get(url, headers=HEADERS, params=params, timeout=20)
        r.raise_for_status()
        data = r.json()
        partidas = data.get("response", [])
        print(f"✅ {len(partidas)} partidas encontradas.")
        return partidas
    except Exception as e:
        print(f"⚠ Erro ao buscar partidas: {e}")
        return []


def fetch_last_matches_for_team(team_id, last=5):
    """Pega últimos jogos de um time"""
    url = "https://v3.football.api-sports.io/fixtures"
    params = {"team": team_id, "last": last}
    data = get_json(url, params)
    return data.get("response", []) if data else []


def fetch_fixture_statistics(fixture_id):
    """Busca estatísticas de um jogo (corners etc.)"""
    url = "https://v3.football.api-sports.io/fixtures/statistics"
    params = {"fixture": fixture_id}
    data = get_json(url, params)
    return data.get("response", []) if data else []


# ==============================
# ANÁLISE E MÉTRICAS
# ==============================
def compute_team_metrics(team_id):
    matches = fetch_last_matches_for_team(team_id, last=3)
    goals_for, goals_against, wins, corners_for = [], [], 0, []

    for m in matches:
        try:
            home_id = m["teams"]["home"]["id"]
            away_id = m["teams"]["away"]["id"]
            goals_home = m["goals"]["home"]
            goals_away = m["goals"]["away"]
        except Exception:
            continue

        if goals_home is None or goals_away is None:
            continue

        if str(home_id) == str(team_id):
            goals_for.append(goals_home)
            goals_against.append(goals_away)
            if goals_home > goals_away:
                wins += 1
        else:
            goals_for.append(goals_away)
            goals_against.append(goals_home)
            if goals_away > goals_home:
                wins += 1

        # Estatísticas de escanteios
        stats = fetch_fixture_statistics(m["fixture"]["id"])
        try:
            for t in stats:
                if str(t.get("team", {}).get("id")) == str(team_id):
                    for s in t.get("statistics", []):
                        if "corner" in s.get("type", "").lower():
                            val = s.get("value")
                            if isinstance(val, int):
                                corners_for.append(val)
        except Exception:
            pass

    return {
        "avg_goals_for": mean(goals_for) if goals_for else 0,
        "avg_goals_against": mean(goals_against) if goals_against else 0,
        "avg_corners": mean(corners_for) if corners_for else 0,
        "win_rate": wins / len(matches) if matches else 0,
    }


def decide_suggestion(home_metrics, away_metrics):
    goals_sum = home_metrics["avg_goals_for"] + away_metrics["avg_goals_for"]
    corners_sum = home_metrics["avg_corners"] + away_metrics["avg_corners"]
    win_delta = home_metrics["win_rate"] - away_metrics["win_rate"]

    suggestions = []
    if goals_sum >= 2.8:
        suggestions.append("+2.5 Gols")
    elif goals_sum >= 2.0:
        suggestions.append("+1.5 Gols")

    if home_metrics["avg_goals_for"] >= 1.1 and away_metrics["avg_goals_for"] >= 1.1:
        suggestions.append("Ambas Marcam")

    if corners_sum >= 9:
        suggestions.append("+8.5 Escanteios")
    elif corners_sum >= 7:
        suggestions.append("+7.5 Escanteios")

    if win_delta >= 0.35:
        suggestions.append("Vitória provável do Mandante")
    elif win_delta <= -0.35:
        suggestions.append("Vitória provável do Visitante")

    conf = int(
        min(
            98,
            (home_metrics["win_rate"] * 40)
            + (away_metrics["win_rate"] * 20)
            + (goals_sum *

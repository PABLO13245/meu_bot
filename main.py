# main.py — Bot Analise Futebol (API-Football)
import os
import asyncio
import requests
from datetime import datetime, date
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from telegram import Bot
import pytz
from statistics import mean

# ==============================
# CONFIGURAÇÃO (substitua ou use ENV vars)
# ==============================
API_KEY = os.environ.get("API_FOOTBALL_KEY", "08493b777211993f1f86dcbaae2b4fad")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "8444936746:AAE5JjO5vhrqb-HL7wWr-8kGpOjaCQybmgE")
CHAT_ID = os.environ.get("CHAT_ID", "5245918045")
TZ = pytz.timezone("America/Sao_Paulo")

HEADERS = {
    "x-apisports-key": API_KEY
}

bot = Bot(token=BOT_TOKEN)

# ==============================
# HELPERS DE REQUISIÇÃO
# ==============================
def get_json(url, params=None, headers=None, timeout=15):
    """Requisição segura com requests; retorna dict ou None."""
    try:
        r = requests.get(url, params=params, headers=headers or HEADERS, timeout=timeout)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        print("HTTP error:", e, url, params)
        return None

# ==============================
# COLETA / PROCESSAMENTO DE DADOS
# ==============================
def fetch_fixtures_today():
    """Busca fixtures do dia atual (UTC -> convert later if needed)."""
    today = date.today().strftime("%Y-%m-%d")
    url = "https://v3.football.api-sports.io/fixtures"
    params = {"date": today}
    data = get_json(url, params=params)
    if not data:
        return []
    return data.get("response", [])

def fetch_last_matches_for_team(team_id, last=5):
    """Pega os últimos last fixtures de um time (passado)."""
    url = "https://v3.football.api-sports.io/fixtures"
    params = {"team": team_id, "last": last}
    data = get_json(url, params=params)
    return data.get("response", []) if data else []

def fetch_fixture_statistics(fixture_id):
    """Puxa estatísticas de um fixture (inclui corners se disponível)."""
    url = "https://v3.football.api-sports.io/fixtures/statistics"
    params = {"fixture": fixture_id}
    data = get_json(url, params=params)
    return data.get("response", []) if data else []

def compute_team_metrics(team_id):
    """
    Calcula:
     - avg_goals_for (últimos 5)
     - avg_goals_against
     - avg_corners_for (se disponível via statistics)
     - win_rate (últimos 5)
    """
    matches = fetch_last_matches_for_team(team_id, last=5)
    goals_for = []
    goals_against = []
    wins = 0
    corners_for = []

    for m in matches:
        # identificar se time era home ou away
        try:
            home_id = m["teams"]["home"]["id"]
            away_id = m["teams"]["away"]["id"]
            goals_home = m["goals"]["home"]
            goals_away = m["goals"]["away"]
        except Exception:
            continue

        # skip if goals None
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

        # tentar pegar corners via fixture statistics
        stats = fetch_fixture_statistics(m["fixture"]["id"])
        # stats structure: list with two dicts per team, each has 'type' and 'value', but wrapped per team
        # We'll try to extract 'Corners' entries for the team
        try:
            for team_stats in stats:
                # each team_stats has 'team' and 'statistics' list
                t = team_stats.get("team", {})
                if t.get("id") is None:
                    continue
                if str(t.get("id")) == str(team_id):
                    stlist = team_stats.get("statistics", [])
                    for s in stlist:
                        if s.get("type", "").lower() in ("corner", "corners", "corners won"):
                            val = s.get("value")
                            if isinstance(val, int):
                                corners_for.append(val)
                            elif isinstance(val, str) and val.isdigit():
                                corners_for.append(int(val))
        except Exception:
            pass

    avg_for = mean(goals_for) if goals_for else 0.0
    avg_against = mean(goals_against) if goals_against else 0.0
    avg_corners = mean(corners_for) if corners_for else 0.0
    win_rate = wins / len(matches) if matches else 0.0

    return {
        "avg_goals_for": avg_for,
        "avg_goals_against": avg_against,
        "avg_corners": avg_corners,
        "win_rate": win_rate,
        "sample_count": len(matches)
    }

def decide_suggestion(home_metrics, away_metrics):
    """
    Regras simples e transparentes para sugerir:
     - Se soma de avg_goals > 2.8 => +2.5 Gols
     - Se both avg_goals_for > 1.2 => Ambas Marcam
     - If avg_corners sum > 9 => +8.5 Escanteios
     - If win_rate delta > 0.35 => Vitória provável
     - Compose a small confidence percent from normalized metrics
    """
    goals_sum = home_metrics["avg_goals_for"] + away_metrics["avg_goals_for"]
    corners_sum = home_metrics["avg_corners"] + away_metrics["avg_corners"]
    win_delta = home_metrics["win_rate"] - away_metrics["win_rate"]

    suggestions = []
    # goals
    if goals_sum >= 2.8:
        suggestions.append("+2.5 Gols")
    elif goals_sum >= 2.0:
        suggestions.append("+1.5 Gols")

    # both score
    if home_metrics["avg_goals_for"] >= 1.1 and away_metrics["avg_goals_for"] >= 1.1:
        suggestions.append("Ambas Marcam")

    # corners
    if corners_sum >= 9:
        suggestions.append("+8.5 Escanteios")
    elif corners_sum >= 7:
        suggestions.append("+7.5 Escanteios")

    # victory
    if win_delta >= 0.35:
        suggestions.append("Vitória provável do Mandante")
    elif win_delta <= -0.35:
        suggestions.append("Vitória provável do Visitante")

    # Confidence: combine normalized metrics to percentage
    # wins contribution
    conf = 0.0
    conf += max(0, (home_metrics["win_rate"] - away_metrics["win_rate"])) * 50  # up to 50%
    conf += min(30, (goals_sum / 4.0) * 30)  # up to 30%
    conf += min(20, (corners_sum / 15.0) * 20)  # up to 20%
    confidence = min(98, round(abs(conf), 0))  # cap

    if not suggestions:
        suggestions.append("Sem sinal forte — evitar aposta agressiva")

    return suggestions, int(confidence)

# ==============================
# FORMATAÇÃO DE MENSAGEM
# ==============================
def country_flag_from_name(name):
    # simple heuristics mapping substrings to flags
    mapping = {
        "brazil": "🇧🇷", "england": "🏴", "spain": "🇪🇸", "france": "🇫🇷",
        "germany": "🇩🇪", "italy": "🇮🇹", "portugal": "🇵🇹", "argentina": "🇦🇷",
        "usa": "🇺🇸", "japan": "🇯🇵", "mexico": "🇲🇽", "netherlands": "🇳🇱",
        "turkey": "🇹🇷", "chile": "🇨🇱", "uruguay": "🇺🇾"
    }
    low = name.lower()
    for k, v in mapping.items():
        if k in low:
            return v
    return "⚽"

def build_message(fixtures, qty):
    now = datetime.now(TZ)
    header = f"📅 Análises de Hoje — {now.strftime('%d/%m/%Y')}\n"
    header += f"⏱ Envio automático — {now.strftime('%H:%M')} (BRT)\n\n"
    header += f"🔥 Top {qty} oportunidades 🔥\n\n"
    lines = [header]

    for idx, f in enumerate(fixtures[:qty], start=1):
        try:
            home = f["teams"]["home"]["name"]
            away = f["teams"]["away"]["name"]
            home_id = f["teams"]["home"]["id"]
            away_id = f["teams"]["away"]["id"]
            league = f["league"]["name"]
            kickoff_utc = datetime.fromtimestamp(f["fixture"]["timestamp"], pytz.utc)
            kickoff_local = kickoff_utc.astimezone(TZ).strftime("%H:%M")
        except Exception:
            continue

        # metrics
        hm = compute_team_metrics(home_id)
        am = compute_team_metrics(away_id)
        suggestions, confidence = decide_suggestion(hm, am)

        flag_home = country_flag_from_name(home)
        flag_away = country_flag_from_name(away)

        part = (
            f"{idx}. {flag_home} {home} x {away} {flag_away}\n"
            f"🏆 {league}  •  🕒 {kickoff_local}\n"
            f"📊 Média gols (casa/fora): {round(hm['avg_goals_for'],2)} / {round(am['avg_goals_for'],2)}\n"
            f"🔁 Média escanteios (casa/fora): {round(hm['avg_corners'],2)} / {round(am['avg_corners'],2)}\n"
            f"📈 Win rate (últ5): {round(hm['win_rate']*100,1)}% / {round(am['win_rate']*100,1)}%\n"
            f"🎯 Sugestões: {', '.join(suggestions)}\n"
            f"💹 Confiança estimada: {confidence}%\n"
            "────────────────────────────────\n"
        )
        lines.append(part)

    footer = "\n🔎 Observação: dados baseados em últimos 5 jogos; escanteios podem estar incompletos.\n_Boa sorte — analise com responsabilidade._"
    lines.append(footer)
    return "\n".join(lines)

# ==============================
# FLUXO PRINCIPAL (chamada pelo agendador)
# ==============================
async def run_analysis_send(qtd):
    try:
        fixtures_all = fetch_fixtures_today()
        if not fixtures_all:
            await bot.send_message(CHAT_ID, text="⚠ Nenhuma partida encontrada para hoje.")
            return

        # sort by time and select top candidates (here top by earliest kickoff)
        fixtures_all = sorted(fixtures_all, key=lambda x: x["fixture"]["timestamp"])
        # build message
        message = await asyncio.to_thread(build_message, fixtures_all, qtd)
        # send (Telegram Markdown)
        await bot.send_message(chat_id=CHAT_ID, text=message, parse_mode="Markdown")
    except Exception as e:
        print("run_analysis_send error:", e)
        await bot.send_message(CHAT_ID, text=f"❌ Erro na análise global: {e}")

# ==============================
# AGENDADOR (3 horários com quantidades diferentes)
# ==============================
def start_scheduler():
    scheduler = AsyncIOScheduler(timezone=TZ)
    # 06:00 -> 5 jogos
    scheduler.add_job(lambda: asyncio.create_task(run_analysis_send(5)), "cron", hour=6, minute=0)
    # 15:00 -> 6 jogos
    scheduler.add_job(lambda: asyncio.create_task(run_analysis_send(6)), "cron", hour=15, minute=0)
    # 19:00 -> 5 jogos
    scheduler.add_job(lambda: asyncio.create_task(run_analysis_send(5)), "cron", hour=19, minute=0)
    scheduler.start()
    print("Scheduler started: 06:00(5), 15:00(6), 19:00(5) BRT")

# ==============================
# START
# ==============================
async def main():
    start_scheduler()
    # keep alive
    while True:
        await asyncio.sleep(60)

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "test":
        import asyncio
        asyncio.(run_analisa_partidas())
    else:
        import asyncio
        asyncio.run(main())

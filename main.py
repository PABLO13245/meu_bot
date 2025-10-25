import os
import asyncio
import requests
from datetime import datetime, timedelta
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from telegram import Bot
import pytz
from statistics import mean

# ==============================
# CONFIGURAÇÕES
# ==============================
API_TOKEN = os.getenv("API_TOKEN")  # Token da SportMonks
BOT_TOKEN = os.getenv("TELEGRAM_TOKEN")  # Token do seu bot do Telegram
CHAT_ID = os.getenv("CHAT_ID")  # ID do chat onde vai enviar as mensagens
TZ = pytz.timezone("America/Sao_Paulo")

BASE_URL = "https://api.sportmonks.com/v3/football"
bot = Bot(token=BOT_TOKEN)

# ==============================
# FUNÇÃO DE REQUISIÇÃO GENÉRICA
# ==============================
def get_json(endpoint, params=None):
    token = API_TOKEN
    if not token:
        print("❌ ERRO: Variável de ambiente API_TOKEN não encontrada.")
        return None

    headers = {"Authorization": f"Bearer {token}"}
    url = f"{BASE_URL}/{endpoint}"

    print(f"🌐 Requisitando: {url}")
    try:
        response = requests.get(url, headers=headers, params=params)
        print(f"🔢 Status code: {response.status_code}")

        if response.status_code != 200:
            print(f"⚠ Erro da API: {response.text}")
            return None

        return response.json()
    except Exception as e:
        print(f"❌ Erro na requisição: {e}")
        return None


# ==============================
# BUSCAR PARTIDAS FUTURAS (CORRIGIDO)
# ==============================
def fetch_upcoming_fixtures(API_TOKEN, start_str, end_str):
    import requests

    url = (
        "https://api.sportmonks.com/v3/football/fixtures"
        f"?api_token={API_TOKEN}"
        "&include=participants;league;season"
        f"&filters[status]=NS"
        f"&filter[between]={start_str},{end_str}"
        "&per_page=50"
    )

    print(f"🔵 Buscando partidas entre {start_str} e {end_str}...")
    try:
        resposta = requests.get(url)
        print(f"🔹 Status code: {resposta.status_code}")

        if resposta.status_code != 200:
            print(f"❌ Erro da API: {resposta.text}")
            return []

        dados = resposta.json()
        fixtures = dados.get("data", [])
        print(f"✅ {len(fixtures)} partidas encontradas com status 'NS'.")
        return fixtures

    except Exception as e:
        print(f"❌ Erro durante a requisição: {e}")
        return []


# ==============================
# COLETAR DADOS DOS TIMES
# ==============================
def fetch_last_matches_for_team(team_id, last=5):
    params = {
        "include": "participants;stats",
        "filter[team_id]": team_id,
        "filter[status]": "FT",
        "sort": "-starting_at",
        "per_page": last
    }
    data = get_json("fixtures", params)
    return data["data"] if data and "data" in data else []


def compute_team_metrics(team_id):
    matches = fetch_last_matches_for_team(team_id, last=5)
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
        except Exception:
            continue

        if g_home is None or g_away is None:
            continue

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

        stats = m.get("stats", [])
        for s in stats:
            if str(s.get("team_id")) == str(team_id):
                corners = s.get("corners", 0)
                if corners:
                    corners_for.append(int(corners))

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


# ==============================
# DECISÃO DAS APOSTAS
# ==============================
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

    conf = 0
    conf += max(0, win_delta) * 50
    conf += min(30, (goals_sum / 4) * 30)
    conf += min(20, (corners_sum / 15) * 20)
    confidence = min(98, round(abs(conf)))

    if not suggestions:
        suggestions.append("Sem sinal forte — evite aposta arriscada")

    return suggestions, confidence


# ==============================
# GERAR MENSAGEM
# ==============================
def country_flag_from_name(name):
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
    header = (
        f"📅 Análises — {now.strftime('%d/%m/%Y')}\n"
        f"⏱ Atualizado — {now.strftime('%H:%M')} (BRT)\n\n"
        f"🔥 Top {qty} Oportunidades (48h) 🔥\n\n"
    )
    lines = [header]

    for idx, f in enumerate(fixtures[:qty], start=1):
        try:
            participants = f["participants"]
            home = participants[0]["name"]
            away = participants[1]["name"]
            league = f.get("league", {}).get("name", "Desconhecida")
            home_id = participants[0]["id"]
            away_id = participants[1]["id"]
            kickoff = datetime.fromisoformat(f["starting_at"].replace("Z", "+00:00")).astimezone(TZ)
            kickoff_local = kickoff.strftime("%H:%M")
        except Exception:
            continue

        hm = compute_team_metrics(home_id)
        am = compute_team_metrics(away_id)
        suggestions, confidence = decide_suggestion(hm, am)
        flag_home, flag_away = country_flag_from_name(home), country_flag_from_name(away)

        part = (
            f"{idx}. {flag_home} {home} x {away} {flag_away}\n"
            f"🏆 {league}  •  🕒 {kickoff_local}\n"
            f"📊 Gols médios: {hm['avg_goals_for']:.2f} / {am['avg_goals_for']:.2f}\n"
            f"🔁 Escanteios médios: {hm['avg_corners']:.2f} / {am['avg_corners']:.2f}\n"
            f"📈 Win rate: {hm['win_rate']*100:.1f}% / {am['win_rate']*100:.1f}%\n"
            f"🎯 Sugestões: {', '.join(suggestions)}\n"
            f"💹 Confiança: {confidence}%\n"
            "──────────────────────────────\n"
        )
        lines.append(part)

    footer = (
        "\n🔎 Obs: baseado nos últimos 5 jogos; escanteios podem estar incompletos.\n"
        "Use análise responsável."
    )
    lines.append(footer)
    return "\n".join(lines)


# ==============================
# EXECUÇÃO AUTOMÁTICA (AGENDADOR)
# ==============================
async def run_analysis_send(qtd):
    now = datetime.utcnow()
    start_str = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    end_str = (now + timedelta(hours=48)).strftime("%Y-%m-%dT%H:%M:%SZ")

    try:
        fixtures = fetch_upcoming_fixtures(API_TOKEN, start_str, end_str)
        if not fixtures:
            await bot.send_message(CHAT_ID, "⚠ Nenhuma partida encontrada nas próximas 48h.")
            return

        fixtures = sorted(fixtures, key=lambda x: x["starting_at"])
        message = await asyncio.to_thread(build_message, fixtures, qtd)
        await bot.send_message(CHAT_ID, message, parse_mode="Markdown")

    except Exception as e:
        await bot.send_message(CHAT_ID, f"❌ Erro na análise: {e}")


def start_scheduler():
    scheduler = AsyncIOScheduler(timezone=TZ)
    scheduler.add_job(lambda: asyncio.create_task(run_analysis_send(3)), "cron", hour=6, minute=0)
    scheduler.add_job(lambda: asyncio.create_task(run_analysis_send(3)), "cron", hour=15, minute=0)
    scheduler.add_job(lambda: asyncio.create_task(run_analysis_send(3)), "cron", hour=19, minute=0)
    scheduler.start()
    print("🕒 Agendador ativo: 06:00, 15:00, 19:00 BRT")


async def main():
    start_scheduler()
    print("🚀 Bot iniciado e rodando continuamente...")
    while True:
        await asyncio.sleep(60)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("🛑 Bot interrompido manualmente.")

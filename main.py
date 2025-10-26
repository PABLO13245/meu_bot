import os
import asyncio
from datetime import datetime, timedelta, timezone
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from telegram import Bot
import pytz

from analysis import (
    fetch_upcoming_fixtures,
    compute_team_metrics,
    decide_best_market,
    kickoff_time_local,
    RELIABLE_LEAGUES
)

API_TOKEN = os.getenv("API_TOKEN")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
TZ = pytz.timezone("America/Sao_Paulo")
bot = Bot(token=TELEGRAM_TOKEN)
TOP_QTY = 7

async def build_message(fixtures, api_token, qty=7):
    now = datetime.now(TZ)
    header = (
        f"📅 Análises — {now.strftime('%d/%m/%Y')}\n"
        f"⏱ Atualizado — {now.strftime('%H:%M')} (BRT)\n\n"
        f"🔥 Top {qty} Oportunidades (48h) 🔥\n\n"
    )
    lines = [header]
    count = 0
    ignored_count = 0

    async def analyze_fixture(f, idx):
        league_name = f.get("league", {}).get("name", "Desconhecida")
        if league_name not in RELIABLE_LEAGUES:
            return None, True

        participants = f.get("participants", [])
        if len(participants) < 2:
            return None, True

        home = participants[0].get("name", "Casa")
        away = participants[1].get("name", "Fora")
        home_id = participants[0].get("id")
        away_id = participants[1].get("id")
        kickoff_local = kickoff_time_local(f, TZ)

        hm = await compute_team_metrics(api_token, home_id)
        am = await compute_team_metrics(api_token, away_id)
        suggestion, confidence = decide_best_market(hm, am)

        part = (
            f"{idx}. ⚽ {home} x {away}\n"
            f"🏆 {league_name}  •  🕒 {kickoff_local}\n"
            f"🎯 Sugestão principal: {suggestion}\n"
            f"💹 Confiança: {confidence}%\n"
            "──────────────────────────────\n"
        )
        return part, False

    tasks = [analyze_fixture(f, idx) for idx, f in enumerate(fixtures, start=1)]
    results = await asyncio.gather(*tasks)

    for res, ignored in results:
        if ignored:
            ignored_count += 1
            continue
        if res:
            lines.append(res)
            count += 1
            if count >= qty:
                break

    if count == 0:
        lines.append("⚠ Nenhuma partida encontrada para análise nas próximas 48h.\n")

    if ignored_count > 0:
        lines.append(f"⚠ {ignored_count} partidas foram ignoradas por não estarem em ligas confiáveis.\n")

    footer = "\n🔎 Obs: análise baseada em últimos 5 jogos. Use responsabilidade."
    lines.append(footer)
    return "\n".join(lines)

async def run_analysis_send(qtd=TOP_QTY):
    now = datetime.now(timezone.utc)
    start_str = now.strftime("%Y-%m-%d")
    end_str = (now + timedelta(hours=48)).strftime("%Y-%m-%d")
    try:
        fixtures = await fetch_upcoming_fixtures(API_TOKEN, start_str, end_str, per_page=100)
        if not fixtures:
            await bot.send_message(chat_id=CHAT_ID, text="⚠ Nenhuma partida encontrada nas próximas 48h.")
            return
        fixtures = sorted(fixtures, key=lambda x: x.get("starting_at", ""))
        message = await build_message(fixtures, API_TOKEN, qtd)
        await bot.send_message(chat_id=CHAT_ID, text=message, parse_mode="Markdown")
    except Exception as e:
        print("Erro run_analysis_send:", e)
        try:
            await bot.send_message(chat_id=CHAT_ID, text=f"❌ Erro na análise: {e}")
        except Exception:
            pass

def start_scheduler():
    scheduler = AsyncIOScheduler(timezone=TZ)
    scheduler.add_job(lambda: asyncio.create_task(run_analysis_send(TOP_QTY)), "cron", hour=6, minute=0)
    scheduler.add_job(lambda: asyncio.create_task(run_analysis_send(TOP_QTY)), "cron", hour=16, minute=0)
    scheduler.add_job(lambda: asyncio.create_task(run_analysis_send(TOP_QTY)), "cron", hour=19, minute=0)
    scheduler.start()
    print("Scheduler started: 06:00, 16:00, 19:00 BRT")

async def main():
    start_scheduler()
    if os.getenv("TEST_NOW", "0") == "1":
        print("TEST_NOW=1 -> enviando teste imediato")
        await run_analysis_send(TOP_QTY)
    await asyncio.Event().wait()  # mantém bot vivo

if __name__ == "__main__":
    missing = []
    if not API_TOKEN:
        missing.append("API_TOKEN")
    if not TELEGRAM_TOKEN:
        missing.append("TELEGRAM_TOKEN")
    if not CHAT_ID:
        missing.append("CHAT_ID")
    if missing:
        print("⚠ Variáveis de ambiente ausentes:", missing)
        import sys; sys.exit(1)
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Bot interrompido manualmente.")

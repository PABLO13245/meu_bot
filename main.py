# main.py
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
    kickoff_time_local
)

# CONFIGURAÇÕES via ENV
API_TOKEN = os.getenv("API_TOKEN")            # SportMonks token
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")  # Telegram bot token
CHAT_ID = os.getenv("CHAT_ID")                # chat id (string)
TZ = pytz.timezone("America/Sao_Paulo")
bot = Bot(token=TELEGRAM_TOKEN)

# Quantidade de partidas por envio (você pediu 7)
TOP_QTY = 7

def build_message(fixtures, api_token, qty=7):
    now = datetime.now(TZ)
    header = (
        f"📅 Análises — {now.strftime('%d/%m/%Y')}\n"
        f"⏱ Atualizado — {now.strftime('%H:%M')} (BRT)\n\n"
        f"🔥 Top {qty} Oportunidades (48h) 🔥\n\n"
    )
    lines = [header]

    count = 0
    for idx, f in enumerate(fixtures, start=1):
        if count >= qty:
            break
        participants = f.get("participants", [])
        if len(participants) < 2:
            continue
        home = participants[0].get("name", "Casa")
        away = participants[1].get("name", "Fora")
        league = f.get("league", {}).get("name", "Desconhecida")
        home_id = participants[0].get("id")
        away_id = participants[1].get("id")
        kickoff_local = kickoff_time_local(f, TZ)

        # calcula métricas
        hm = compute_team_metrics(api_token, home_id, last=5)
        am = compute_team_metrics(api_token, away_id, last=5)

        # decide a melhor aposta
        suggestion, confidence = decide_best_market(hm, am)

        part = (
            f"{idx}. ⚽ {home} x {away}\n"
            f"🏆 {league}  •  🕒 {kickoff_local}\n"
            f"🎯 Sugestão principal: {suggestion}\n"
            f"💹 Confiança: {confidence}%\n"
            "──────────────────────────────\n"
        )
        lines.append(part)
        count += 1

    if count == 0:
        lines.append("⚠ Nenhuma partida encontrada para análise nas próximas 48h.\n")

    footer = "\n🔎 Obs: análise baseada em últimos 5 jogos. Use responsabilidade."
    lines.append(footer)
    # return single string (Markdown)
    return "\n".join(lines)

async def run_analysis_send(qtd=TOP_QTY):
    # build date range: next 48h (SportMonks accepts YYYY-MM-DD for between)
    now = datetime.now(timezone.utc)
    start_str = now.strftime("%Y-%m-%d")
    end_str = (now + timedelta(hours=48)).strftime("%Y-%m-%d")

    try:
        fixtures = fetch_upcoming_fixtures(API_TOKEN, start_str, end_str, per_page=100)
        if not fixtures:
            await bot.send_message(chat_id=CHAT_ID, text="⚠ Nenhuma partida encontrada nas próximas 48h.")
            return
        # sort by starting_at
        fixtures = sorted(fixtures, key=lambda x: x.get("starting_at", ""))
        message = await asyncio.to_thread(build_message, fixtures, API_TOKEN, qtd)
        await bot.send_message(chat_id=CHAT_ID, text=message, parse_mode="Markdown")
    except Exception as e:
        # log and send minimal error
        print("Erro run_analysis_send:", e)
        try:
            await bot.send_message(chat_id=CHAT_ID, text=f"❌ Erro na análise: {e}")
        except Exception:
            pass

def start_scheduler():
    scheduler = AsyncIOScheduler(timezone=TZ)
    # 06:00, 16:00, 19:00 BRT
    scheduler.add_job(lambda: asyncio.create_task(run_analysis_send(TOP_QTY)), "cron", hour=6, minute=0)
    scheduler.add_job(lambda: asyncio.create_task(run_analysis_send(TOP_QTY)), "cron", hour=16, minute=0)
    scheduler.add_job(lambda: asyncio.create_task(run_analysis_send(TOP_QTY)), "cron", hour=19, minute=0)
    scheduler.start()
    print("Scheduler started: 06:00, 16:00, 19:00 BRT")

async def main():
    start_scheduler()
    # test-on-start support
    if os.getenv("TEST_NOW", "0") == "1":
        print("TEST_NOW=1 -> enviando teste imediato")
        await run_analysis_send(TOP_QTY)
    # keep alive
    while True:
        await asyncio.sleep(60)

if _name_ == "_main_":
    # quick check for env variables
    missing = []
    if not API_TOKEN:
        missing.append("API_TOKEN")
    if not TELEGRAM_TOKEN:
        missing.append("TELEGRAM_TOKEN")
    if not CHAT_ID:
        missing.append("CHAT_ID")
    if missing:
        print("⚠ Variáveis de ambiente ausentes:", missing)
        print("Defina-as antes de rodar. Exemplo (bash):")
        print(' export API_TOKEN="seu_token"')
        print(' export TELEGRAM_TOKEN="seu_telegram_token"')
        print(' export CHAT_ID="sua_chat_id"')
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Bot interrompido manualmente.")

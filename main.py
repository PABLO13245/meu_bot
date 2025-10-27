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

# CRÍTICO: Quantidade de partidas por envio, voltando para 7
TOP_QTY = 7 

async def build_message(fixtures, api_token, qty=TOP_QTY):
    now = datetime.now(TZ)
    
    # 1. Processar e Enriquecer os dados com Sugestão e Confiança
    enriched_fixtures = []
    for f in fixtures:
        participants = f.get("participants", [])
        if len(participants) < 2:
            continue
            
        home_id = participants[0].get("id")
        away_id = participants[1].get("id")

        # Chamada assíncrona para métricas
        hm = await compute_team_metrics(api_token, home_id, last=5)
        am = await compute_team_metrics(api_token, away_id, last=5)

        # Decisão da aposta
        suggestion, confidence = decide_best_market(hm, am)
        
        # Anexa os dados de análise ao objeto da partida
        f["suggestion"] = suggestion
        f["confidence"] = confidence
        
        # Adiciona apenas se houver uma sugestão forte (confiança > 70% por exemplo)
        if confidence > 0: # Como a confiança está fixa, todos são incluídos.
            enriched_fixtures.append(f)

    # 2. ORDENAÇÃO: Ordena pela CONFIANÇA (descrescente) e depois pela HORA (crescente)
    # A confiança (f["confidence"]) é o critério principal
    # A hora (f["starting_at"]) é o critério de desempate
    enriched_fixtures.sort(key=lambda f: (f["confidence"], f["starting_at"]), reverse=True)


    header = (
        f"📅 Análises — {now.strftime('%d/%m/%Y')} (JOGOS DE HOJE)\n"
        f"⏱ Atualizado — {now.strftime('%H:%M')} (BRT)\n\n"
        f"🔥 Top {qty} Oportunidades do Dia 🔥\n\n" 
    )
    lines = [header]

    # 3. CONSTRUÇÃO DA MENSAGEM: Itera apenas sobre os TOP N
    count = 0
    # Limita a iteração ao TOP_QTY
    for idx, f in enumerate(enriched_fixtures[:qty], start=1): 
        participants = f.get("participants", [])
        home = participants[0].get("name", "Casa")
        away = participants[1].get("name", "Fora")
        league = f.get("league", {}).get("name", "Desconhecida")
        kickoff_local = kickoff_time_local(f, TZ)
        suggestion = f["suggestion"]
        confidence = f["confidence"]

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
        lines.append("⚠ Nenhuma partida encontrada para análise hoje com sinal forte.\n")

    footer = "\n🔎 Obs: análise baseada em últimos 5 jogos. Use responsabilidade."
    lines.append(footer)
    # return single string (Markdown)
    return "\n".join(lines)

async def run_analysis_send(qtd=TOP_QTY):
    # CRÍTICO: build date range: Apenas hoje (0 dias)
    now = datetime.now(timezone.utc)
    
    # Busca do início do dia (hoje) até o final do dia (hoje)
    start_str = now.strftime("%Y-%m-%d")
    end_str = start_str 

    try:
        fixtures = await fetch_upcoming_fixtures(API_TOKEN, start_str, end_str, per_page=500)
        
        if not fixtures:
            message = f"⚠ Nenhuma partida agendada para hoje ({start_str}). Verifique seu API_TOKEN e ligas."
            print(message)
            await bot.send_message(chat_id=CHAT_ID, text=message)
            return
            
        # O SORTING e a LIMIÇÃO para os TOP 7 ocorrem dentro do build_message
        message = await build_message(fixtures, API_TOKEN, qtd)
        
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
    # Mantendo os horários de envio: 06:00, 16:00, 19:00 BRT
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

if __name__ == "__main__":
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

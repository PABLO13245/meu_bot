from keep_alive import keep_alive
keep_alive()

import asyncio
import requests
import pytz
from datetime import datetime
from telegram import Bot
from telegram.constants import ParseMode
from apscheduler.schedulers.asyncio import AsyncIOScheduler

# === CONFIGURAÇÕES ===
TOKEN = ""8444936746:AAE5JjO5vhrqb-HL7wWr-8kGpOjaCQybmgE
CHAT_ID = "5245918045"

bot = Bot(token=TOKEN)

async def analisar_partidas():
    try:
        url = "https://www.scorebat.com/video-api/v3/feed/"
        resposta = requests.get(url, timeout=10).json()

        partidas = resposta.get("response", [])
        if not partidas:
            await bot.send_message(chat_id=CHAT_ID, text="⚠ Nenhuma partida encontrada no momento.")
            return

        mensagens = []
        for jogo in partidas[:5]:
            titulo = jogo.get("title", "Partida sem título")
            competicao = jogo.get("competition", {}).get("name", "Desconhecida")
            data = jogo.get("date", "")[:16].replace("T", " ")
            video_url = jogo.get("matchviewUrl", "")

            mensagens.append(
                f"🏆 <b>{competicao}</b>\n⚽ {titulo}\n🕒 {data}\n🔗 <a href='{video_url}'>Ver detalhes</a>"
            )

        mensagem_final = "\n\n".join(mensagens)
        await bot.send_message(chat_id=CHAT_ID, text=f"📊 <b>Análise automática de jogos:</b>\n\n{mensagem_final}", parse_mode=ParseMode.HTML)

    except Exception as e:
        await bot.send_message(chat_id=CHAT_ID, text=f"❌ Erro ao obter partidas: {e}")

async def main():
    tz = pytz.timezone("America/Sao_Paulo")
    scheduler = AsyncIOScheduler(timezone=tz)

    # Horários automáticos
    scheduler.add_job(analisar_partidas, 'cron', hour=6, minute=0)
    scheduler.add_job(analisar_partidas, 'cron', hour=18, minute=0)
    scheduler.start()

    # Executa uma vez imediatamente (modo teste)
    await analisar_partidas()

    # Mantém o bot rodando
    while True:
        await asyncio.sleep(60)

if _name_ == "_main_":
    asyncio.run(main())
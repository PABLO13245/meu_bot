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
TOKEN = "8444936746:AAE5JjO5vhrqb-HL7wWr-8kGpOjaCQybmgE"
CHAT_ID = "5245918045"

bot = Bot(token=TOKEN)

async def analisar_partidas():
    try:
        url = f"https://www.scorebat.com/video-api/v3/feed/?token={ab6e5b1b2e0442c99c5d0a627730b33f}"
        resposta = requests.get(url, timeout=10)
        partidas = resposta.json().get("response", [])

        if not partidas:
            await bot.send_message(chat_id=CHAT_ID, text="⚠ Nenhuma partida encontrada no momento.")
            return

        mensagens = []
        for jogo in partidas[:5]:
            titulo = jogo.get("title", "Partida sem título")
            competicao = jogo.get("competition", {}).get("name", "Desconhecida")
            data = jogo.get("date", "")[:16].replace("T", " ")
            video_url = jogo.get("matchviewUrl", "#")

            mensagens.append(
                f"⚽ <b>{titulo}</b>\n"
                f"🏆 {competicao}\n"
                f"📅 {data}\n"
                f"<a href='{video_url}'>Ver detalhes</a>\n"
            )

        final = "\n\n".join(mensagens)
        await bot.send_message(
            chat_id=CHAT_ID,
            text=f"<b>Análise automática de jogos:</b>\n\n{final}",
            parse_mode="HTML"
        )

    except Exception as e:
        await bot.send_message(chat_id=CHAT_ID, text=f"❌ Erro ao obter partidas: {e}")async def main():  # Função principal
    # Executa o teste imediatamente
    await analisar_partidas()

    tz = pytz.timezone('America/Sao_Paulo')
    scheduler = AsyncIOScheduler(timezone=tz)

    # Horários automáticos
    scheduler.add_job(analisar_partidas, 'cron', hour=6, minute=0)
    scheduler.add_job(analisar_partidas, 'cron', hour=18, minute=0)
    scheduler.start()

    # Mantém o bot rodando continuamente
    while True:
        await asyncio.sleep(60)


if __name__ == "__main__":
    asyncio.run(main())

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
    # Simulação temporária de partidas (modo teste)
    partidas = [
        {"titulo": "Brasil x Argentina", "competicao": "Amistoso Internacional", "data": "2025-10-22", "video_url": "https://exemplo.com"}
    ]

    if not partidas:
        await bot.send_message(chat_id=CHAT_ID, text="⚠ Nenhuma partida encontrada no momento.")
        return

    mensagens = []
    for jogo in partidas[:5]:
        titulo = jogo.get("titulo", "Partida sem título")
        competicao = jogo.get("competicao", "Desconhecida")
        data = jogo.get("data", "Sem data")
        video_url = jogo.get("video_url", "")

        mensagens.append(f"🏆 <b>{competicao}</b>\n⚽ {titulo}\n📅 {data}\n🎥 <a href='{video_url}'>Ver detalhes</a>")

    final = "\n\n".join(mensagens)
    await bot.send_message(chat_id=CHAT_ID, text=f"📊 <b>Análise automática de jogos</b>\n\n{final}", parse_mode="HTML")

except Exception as e:
    await bot.send_message(chat_id=CHAT_ID, text=f"❌ Erro ao obter partidas: {e}")

            mensagens.append(
                f"🏆 <b>{competicao}</b>\n⚽ {titulo}\n🕒 {data}\n🔗 <a href='{video_url}'>Ver detalhes</a>"
            )

        mensagem_final = "\n\n".join(mensagens)
        await bot.send_message(chat_id=CHAT_ID, text=f"📊 <b>Análise automática de jogos:</b>\n\n{mensagem_final}", parse_mode=ParseMode.HTML)

    except Exception as e:
        await bot.send_message(chat_id=CHAT_ID, text=f"❌ Erro ao obter partidas: {e}")

async def main():  # Função principal
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

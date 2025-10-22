import asyncio
import requests
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from telegram import Bot

# ==============================
# CONFIGURAÇÕES DO BOT
# ==============================
API_KEY = "ab6e5b1b2e0442c99c5d0a627730b33f"
BOT_TOKEN = ""8444936746:AAE5JjO5vhrqb-HL7wWr-8kGpOjaCQybmgE
CHAT_ID = "5245918045"

bot = Bot(token=BOT_TOKEN)

# ==============================
# FUNÇÃO PARA ANALISAR PARTIDAS
# ==============================
async def analisar_partidas():
    try:
        url = f"https://www.scorebat.com/video-api/v3/feed/?token={API_KEY}"
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
        await bot.send_message(chat_id=CHAT_ID, text=f"❌ Erro ao obter partidas: {e}")


# ==============================
# LOOP PRINCIPAL
# ==============================
async def main():
    scheduler = AsyncIOScheduler()

    # Horários automáticos (exemplo: 06h e 18h)
    scheduler.add_job(analisar_partidas, 'cron', hour=6, minute=0)
    scheduler.add_job(analisar_partidas, 'cron', hour=18, minute=0)

    scheduler.start()

    # Mantém o bot rodando continuamente
    while True:
        await asyncio.sleep(60)


# ==============================
# EXECUÇÃO DO BOT
# ==============================
if __name__ == "__main__":
    asyncio.run(main())

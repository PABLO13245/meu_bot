import asyncio
import requests
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from telegram import Bot

# ==============================
# CONFIGURAÇÕES DO BOT
# ==============================
API_KEY = "eac4bfa1690903a2c6328dd2bb4a94e"
BOT_TOKEN = "8444936746:AAE5JjO5vhrqb-HL7wWr-8kGpOjaCQybmgE"
CHAT_ID = "5245918045"

bot = Bot(token=BOT_TOKEN)

# NOVA FUNÇÃO PARA BUSCAR PARTIDAS (sem chave de API)
async def analisa_partidas():
    import requests
    from datetime import date

    try:
        hoje = date.today()
        url = f"https://www.thesportsdb.com/api/v1/json/3/eventsday.php?d={hoje}&s=Soccer"
        resposta = requests.get(url, timeout=15)
        dados = resposta.json()
        partidas = dados.get("events", [])

        if not partidas:
            await bot.send_message(CHAT_ID, text="⚠ Nenhuma partida encontrada no momento.")
            return

        mensagens = []
        for jogo in partidas[:5]:  # mostra só 7 jogos pra não lotar o chat
            time_casa = jogo.get("strHomeTeam", "Desconhecido")
            time_fora = jogo.get("strAwayTeam", "Desconhecido")
            horario = jogo.get("strTime", "00:00")
            liga = jogo.get("strLeague", "Desconhecida")

            mensagens.append(f"⚽ {time_casa} x {time_fora}\n🏆 {liga}\n🕒 {horario}\n")

        for msg in mensagens:
            await bot.send_message(CHAT_ID, text=msg)

    except Exception as e:
        await bot.send_message(CHAT_ID, text=f"❌ Erro ao buscar partidas: {e}")


# ==============================
# LOOP PRINCIPAL
# ==============================
async def main():
    scheduler = AsyncIOScheduler()

    # Horários automáticos (exemplo: 06h e 18h)
    scheduler.add_job(analisa_partidas, 'cron', hour=6, minute=0)
    scheduler.add_job(analisa_partidas, 'cron', hour=18, minute=0)

    scheduler.start()

    # Mantém o bot rodando continuamente
    while True:
        await asyncio.sleep(60)


# ==============================
# EXECUÇÃO DO BOT
# ==============================
if __name__ == "__main__":
    asyncio.run(analisa_partidas())  # executa o teste manual
    asyncio.run(main())               # inicia o loop automático

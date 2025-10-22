import asyncio
import requests
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from telegram import Bot
from datetime import date
import random

# ==============================
# CONFIGURAÇÕES DO BOT
# ==============================
API_KEY = "eac4bfa1690903a2c6328dd2bb4a94e"
BOT_TOKEN = "8444936746:AAE5JjO5vhrqb-HL7wWr-8kGpOjaCQybmgE"
CHAT_ID = "5245918045"

bot = Bot(token=BOT_TOKEN)

# ==============================
# FUNÇÃO PRINCIPAL DE ANÁLISE
# ==============================
async def analisa_partidas():
    try:
        hoje = date.today()
        url = f"https://www.thesportsdb.com/api/v1/json/3/eventsday.php?d={hoje}&s=Soccer"
        resposta = requests.get(url, timeout=15)
        dados = resposta.json()
        partidas = dados.get("events", [])

        if not partidas:
            await bot.send_message(CHAT_ID, text="⚠ Nenhuma partida encontrada no momento.")
            return

        mensagens = ["📊 Análise Automática de Futebol – Jogos do Dia ⚽\n"]

        for jogo in partidas[:8]:  # Mostra 8 jogos do dia
            time_casa = jogo.get("strHomeTeam", "Desconhecido")
            time_fora = jogo.get("strAwayTeam", "Desconhecido")
            horario = jogo.get("strTime", "00:00")
            liga = jogo.get("strLeague", "Desconhecida")

            # Simulação de sugestões automáticas
            opcoes_gol = ["+1.5 Gols", "+2.5 Gols", "Ambas Marcam", "Menos de 3.5 Gols"]
            opcoes_esc = ["+8 Escanteios", "+9 Escanteios", "Mais de 10 Escanteios"]
            opcoes_vit = [
                f"Vitória do {time_casa}",
                f"Vitória do {time_fora}",
                "Empate Anula",
                "Chance Dupla"
            ]

            sugestao_gol = random.choice(opcoes_gol)
            sugestao_esc = random.choice(opcoes_esc)
            sugestao_vit = random.choice(opcoes_vit)

            mensagens.append(
                f"🏆 {liga}\n"
                f"⚔ {time_casa} vs {time_fora}\n"
                f"🕒 {horario}\n\n"
                f"💡 Sugestões de Aposta:\n"
                f"   • {sugestao_gol}\n"
                f"   • {sugestao_esc}\n"
                f"   • {sugestao_vit}\n"
                "───────────────────────────────"
            )

        await bot.send_message(CHAT_ID, text="\n\n".join(mensagens), parse_mode="Markdown")

    except Exception as e:
        await bot.send_message(CHAT_ID, text=f"❌ Erro ao buscar partidas: {e}")


# ==============================
# LOOP PRINCIPAL DO BOT
# ==============================
async def main():
    scheduler = AsyncIOScheduler()

    # Roda automaticamente às 06:00 e 16:00
    scheduler.add_job(analisa_partidas, 'cron', hour=6, minute=0)
    scheduler.add_job(analisa_partidas, 'cron', hour=16, minute=0)
    scheduler.start()

    print("✅ Bot de análise iniciado! Enviará jogos às 06:00 e 16:00 (horário de Brasília).")

    # Mantém o bot ativo
    while True:
        await asyncio.sleep(60)


# ==============================
# EXECUÇÃO DO BOT
# ==============================
if __name__ == "__main__":
    asyncio.run(analisa_partidas())  # Envia UMA análise agora (teste)

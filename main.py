import asyncio
import requests
from datetime import date, datetime
from telegram import Bot
from apscheduler.schedulers.asyncio import AsyncIOScheduler
import random
import pytz

# ==============================
# CONFIGURAÇÕES DO BOT
# ==============================
BOT_TOKEN = "8444936746:AAE5JjO5vhrqb-HL7wWr-8kGpOjaCQybmgE"
CHAT_ID = "5245918045"
bot = Bot(token=BOT_TOKEN)
tz = pytz.timezone("America/Sao_Paulo")

# ==============================
# FUNÇÃO PARA PEGAR BANDEIRA
# ==============================
def get_flag(team_name):
    flags = {
        "Brazil": "🇧🇷", "England": "🏴", "Spain": "🇪🇸", "France": "🇫🇷",
        "Germany": "🇩🇪", "Italy": "🇮🇹", "Portugal": "🇵🇹", "Argentina": "🇦🇷",
        "USA": "🇺🇸", "Japan": "🇯🇵", "Mexico": "🇲🇽", "Netherlands": "🇳🇱",
        "Turkey": "🇹🇷", "Chile": "🇨🇱", "Uruguay": "🇺🇾"
    }
    for country, flag in flags.items():
        if country.lower() in team_name.lower():
            return flag
    return "⚽"

# ==============================
# FUNÇÃO PRINCIPAL DE ANÁLISE
# ==============================
async def analisa_partidas():
    try:
        hoje = date.today()
        data_formatada = datetime.now(tz).strftime("%d/%m/%Y")
        url = f"https://www.thesportsdb.com/api/v1/json/3/eventsday.php?d={hoje}&s=Soccer"
        resposta = requests.get(url, timeout=15)
        dados = resposta.json()
        partidas = dados.get("events", [])

        if not partidas:
            await bot.send_message(CHAT_ID, text="⚠ Nenhuma partida encontrada no momento.")
            return

        texto_final = f"📅 Análises de Hoje — {data_formatada}\n"
        texto_final += "🔥 ANÁLISE VIP FUTEBOL 🔥\n\n"
        texto_final += "As 8 melhores partidas com oportunidades de aposta:\n\n"

        for jogo in partidas[:8]:
            time_casa = jogo.get("strHomeTeam", "Desconhecido")
            time_fora = jogo.get("strAwayTeam", "Desconhecido")
            horario = jogo.get("strTime", "00:00")
            liga = jogo.get("strLeague", "Desconhecida")

            flag_casa = get_flag(time_casa)
            flag_fora = get_flag(time_fora)

            aposta = random.choice([
                "✅ Vitória provável do time da casa",
                "⚽ Mais de 2.5 gols",
                "🔺 Mais de 8.5 escanteios",
                "🚨 Ambas as equipes marcam",
                "💪 Vitória provável do visitante",
                "🎯 Mais de 1.5 gols no 1º tempo",
                "🔥 +10 escanteios totais"
            ])

            texto_final += f"{flag_casa} {time_casa} x {time_fora} {flag_fora}\n"
            texto_final += f"🏆 {liga}\n🕒 {horario}\n🎯 {aposta}\n\n"

        texto_final += "📊 Gerado automaticamente pelo Bot Análise Futebol."

        await bot.send_message(CHAT_ID, text=texto_final, parse_mode="Markdown")

    except Exception as e:
        await bot.send_message(CHAT_ID, text=f"❌ Erro ao buscar partidas: {e}")

# ==============================
# LOOP PRINCIPAL E AGENDAMENTO
# ==============================
async def main():
    scheduler = AsyncIOScheduler(timezone=tz)

    from datetime import datetime, timedelta

# Agendamentos automáticos
scheduler.add_job(analisa_partidas, "cron", hour=6, minute=0)
scheduler.add_job(analisa_partidas, "cron", hour=16, minute=0)

# Agendamento especial (somente hoje às 18h)
agora = datetime.now(tz)
if agora.hour < 18:
    scheduler.add_job(analisa_partidas, "date", run_date=agora.replace(hour=18, minute=0, second=0))

scheduler.start()

    print("✅ Bot rodando 24h. Enviará análises automáticas às 06:00 e 16:00 (horário de Brasília).")

    while True:
        await asyncio.sleep(60)

# ==============================
# EXECUÇÃO
# ==============================
if _name_ == "_main_":
    asyncio.run(analisa_partidas())  # Teste imediato
    asyncio.run(main())              # Inicia agendamentos
    print("✅ Bot rodando 24h. Enviará análises automáticas às 06:00 e 16:00 (horário de Brasília).")

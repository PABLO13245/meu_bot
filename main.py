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
    get_flag_emoji
)

# CONFIGURAÇÕES via ENV
API_TOKEN = os.getenv("API_TOKEN")            # SportMonks token
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")  # Telegram bot token
CHAT_ID = os.getenv("CHAT_ID")                # chat id (string)
TZ = pytz.timezone("America/Sao_Paulo")
# O bot é inicializado aqui para uso em funções assíncronas
bot = Bot(token=TELEGRAM_TOKEN)

# Quantidade de partidas por envio (limite de TOP Oportunidades)
TOP_QTY = 7

# Função build_message agora aceita fixtures já ordenados
async def build_message(fixtures, api_token, qty=7):
    now = datetime.now(TZ)
    
    # 1. ORDENAR PELA CONFIANÇA (decide_best_market)
    analyzed_fixtures = []
    
    # Vamos rodar a análise antes de construir a mensagem para obter a confiança
    for f in fixtures:
        participants = f.get("participants", [])
        if len(participants) < 2:
            continue
        
        home_id = participants[0].get("id")
        away_id = participants[1].get("id")

        # Chama a corrotina (necessita 'await')
        # CORREÇÃO: Ajuste para última partida (last=1) para simulação mais rápida
        hm = await compute_team_metrics(api_token, home_id, last=5) 
        am = await compute_team_metrics(api_token, away_id, last=5)

        suggestion, confidence = decide_best_market(hm, am)
        
        # Adiciona sugestão e confiança ao dicionário
        f['suggestion'] = suggestion
        f['confidence'] = confidence
        analyzed_fixtures.append(f)

    # Ordena pelo campo 'confidence' (do maior para o menor)
    # Se a confiança for igual (como na simulação), usa o horário de início como desempate
    analyzed_fixtures.sort(key=lambda x: (x.get('confidence', 0), x.get("starting_at", "")), reverse=True)


    # 2. CONSTRUIR MENSAGEM (apenas com o TOP_QTY)
    
    header = (
        f"📅 Análises — {now.strftime('%d/%m/%Y')} (JOGOS DE HOJE)\n"
        f"⏱ Atualizado — {now.strftime('%H:%M')} (BRT)\n\n"
        f"🔥 Top {qty} Oportunidades Encontradas 🔥\n\n"
    )
    lines = [header]

    count = 0
    
    # Itera sobre a lista JÁ ORDENADA
    for f in analyzed_fixtures:
        if count >= qty:
            break
            
        participants = f.get("participants", [])
        
        home = participants[0].get("name", "Casa")
        away = participants[1].get("name", "Fora")
        
        # Obtendo bandeiras e nome da liga/país
        league_data = f.get("league", {})
        league_name = league_data.get("name", "Desconhecida")
        
        # CORREÇÃO: Usando country_code para o país da liga
        league_country_code = league_data.get("country", {}).get("code", "xx")
        league_flag = get_flag_emoji(league_country_code)

        home_country_code = participants[0].get("country", {}).get("code", "xx")
        away_country_code = participants[1].get("country", {}).get("code", "xx")
        
        home_flag = get_flag_emoji(home_country_code)
        away_flag = get_flag_emoji(away_country_code)

        kickoff_local = kickoff_time_local(f, TZ)
        
        suggestion = f['suggestion']
        confidence = f['confidence']

        part = (
            f"{count + 1}. ⚽ {home_flag} {home} x {away} {away_flag}\n"
            f"🏆 {league_flag} {league_name}  •  🕒 {kickoff_local}\n"
            f"🎯 Sugestão principal: {suggestion}\n"
            f"💹 Confiança: {confidence}%\n"
            "──────────────────────────────\n"
        )
        lines.append(part)
        count += 1

    if count == 0:
        lines.append("⚠ Nenhuma partida TOP 7 encontrada para hoje nas ligas selecionadas.\n")

    footer = "\n🔎 Obs: análise baseada em últimos 5 jogos. Use responsabilidade."
    lines.append(footer)
    # return single string (Markdown)
    return "\n".join(lines)


async def run_analysis_send(qtd=TOP_QTY):
    # build date range: APENAS HOJE
    now = datetime.now(timezone.utc)
    # Start e End são a mesma data para filtrar apenas hoje
    start_str = now.strftime("%Y-%m-%d")
    
    # Flag para debug
    print(f"DEBUG: Buscando jogos de {start_str} nas Ligas Filtradas.")

    try:
        # CORREÇÃO: Passando apenas a data de início (start_str)
        fixtures = await fetch_upcoming_fixtures(API_TOKEN, start_str, per_page=100)
        
        # Filtro final para garantir que apenas jogos de HOJE passem
        now_local = datetime.now(TZ).date()
        
        filtered_fixtures = [
            f for f in fixtures 
            if kickoff_time_local(f, TZ, return_datetime=True).date() == now_local
        ]
        
        if not filtered_fixtures:
            await bot.send_message(chat_id=CHAT_ID, text=f"⚠ Nenhuma partida agendada para hoje ({now_local.strftime('%d/%m')}) nas ligas filtradas.")
            return
            
        # Chamada assíncrona para build_message, que agora faz a análise e ordenação
        message = await build_message(filtered_fixtures, API_TOKEN, qtd)
        
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
    print("Agendador iniciado: 06:00, 16:00, 19:00 BRT")

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

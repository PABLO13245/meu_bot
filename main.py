import os
import asyncio
from datetime import datetime, timedelta, timezone
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from telegram import Bot
import pytz

# Importa as funções de análise do arquivo analysis.py
from analysis import (
    fetch_upcoming_fixtures,
    compute_team_metrics,
    decide_best_market,
    kickoff_time_local
)

# ========== VARIÁVEIS DE AMBIENTE ==========
# Estas variáveis devem ser definidas no seu ambiente (ex: arquivo .env)
API_TOKEN = os.getenv("API_TOKEN")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
TZ = pytz.timezone("America/Sao_Paulo")
bot = Bot(token=TELEGRAM_TOKEN)
TOP_QTY = 7 # Quantidade de melhores oportunidades para enviar

# ===================================
# CONSTRUÇÃO DA MENSAGEM COM FILTRO DE CONFIANÇA
# ===================================
async def build_message(fixtures, api_token, qty=TOP_QTY):
    now = datetime.now(TZ)
    header = (
        f"📅 Análises — {now.strftime('%d/%m/%Y')}\n"
        f"⏱ Atualizado — {now.strftime('%H:%M')} (BRT)\n\n"
        f"🔥 Top {qty} Oportunidades (48h) 🔥\n\n"
    )
    lines = [header]
    
    analyzed_fixtures = []

    # 1. Processar e Analisar TODOS os jogos
    for f in fixtures:
        participants = f.get("participants", [])
        if len(participants) < 2:
            continue
            
        try:
            home = participants[0].get("name", "Casa")
            away = participants[1].get("name", "Fora")
            
            # Chama a função SIMULADA de métricas
            hm = await compute_team_metrics(api_token, participants[0].get("id"))
            am = await compute_team_metrics(api_token, participants[1].get("id"))
            suggestion, confidence = decide_best_market(hm, am)
            
            # Armazena os dados processados
            analyzed_fixtures.append({
                "home": home,
                "away": away,
                "league_name": f.get('league', {}).get('name', 'Desconhecida'),
                "kickoff_local": kickoff_time_local(f, TZ),
                "suggestion": suggestion,
                "confidence": confidence,
                "starting_at": f.get("starting_at", "") # Mantém para ordenação secundária, se necessário
            })
            
        except Exception as e:
            print(f"Erro ao analisar fixture {f.get('id', 'N/A')}: {e}")
            continue

    # 2. Ordenar pela CONFIANÇA (do maior para o menor)
    # Garante que as 'melhores' oportunidades (maior confiança) sejam selecionadas.
    analyzed_fixtures.sort(key=lambda x: x['confidence'], reverse=True)

    # 3. Selecionar o Top QTY e formatar a mensagem
    for data in analyzed_fixtures[:qty]:
        line = (
            f"⚽ {data['home']} x {data['away']}\n"
            f"🏆 {data['league_name']}  •  🕒 {data['kickoff_local']}\n"
            f"🎯 Sugestão: {data['suggestion']}\n"
            f"💹 Confiança: {data['confidence']}%\n"
            "──────────────────────────────\n"
        )
        lines.append(line)
        
    if not analyzed_fixtures:
        lines.append("Nenhuma oportunidade encontrada no período analisado.")

    lines.append("🔎 Use responsabilidade.")
    return "\n".join(lines)

# ===================================
# EXECUTAR ANÁLISE E ENVIAR
# ===================================
async def run_analysis_send(qtd=TOP_QTY):
    # O Sportmonks requer que as datas estejam no formato UTC
    now_utc = datetime.now(timezone.utc)
    start_str = now_utc.strftime("%Y-%m-%d")
    end_str = (now_utc + timedelta(hours=48)).strftime("%Y-%m-%d")
    
    print(f"\nIniciando análise para o período: {start_str} a {end_str} (UTC)")
    
    try:
        # Busca todos os jogos no período (Filtro da API)
        fixtures = await fetch_upcoming_fixtures(API_TOKEN, start_str, end_str)
        
        # A ordenação por horário não é mais necessária aqui,
        # pois o filtro de confiança a substituirá no build_message.
        
        message = await build_message(fixtures, API_TOKEN, qtd)
        await bot.send_message(chat_id=CHAT_ID, text=message, parse_mode="Markdown")
        print("✅ Mensagem enviada com sucesso para o Telegram.")
        
    except Exception as e:
        print(f"❌ Erro run_analysis_send: {e}")
        try:
            # Tenta enviar a mensagem de erro para o Telegram
            await bot.send_message(chat_id=CHAT_ID, text=f"❌ Erro na análise: {type(e)._name_} - {e}")
        except Exception:
            pass # Falha ao enviar a mensagem de erro

# ===================================
# AGENDADOR
# ===================================
def start_scheduler():
    scheduler = AsyncIOScheduler(timezone=TZ)
    # Cria uma tarefa assíncrona para cada agendamento
    scheduler.add_job(lambda: asyncio.create_task(run_analysis_send(TOP_QTY)), "cron", hour=6, minute=0)
    scheduler.add_job(lambda: asyncio.create_task(run_analysis_send(TOP_QTY)), "cron", hour=16, minute=0)
    scheduler.add_job(lambda: asyncio.create_task(run_analysis_send(TOP_QTY)), "cron", hour=19, minute=0)
    scheduler.start()
    print(f"✅ Scheduler iniciado: 06:00, 16:00, 19:00 ({TZ.zone})")

# ===================================
# FUNÇÃO PRINCIPAL
# ===================================
async def main():
    start_scheduler()
    
    # Executa uma análise imediatamente se a variável de ambiente TEST_NOW for "1"
    if os.getenv("TEST_NOW", "0") == "1":
        print("Modo de teste imediato ativado.")
        await run_analysis_send(TOP_QTY)
        
    # Mantém o loop de eventos ativo para o agendador e o Telegram
    await asyncio.Event().wait() 

if __name__ == "__main__":
    # Verifica se as variáveis de ambiente necessárias estão definidas
    missing = []
    if not API_TOKEN:
        missing.append("API_TOKEN")
    if not TELEGRAM_TOKEN:
        missing.append("TELEGRAM_TOKEN")
    if not CHAT_ID:
        missing.append("CHAT_ID")
        
    if missing:
        print("❌ Variáveis de ambiente ausentes:", missing)
        import sys; sys.exit(1)
        
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nBot interrompido manualmente.")

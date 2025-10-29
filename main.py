import os
import asyncio
from datetime import datetime, timedelta
import pytz
from telegram import Bot
from apscheduler.schedulers.asyncio import AsyncIOScheduler
# CORREÇÃO CRÍTICA: Importação explícita de TODOS os tipos usados
from typing import List, Dict, Any, Optional 

# Importa TODAS as funções do analysis.py (API, análise e utilidades)
from analysis import (
    fetch_upcoming_fixtures,
    compute_team_metrics,
    decide_best_market, 
    kickoff_time_local,
    get_flag_emoji
)

# CONFIGURAÇÕES via ENV (Valores default usados se a ENV falhar)
# SUBSTITUA ESTES VALORES ANTES DE RODAR
API_TOKEN = os.getenv("API_TOKEN", "YOUR_FOOTBALLDATA_API_TOKEN") 
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "YOUR_TELEGRAM_TOKEN") 
CHAT_ID = os.getenv("CHAT_ID", "YOUR_CHAT_ID")                     
TZ = pytz.timezone("America/Sao_Paulo")

# Bot do Telegram
bot = Bot(token=TELEGRAM_TOKEN)

# CONFIGURAÇÕES DE FILTRO
HOURS_LIMIT = 24 
TOP_QTY = 4      
MIN_CONFIDENCE = 50 

# Margem de tempo de segurança
MINUTES_BEFORE_KICKOFF = 2 

# NOVO VALOR: Aumentado para 4.5 segundos para respeitar o Rate Limit da API Free
SLEEP_TIME_BETWEEN_ANALYSIS = 4.5 

# ----------------------------------------------------------------------
# FUNÇÕES DE ANÁLISE E MENSAGEM
# ----------------------------------------------------------------------

async def analyze_and_rate_fixture(fixture: Dict[str, Any], api_token: str) -> Optional[Dict[str, Any]]:
    """Analisa uma única partida, seleciona a MELHOR SUGESTÃO e retorna o objeto da partida."""
    
    participants = fixture.get("participants", [])
    if len(participants) < 2:
        return None
    
    home_id = next((p["id"] for p in participants if p["meta"]["location"] == "home"), None)
    away_id = next((p["id"] for p in participants if p["meta"]["location"] == "away"), None)

    if not home_id or not away_id:
        return None
    
    # Análise de Métricas
    hm, am = await asyncio.gather(
        compute_team_metrics(api_token, home_id, last=5), 
        compute_team_metrics(api_token, away_id, last=5)
    )

    suggestion, confidence = decide_best_market(hm, am)
    
    # Filtro: Apenas sinais fortes (>= MIN_CONFIDENCE)
    if confidence < MIN_CONFIDENCE:
        return None
    
    fixture['suggestion'] = suggestion
    fixture['confidence'] = confidence
    return fixture


async def build_top_n_message(top_fixtures: List[Dict[str, Any]]) -> str:
    """Constrói a mensagem final consolidada para os TOP N jogos."""
    
    now = datetime.now(TZ)
    
    header = (
        f"🚨 *ALERTA DE OPORTUNIDADES (TOP {len(top_fixtures)}) – {now.strftime('%d/%m/%Y %H:%M')}*\n"
        f"🔎 *Próximas {HOURS_LIMIT} Horas*\n"
        f"──────────────────────────────\n"
    )
    
    message_parts = []
    
    for i, f in enumerate(top_fixtures):
        participants = f.get("participants", [])
        home = next((p for p in participants if p["meta"]["location"] == "home"), {})
        away = next((p for p in participants if p["meta"]["location"] == "away"), {})

        league_data = f.get("league", {})
        league_name = league_data.get("name", "Desconhecida")
        league_country_code = league_data.get("country", {}).get("code", "xx")
        
        kickoff_local = kickoff_time_local(f, TZ)
        league_flag = get_flag_emoji(league_country_code)
        
        home_name = home.get("name", "Casa")
        away_name = away.get("name", "Fora")
        
        suggestion = f.get('suggestion', 'N/A')
        confidence = f.get('confidence', 0)

        part = (
            f"{i+1}.** ⚽ *{home_name}* x *{away_name}*\n"
            f"   🏆 {league_flag} {league_name}\n"
            f"   🕒 {kickoff_local} (BRT)\n"
            f"   🔥 *Aposta:* {suggestion}\n"
            f"   📊 *Confiança:* {confidence}%\n"
        )
        message_parts.append(part)
    
    footer = "\n_Aposte com responsabilidade. Análise baseada em performance histórica._"
    
    return header + "\n".join(message_parts) + footer


async def run_analysis_send():
    """Executa o ciclo completo de busca, filtro, análise e ENVIO DAS MELHORES APOSTAS."""
    
    if API_TOKEN == "YOUR_FOOTBALLDATA_API_TOKEN":
        print("\n🚨 ERRO: Token da API (football-data.org) não configurado. Abortando execução.")
        return 
    
    if CHAT_ID == "YOUR_CHAT_ID" or TELEGRAM_TOKEN == "YOUR_TELEGRAM_TOKEN":
        print("\n🚨 ERRO: CHAT_ID ou TELEGRAM_TOKEN não configurados. A análise será executada, mas a mensagem não será enviada.")
        
    # 1. Definir o range de tempo (24 HORAS)
    now_local = datetime.now(TZ)
    time_limit_24h = now_local + timedelta(hours=HOURS_LIMIT)
    
    print(f"DEBUG: Buscando jogos futuros. Limite de {HOURS_LIMIT}h: {time_limit_24h.strftime('%d/%m %H:%M')} (BRT)")

    try:
        # 2. Busca fixtures 
        fixtures = await fetch_upcoming_fixtures(API_TOKEN, per_page=200) 
        
        if not fixtures:
            return
        
        # 3. FILTRO TEMPORAL E DE INÍCIO
        upcoming_fixtures: List[Dict[str, Any]] = []
        time_threshold = now_local + timedelta(minutes=MINUTES_BEFORE_KICKOFF) 

        for f in fixtures:
            kickoff_dt = kickoff_time_local(f, TZ, return_datetime=True)
            
            if time_threshold < kickoff_dt <= time_limit_24h:
                upcoming_fixtures.append(f)

        print(f"DEBUG: Jogos dentro de {HOURS_LIMIT}h e não iniciados (restantes): {len(upcoming_fixtures)}.")
        
        if not upcoming_fixtures:
            return
            
        # 4. Analisa os jogos sequencialmente, com tempo de espera
        analyzed_fixtures: List[Dict[str, Any]] = []

        for f in upcoming_fixtures:
            # NOVO: Tempo de espera para evitar Rate Limit
            await asyncio.sleep(SLEEP_TIME_BETWEEN_ANALYSIS) 

            result = await analyze_and_rate_fixture(f, API_TOKEN)
            if result is not None:
                analyzed_fixtures.append(result)
        
        if not analyzed_fixtures:
            message = f"⚠ Nenhuma partida TOP encontrada nas próximas {HOURS_LIMIT}h, com confiança acima de {MIN_CONFIDENCE}%."
            if CHAT_ID != "YOUR_CHAT_ID":
                await bot.send_message(chat_id=CHAT_ID, text=message)
            else:
                print(message)
            return

        # 5. Ordena pela confiança (do maior para o menor)
        analyzed_fixtures.sort(key=lambda x: (x.get('confidence', 0), x.get("starting_at", "")), reverse=True)
        
        # 6. Pega APENAS os TOP N jogos (os 4 primeiros da lista)
        top_fixtures = analyzed_fixtures[:TOP_QTY]

        # 7. Constrói a mensagem e envia
        message = await build_top_n_message(top_fixtures)
        
        if CHAT_ID != "YOUR_CHAT_ID" and TELEGRAM_TOKEN != "YOUR_TELEGRAM_TOKEN":
            await bot.send_message(chat_id=CHAT_ID, text=message, parse_mode="Markdown")
        else:
            print(f"--- MENSAGEM TOP {len(top_fixtures)} PRONTA (NÃO ENVIADA) ---")
            print(message)
            print("-----------------------------------")
        
    except Exception as e:
        print(f"❌ Erro em run_analysis_send: {e}")
        try:
            if CHAT_ID != "YOUR_CHAT_ID":
                 await bot.send_message(chat_id=CHAT_ID, text=f"❌ Erro na análise. Verifique os logs.")
        except Exception:
            pass
            
# ----------------------------------------------------------------------
# SCHEDULER E EXECUÇÃO PRINCIPAL 
# ----------------------------------------------------------------------

def start_scheduler():
    """Inicia o agendador de tarefas."""
    scheduler = AsyncIOScheduler(timezone=TZ)
    
    # Horários de execução (BRT)
    scheduler.add_job(lambda: asyncio.create_task(run_analysis_send()), "cron", hour=0, minute=0) 
    scheduler.add_job(lambda: asyncio.create_task(run_analysis_send()), "cron", hour=6, minute=0) 
    scheduler.add_job(lambda: asyncio.create_task(run_analysis_send()), "cron", hour=16, minute=0) 
    scheduler.add_job(lambda: asyncio.create_task(run_analysis_send()), "cron", hour=19, minute=0) 
    
    scheduler.start()
    print("✅ Agendador iniciado para 06:00, 12:00, e 19:00 (BRT).")

async def main():
    """Função principal que mantém o bot rodando."""
    
    missing = []
    if API_TOKEN == "YOUR_FOOTBALLDATA_API_TOKEN": missing.append("API_TOKEN") 
    if TELEGRAM_TOKEN == "YOUR_TELEGRAM_TOKEN": missing.append("TELEGRAM_TOKEN")
    if CHAT_ID == "YOUR_CHAT_ID": missing.append("CHAT_ID")
        
    if missing:
        print("🚨 ATENÇÃO: Variáveis de ambiente ausentes ou com valor default:", missing)

    start_scheduler()
    
    if os.getenv("TEST_NOW", "0") == "1":
        print("TEST_NOW=1 -> enviando teste imediato...")
        await run_analysis_send()
        
    try:
        while True:
            await asyncio.sleep(60 * 60) 
    except Exception as e:
        print(f"Erro no loop principal: {e}")
        
if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Bot interrompido manualmente.")

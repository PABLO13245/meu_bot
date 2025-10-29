import os
import asyncio
from datetime import datetime, timedelta
import pytz
from telegram import Bot
from apscheduler.schedulers.asyncio import AsyncIOScheduler

# Importa TODAS as funções do analysis.py (API, análise e utilidades)
from analysis import (
    fetch_upcoming_fixtures,
    compute_team_metrics,
    decide_best_market, # Esta função agora retorna o melhor de todos os mercados
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

# Filtro mínimo de confiança (para QUALQUER aposta ser considerada)
# Aumentado para 65% para garantir um "TOP 1" de alta qualidade
MIN_CONFIDENCE = 65 

# Margem de tempo de segurança para evitar pegar jogos que já começaram ou começarão em segundos.
MINUTES_BEFORE_KICKOFF = 2 

# ----------------------------------------------------------------------
# FUNÇÕES DE ANÁLISE E MENSAGEM
# ----------------------------------------------------------------------

async def analyze_and_rate_fixture(fixture, api_token):
    """Analisa uma única partida, seleciona a MELHOR SUGESTÃO e retorna o objeto da partida."""
    
    participants = fixture.get("participants", [])
    if len(participants) < 2:
        return None
    
    # Encontra IDs dos times (com base na localização 'home'/'away')
    home_id = next((p["id"] for p in participants if p["meta"]["location"] == "home"), None)
    away_id = next((p["id"] for p in participants if p["meta"]["location"] == "away"), None)

    if not home_id or not away_id:
        return None
    
    # Análise de Métricas
    hm, am = await asyncio.gather(
        compute_team_metrics(api_token, home_id, last=5), 
        compute_team_metrics(api_token, away_id, last=5)
    )

    # decide_best_market: Retorna a melhor sugestão entre todos os mercados (Gols FT, 1X2, BTTS, HT, Corners)
    suggestion, confidence = decide_best_market(hm, am)
    
    # Filtro: Apenas sinais fortes (>= MIN_CONFIDENCE)
    if confidence < MIN_CONFIDENCE:
        log_msg = f"DEBUG: Jogo ignorado por baixa confiança ({confidence}%)"
        if confidence == 0:
             log_msg += " (FALHA DE DADOS HISTÓRICOS)"
        print(log_msg)
        return None
    
    fixture['suggestion'] = suggestion
    fixture['confidence'] = confidence
    return fixture


async def build_single_best_message(best_fixture):
    """Constrói a mensagem final APENAS para a melhor aposta."""
    
    now = datetime.now(TZ)
    
    header = (
        f"🚨 *ALERTA DE OPORTUNIDADE (TOP 1) – {now.strftime('%d/%m/%Y %H:%M')}*\n"
        f"──────────────────────────────\n"
    )
    
    f = best_fixture
    participants = f.get("participants", [])
    home = next((p for p in participants if p["meta"]["location"] == "home"), {})
    away = next((p for p in participants if p["meta"]["location"] == "away"), {})

    # Dados da partida
    league_data = f.get("league", {})
    league_name = league_data.get("name", "Desconhecida")
    # O código de país agora vem do mapeamento no analysis.py
    league_country_code = league_data.get("country", {}).get("code", "xx")
    
    kickoff_local = kickoff_time_local(f, TZ)
    
    # Emoji da bandeira da liga (País)
    league_flag = get_flag_emoji(league_country_code)
    
    home_name = home.get("name", "Casa")
    away_name = away.get("name", "Fora")
    
    suggestion = f.get('suggestion', 'N/A')
    confidence = f.get('confidence', 0)

    # Mensagem final focada na Aposta Única
    part = (
        f"⚽ *{home_name}* x *{away_name}*\n"
        f"🏆 {league_flag} {league_name}\n"
        f"🕒 Início: {kickoff_local} (BRT)\n\n"
        f"🔥 *MELHOR SUGESTÃO GERAL:*\n"
        f"   *{suggestion}*\n"
        f"📊 *Confiança:* {confidence}%\n"
        f"📅 Próximas 24h\n"
    )
    
    footer = "\n_Aposte com responsabilidade. Análise baseada em performance histórica._"
    
    return header + part + footer


async def run_analysis_send():
    """Executa o ciclo completo de busca, filtro, análise e ENVIO DA MELHOR APOSTA."""
    
    if API_TOKEN == "YOUR_FOOTBALLDATA_API_TOKEN":
        print("\n🚨 ERRO: Token da API (football-data.org) não configurado. Abortando execução.")
        return 
    
    if CHAT_ID == "YOUR_CHAT_ID" or TELEGRAM_TOKEN == "YOUR_TELEGRAM_TOKEN":
        print("\n🚨 ERRO: CHAT_ID ou TELEGRAM_TOKEN não configurados. A análise será executada, mas a mensagem não será enviada.")
        
    # 1. Definir o range de tempo (24H)
    now_local = datetime.now(TZ)
    time_limit_48h = now_local + timedelta(hours=24)
    
    print(f"DEBUG: Buscando jogos futuros. Limite de 48h: {time_limit_48h.strftime('%d/%m %H:%M')} (BRT)")

    try:
        # 2. Busca fixtures (já filtrando todas as ligas configuradas no analysis.py)
        fixtures = await fetch_upcoming_fixtures(API_TOKEN, per_page=200) 
        
        if not fixtures:
            if CHAT_ID != "YOUR_CHAT_ID":
                await bot.send_message(chat_id=CHAT_ID, text=f"⚠ A API não retornou jogos futuros para o período de análise.")
            return
        
        # 3. FILTRO TEMPORAL E DE INÍCIO
        upcoming_fixtures = []
        time_threshold = now_local + timedelta(minutes=MINUTES_BEFORE_KICKOFF) 

        for f in fixtures:
            kickoff_dt = kickoff_time_local(f, TZ, return_datetime=True)
            
            # Filtro de 48 horas e Filtro de JÁ COMEÇOU
            if time_threshold < kickoff_dt <= time_limit_48h:
                upcoming_fixtures.append(f)

        print(f"DEBUG: Jogos dentro de 48h e não iniciados (restantes): {len(upcoming_fixtures)}.")
        
        if not upcoming_fixtures:
            if CHAT_ID != "YOUR_CHAT_ID":
                await bot.send_message(chat_id=CHAT_ID, text=f"⚠ Nenhuma partida agendada para as próximas 48h que ainda não começou e/ou passou pelo filtro de tempo.")
            return
            
        # 4. Analisa todos os jogos em paralelo e encontra o melhor
        analysis_tasks = [analyze_and_rate_fixture(f, API_TOKEN) for f in upcoming_fixtures]
        
        # Executa a análise para todos os jogos e filtra os nulos (confiança < MIN_CONFIDENCE)
        analyzed_fixtures_raw = await asyncio.gather(*analysis_tasks)
        analyzed_fixtures = [f for f in analyzed_fixtures_raw if f is not None]

        if not analyzed_fixtures:
            message = f"⚠ Nenhuma partida TOP encontrada nas próximas 48h, com confiança acima de {MIN_CONFIDENCE}%."
            if CHAT_ID != "YOUR_CHAT_ID":
                await bot.send_message(chat_id=CHAT_ID, text=message)
            else:
                print(message)
            return

        # 5. Ordena pela confiança (do maior para o menor)
        analyzed_fixtures.sort(key=lambda x: (x.get('confidence', 0), x.get("starting_at", "")), reverse=True)
        
        # 6. Pega APENAS o melhor jogo (o primeiro da lista)
        best_fixture = analyzed_fixtures[0]

        # 7. Constrói a mensagem e envia
        message = await build_single_best_message(best_fixture)
        
        if CHAT_ID != "YOUR_CHAT_ID" and TELEGRAM_TOKEN != "YOUR_TELEGRAM_TOKEN":
             # Parse mode é Markdown
            await bot.send_message(chat_id=CHAT_ID, text=message, parse_mode="Markdown")
        else:
            print("--- MENSAGEM ÚNICA PRONTA (NÃO ENVIADA) ---")
            print(message)
            print("-----------------------------------")
        
    except Exception as e:
        # log and send minimal error
        print(f"❌ Erro em run_analysis_send: {e}")
        try:
            if CHAT_ID != "YOUR_CHAT_ID":
                 await bot.send_message(chat_id=CHAT_ID, text=f"❌ Erro na análise. Verifique os logs.")
        except Exception:
            pass
            
# ----------------------------------------------------------------------
# SCHEDULER E EXECUÇÃO PRINCIPAL (Mantido do original)
# ----------------------------------------------------------------------

def start_scheduler():
    """Inicia o agendador de tarefas."""
    scheduler = AsyncIOScheduler(timezone=TZ)
    
    # Horários de execução (BRT)
    scheduler.add_job(lambda: asyncio.create_task(run_analysis_send()), "cron", hour=0, minute=0) # Meia-noite
    scheduler.add_job(lambda: asyncio.create_task(run_analysis_send()), "cron", hour=6, minute=0) # Manhã
    scheduler.add_job(lambda: asyncio.create_task(run_analysis_send()), "cron", hour=16, minute=0) # Tarde
    scheduler.add_job(lambda: asyncio.create_task(run_analysis_send()), "cron", hour=19, minute=0) # Noite
    
    scheduler.start()
    print("✅ Agendador iniciado para 06:00, 12:00, e 19:00 (BRT).")

async def main():
    """Função principal que mantém o bot rodando."""
    
    # 1. Checagem de variáveis de ambiente
    missing = []
    if API_TOKEN == "YOUR_FOOTBALLDATA_API_TOKEN": missing.append("API_TOKEN") 
    if TELEGRAM_TOKEN == "YOUR_TELEGRAM_TOKEN": missing.append("TELEGRAM_TOKEN")
    if CHAT_ID == "YOUR_CHAT_ID": missing.append("CHAT_ID")
        
    if missing:
        print("🚨 ATENÇÃO: Variáveis de ambiente ausentes ou com valor default:", missing)
        print("O bot rodará o scheduler, mas não enviará mensagens até a configuração correta.")

    # 2. Inicia o agendador
    start_scheduler()
    
    # 3. Opção de teste imediato
    if os.getenv("TEST_NOW", "0") == "1":
        print("TEST_NOW=1 -> enviando teste imediato...")
        await run_analysis_send()
        
    # 4. Mantém o loop ativo (Keep Alive) - ESSENCIAL PARA O SCHEDULER
    try:
        # Dorme por 1 hora, mas o agendador continua rodando em background
        while True:
            await asyncio.sleep(60 * 60) 
    except Exception as e:
        print(f"Erro no loop principal: {e}")
        
if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Bot interrompido manualmente.")

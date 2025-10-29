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
    decide_best_market,
    kickoff_time_local,
    get_flag_emoji
)

# CONFIGURAÇÕES via ENV (Valores default usados se a ENV falhar)
# ATENÇÃO: Agora esta variável espera um X-Auth-Token do football-data.org!
API_TOKEN = os.getenv("API_TOKEN", "YOUR_FOOTBALLDATA_API_TOKEN") 
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "YOUR_TELEGRAM_TOKEN") 
CHAT_ID = os.getenv("CHAT_ID", "YOUR_CHAT_ID")                     
TZ = pytz.timezone("America/Sao_Paulo")

# Bot do Telegram
bot = Bot(token=TELEGRAM_TOKEN)
TOP_QTY = 4 # Quantidade de partidas por envio (limite de TOP Oportunidades)

# Filtro mínimo de confiança (para aparecer na lista de oportunidades)
# 0% para "Sem Dados" será filtrado aqui.
MIN_CONFIDENCE = 50 

# Margem de tempo de segurança para evitar pegar jogos que já começaram ou começarão em segundos.
MINUTES_BEFORE_KICKOFF = 2 

# ----------------------------------------------------------------------
# FUNÇÕES DE ANÁLISE E MENSAGEM
# ----------------------------------------------------------------------

async def build_message(fixtures, api_token, qtd=4):
    """Analisa as fixtures, ordena pela confiança e constrói a mensagem final."""
    
    # 1. Analisa todos os jogos em paralelo
    analysis_tasks = []
    
    for f in fixtures:
        async def analyze_and_rate(fixture):
            participants = fixture.get("participants", [])
            if len(participants) < 2:
                # DEBUG: Ignorar jogos sem 2 participantes
                return None
            
            # Encontra IDs dos times (com base na localização 'home'/'away')
            # A nova estrutura mapeada do football-data.org mantém 'meta'
            home_id = next((p["id"] for p in participants if p["meta"]["location"] == "home"), None)
            away_id = next((p["id"] for p in participants if p["meta"]["location"] == "away"), None)

            if not home_id or not away_id:
                # DEBUG: Ignorar jogos onde home/away ID não está claro
                return None
            
            # Análise de Métricas (REAL)
            # compute_team_metrics agora usa aiohttp
            hm, am = await asyncio.gather(
                compute_team_metrics(api_token, home_id, last=3), 
                compute_team_metrics(api_token, away_id, last=3)
            )

            # decide_best_market agora escolhe o melhor mercado entre todos (Gols FT, Vencedor, Escanteios, Gols HT)
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

        analysis_tasks.append(analyze_and_rate(f))

    # Executa a análise para todos os jogos e filtra os nulos (confiança < MIN_CONFIDENCE)
    analyzed_fixtures_raw = await asyncio.gather(*analysis_tasks)
    analyzed_fixtures = [f for f in analyzed_fixtures_raw if f is not None]

    # 2. Ordena pela confiança (do maior para o menor)
    analyzed_fixtures.sort(key=lambda x: (x.get('confidence', 0), x.get("starting_at", "")), reverse=True)


    # 3. CONSTRUIR MENSAGEM
    now = datetime.now(TZ)
    
    # Altera o cabeçalho para refletir o novo filtro
    header = (
        f"📅 Análises — {now.strftime('%d/%m/%Y')} (JOGOS NAS PRÓXIMAS 24H)\n"
        f"⏱ Atualizado — {now.strftime('%H:%M')} (BRT)\n\n"
        f"🔥 Top {qtd} Oportunidades (Sinais > {MIN_CONFIDENCE}%) 🔥\n\n"
    )
    lines = [header]

    count = 0
    
    for f in analyzed_fixtures:
        if count >= qtd:
            break
            
        participants = f.get("participants", [])
        # Uso 'next' para garantir que pegamos os times corretos, independentemente da ordem na lista
        home = next((p for p in participants if p["meta"]["location"] == "home"), {})
        away = next((p for p in participants if p["meta"]["location"] == "away"), {})

        # Dados da partida
        league_data = f.get("league", {})
        league_name = league_data.get("name", "Desconhecida")
        # O country code agora é mapeado pelo analysis.py
        league_country_code = league_data.get("country", {}).get("code", "xx")
        
        kickoff_local = kickoff_time_local(f, TZ)
        
        # Emoji da bandeira da liga (País)
        league_flag = get_flag_emoji(league_country_code)
        
        home_name = home.get("name", "Casa")
        away_name = away.get("name", "Fora")
        
        suggestion = f.get('suggestion', 'N/A')
        confidence = f.get('confidence', 0)

        # LINHA ATUALIZADA: Remoção das bandeiras dos times (home_flag e away_flag)
        part = (
            f"{count + 1}. ⚽ {home_name} x {away_name}\n"
            f"🏆 {league_flag} {league_name}  •  🕒 {kickoff_local}\n"
            f"🎯 Sugestão principal: {suggestion}\n"
            f"💹 Confiança: {confidence}%\n"
            "──────────────────────────────\n"
        )
        lines.append(part)
        count += 1

    if count == 0:
        lines.append(f"⚠ Nenhuma partida TOP {qtd} encontrada para as próximas 48h, com confiança acima de {MIN_CONFIDENCE}%.\n")

    footer = "\n🔎 Obs: análise baseada em últimos 5 jogos e responsabilidade."
    lines.append(footer)
    return "\n".join(lines)


async def run_analysis_send(qtd=TOP_QTY):
    """Executa o ciclo completo de busca, filtro e envio de mensagem."""
    
    # ATENÇÃO: O API_TOKEN agora é para football-data.org (X-Auth-Token)
    if API_TOKEN == "YOUR_FOOTBALLDATA_API_TOKEN":
        print("\n🚨 ERRO: Token da API (football-data.org) não configurado. Abortando execução.")
        return 
    
    if CHAT_ID == "YOUR_CHAT_ID" or TELEGRAM_TOKEN == "YOUR_TELEGRAM_TOKEN":
        print("\n🚨 ERRO: CHAT_ID ou TELEGRAM_TOKEN não configurados. A análise será executada, mas a mensagem não será enviada.")
        
    # 1. Definir o range de tempo (48h)
    now_local = datetime.now(TZ)
    time_limit_48h = now_local + timedelta(hours=24)
    
    print(f"DEBUG: Buscando jogos futuros. Limite de 48h: {time_limit_48h.strftime('%d/%m %H:%M')} (BRT)")

    try:
        # 2. Busca fixtures (agora com filtro de data no analysis.py)
        fixtures = await fetch_upcoming_fixtures(API_TOKEN, per_page=100)
        
        if not fixtures:
            if CHAT_ID != "YOUR_CHAT_ID":
                await bot.send_message(chat_id=CHAT_ID, text=f"⚠ A API não retornou jogos futuros para o período de análise.")
            return
        
        # 3. FILTRO TEMPORAL E DE INÍCIO
        upcoming_fixtures = []
        # Margem de segurança de 2 minutos (MINUTES_BEFORE_KICKOFF)
        time_threshold = now_local + timedelta(minutes=MINUTES_BEFORE_KICKOFF) 

        print(f"DEBUG: Total de jogos encontrados pela API: {len(fixtures)}.")
        
        # O LOG MAIS IMPORTANTE: Para identificar as datas distantes!
        for f in fixtures:
            # kickoff_time_local agora usa datetime.fromisoformat
            kickoff_dt = kickoff_time_local(f, TZ, return_datetime=True)
            home_name = next((p["name"] for p in f.get("participants", []) if p["meta"]["location"] == "home"), "Time Desconhecido")
            away_name = next((p["name"] for p in f.get("participants", []) if p["meta"]["location"] == "away"), "Time Desconhecido")
            
            log_prefix = f"DEBUG FILTRO {home_name} x {away_name} ({kickoff_dt.strftime('%d/%m %H:%M')}): "

            # 3.1. Filtro de 48 horas (precisa ser antes ou igual ao limite de 48h)
            if kickoff_dt > time_limit_48h:
                print(f"{log_prefix} ELIMINADO: Jogo após 48h. (Limite: {time_limit_48h.strftime('%d/%m %H:%M')})")
                continue

            # 3.2. Filtro de JÁ COMEÇOU (precisa ser depois do limite de 2 minutos)
            if kickoff_dt > time_threshold:
                 upcoming_fixtures.append(f)
            else:
                 print(f"{log_prefix} ELIMINADO: Jogo já começou ou está muito perto. (Threshold: {time_threshold.strftime('%H:%M')})")

        print(f"DEBUG: Jogos dentro de 48h e não iniciados (restantes): {len(upcoming_fixtures)}.")
        
        if not upcoming_fixtures:
            if CHAT_ID != "YOUR_CHAT_ID":
                await bot.send_message(chat_id=CHAT_ID, text=f"⚠ Nenhuma partida agendada para as próximas 48h que ainda não começou e/ou passou pelo filtro de tempo.")
            return
            
        # 4. Análise, construção da mensagem e envio
        message = await build_message(upcoming_fixtures, API_TOKEN, qtd)
        
        if CHAT_ID != "YOUR_CHAT_ID" and TELEGRAM_TOKEN != "YOUR_TELEGRAM_TOKEN":
             # Parse mode é Markdown
            await bot.send_message(chat_id=CHAT_ID, text=message, parse_mode="Markdown")
        else:
            print("--- MENSAGEM PRONTA (NÃO ENVIADA) ---")
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
# SCHEDULER E EXECUÇÃO PRINCIPAL
# ----------------------------------------------------------------------

def start_scheduler():
    """Inicia o agendador de tarefas."""
    scheduler = AsyncIOScheduler(timezone=TZ)
    
    # Horários de execução (BRT)
    scheduler.add_job(lambda: asyncio.create_task(run_analysis_send(TOP_QTY)), "cron", hour=0, minute=0) # Meia-noite (para pegar jogos do dia)
    scheduler.add_job(lambda: asyncio.create_task(run_analysis_send(TOP_QTY)), "cron", hour=6, minute=0) # Manhã
    scheduler.add_job(lambda: asyncio.create_task(run_analysis_send(TOP_QTY)), "cron", hour=16, minute=0) # Tarde
    scheduler.add_job(lambda: asyncio.create_task(run_analysis_send(TOP_QTY)), "cron", hour=19, minute=0) # Noite
    
    scheduler.start()
    print("✅ Agendador iniciado para 00:00, 06:00, 16:00, e 19:00 (BRT).")

async def main():
    """Função principal que mantém o bot rodando."""
    
    # 1. Checagem de variáveis de ambiente
    missing = []
    # Verifica o novo valor default
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
        await run_analysis_send(TOP_QTY)
        
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

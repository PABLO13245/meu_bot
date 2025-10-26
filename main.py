import asyncio
import os
import pytz
import random
import sys
from datetime import datetime, timedelta, timezone

# IMPORTAÇÕES LOCAIS
# Certifique-se de que analysis.py e telegram_bot.py estão no mesmo diretório
# Assumimos que o telegram_bot é responsável por telegram_send_message
from analysis import fetch_upcoming_fixtures, compute_team_metrics, decide_best_market, kickoff_time_local
from telegram_bot import telegram_send_message 

# ========== CONFIGURAÇÕES GLOBAIS ==========
# Use os tokens fornecidos pelas variáveis de ambiente do Render
API_TOKEN = os.environ.get("SPORTMONKS_API_TOKEN")
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

# Quantidade de jogos que você quer analisar e enviar
TOP_QTY = 3 

# =================================================================
# LISTA DE GRUPOS DE LIGAS PARA ANÁLISE (PREENCHA AQUI)
# Cada item da lista deve ser uma string de IDs de ligas separados por vírgula.
# Exemplo de IDs: 8 (Premier League), 384 (Serie A), 564 (La Liga)
# Mantenha cada grupo com a quantidade de times que você deseja (ex: 7)
# =================================================================
LEAGUE_GROUPS = [
    # GRUPO 1: Substitua "ID1,ID2,..." pelos seus primeiros 7 IDs de ligas.
    "ID1,ID2,ID3,ID4,ID5,ID6,ID7", 
    
    # GRUPO 2: Substitua "ID8,ID9,..." pelos seus próximos 7 IDs de ligas.
    "ID8,ID9,ID10,ID11,ID12,ID13,ID14",
    
    # GRUPO 3: Substitua "ID15,ID16,..." pelos seus últimos 7 IDs de ligas.
    "ID15,ID16,ID17,ID18,ID19,ID20,ID21"
]
# =================================================================


# ===================================================
# FUNÇÃO PRINCIPAL: RODA ANÁLISES E ENVIA MENSAGENS
# ===================================================
async def run_analysis_send(qtd_top_qty):
    if not API_TOKEN or not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("❌ Erro: Tokens de API ou Telegram não configurados nas variáveis de ambiente.")
        return

    # O Sportmonks requer que as datas estejam no formato UTC
    now_utc = datetime.now(timezone.utc)
    start_str = now_utc.strftime("%Y-%m-%d")
    # Busca de 7 dias
    end_str = (now_utc + timedelta(days=7)).strftime("%Y-%m-%d") 
    
    print(f"\nIniciando análise para o período: {start_str} a {end_str} (UTC)")
    
    # Loop para rodar as 3 análises separadas
    for i, league_set in enumerate(LEAGUE_GROUPS):
        print(f"\n--- INICIANDO ANÁLISE DO GRUPO {i+1} ({len(league_set.split(','))} ligas) ---")
        
        try:
            # 1. BUSCA DE FIXTURES (Partidas)
            # Passa o conjunto de ligas (league_set) para a função
            fixtures = await fetch_upcoming_fixtures(
                API_TOKEN, 
                start_str, 
                end_str, 
                league_ids=league_set # <--- Argumento league_ids para o analysis.py
            )
            
            if not fixtures:
                print(f"❌ Não foram encontrados jogos futuros para o Grupo {i+1} com estes filtros.")
                continue # Pula para o próximo grupo

            # 2. PROCESSAMENTO E GERAÇÃO DE SUGESTÕES
            filtered_suggestions = []
            
            for fixture in fixtures:
                # Simula a obtenção de métricas (na versão real, esta função usaria API)
                home_metrics = await compute_team_metrics(API_TOKEN, fixture["participants"][0]["id"])
                away_metrics = await compute_team_metrics(API_TOKEN, fixture["participants"][1]["id"])
                
                # Decisão do Mercado
                market_suggestion, confidence = decide_best_market(home_metrics, away_metrics)
                
                # Formata a mensagem
                home_team = fixture["participants"][0]["name"]
                away_team = fixture["participants"][1]["name"]
                
                message = (
                    f"⏰ {kickoff_time_local(fixture)} | {fixture['league']['name']}\n"
                    f"🏆 {home_team} vs {away_team}\n"
                    f"🔥 Sugestão: {market_suggestion} (Confiança: {confidence}%)"
                )
                
                filtered_suggestions.append({
                    "confidence": confidence,
                    "message": message
                })

            # 3. FILTRO FINAL E ENVIO
            # Ordena por confiança e seleciona os TOP QTY
            filtered_suggestions.sort(key=lambda x: x["confidence"], reverse=True)
            top_suggestions = [s["message"] for s in filtered_suggestions[:qtd_top_qty]]

            if top_suggestions:
                header = f"🚀 TOP {len(top_suggestions)} ANÁLISES PARA O GRUPO {i+1}\n"
                full_message = header + "\n\n".join(top_suggestions)
                
                await telegram_send_message(full_message, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID)
                print(f"✅ Mensagens enviadas com sucesso para o Telegram para o Grupo {i+1}.")
            else:
                print(f"❌ Nenhuma sugestão com alta confiança para o Grupo {i+1}.")

            # Espera 5 segundos para evitar saturar a API (importante para o Rate Limit)
            await asyncio.sleep(5) 
            
        except Exception as e:
            print(f"⚠ Erro fatal durante a análise do Grupo {i+1}: {e}")
    
    print("\nAnálise de todos os grupos concluída.")


# ===================================================
# PONTO DE ENTRADA DO SCRIPT
# ===================================================
if __name__ == "__main__":
    try:
        # Modo de teste imediato, usado para debugar no Web Shell do Render
        if "TEST_NOW" in os.environ:
            print("Modo de teste imediato ativado.")
            asyncio.run(run_analysis_send(TOP_QTY))
            
        # Modo de execução agendada (usando o agendador do Render)
        else:
            # O Render roda o bot nos horários configurados (06:00, 16:00, 19:00)
            print("Execução agendada iniciada.")
            asyncio.run(run_analysis_send(TOP_QTY))

    except Exception as e:
        print(f"🚨 Erro na execução principal: {e}")

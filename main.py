import asyncio
import aiohttp
from datetime import datetime, timezone, timedelta
import pytz
import sys
import os
import random 
from analysis import compute_team_metrics, decide_best_market # Importando as funções

# CONFIGURAÇÃO: O script agora tentará ler o token da variável de ambiente 'SPORTMONKS_API_TOKEN'.
ENV_TOKEN = os.environ.get('API_TOKEN')
API_TOKEN = ENV_TOKEN if ENV_TOKEN else "API_TOKEN" 

# Configurações Base
BASE_URL = "https://api.sportmonks.com/v3/football"
STATE_FUTURE_IDS = "1,3" # 1=Awaiting, 3=Scheduled 

# Mapeamento manual para corrigir ligas onde o código do país está ausente (Ex: Suécia)
MANUAL_COUNTRY_MAP = {
    "Allsvenskan": "SE", 
}

# Mapeamento de Países para Bandeiras (Emojis)
def get_flag_emoji(country_code):
    """Converte o código de país (ISO 3166-1 alpha-2) em emoji de bandeira."""
    if country_code is None or len(country_code) != 2:
        return ""
    # Emojis de bandeira são gerados a partir de 2 caracteres regionais:
    return "".join(chr(0x1F1E6 + ord(char) - ord('A')) for char in country_code.upper())


# ----------------------------------------------------------------------
# FUNÇÕES DE BUSCA DA API
# ----------------------------------------------------------------------

async def fetch_upcoming_fixtures(api_token, start_date, per_page=150):
    """Busca jogos futuros na API da SportMonks, filtrando apenas por data e estado (TODAS AS LIGAS)."""
    
    main_filters = f"dates:{start_date};fixtureStates:{STATE_FUTURE_IDS}"
    
    url = (
        f"{BASE_URL}/fixtures"
        f"?api_token={api_token}"
        f"&include=participants;league;season;participants.country;league.country"
        f"&filters={main_filters}"
        f"&per_page={per_page}"
    )
    
    print(f"DEBUG: Buscando jogos de {start_date} em TODAS as ligas.")
    
    try:
        async with aiohttp.ClientSession() as session:
            max_retries = 3
            for attempt in range(max_retries):
                async with session.get(url) as response:
                    if response.status == 200:
                        data = await response.json()
                        fixtures = data.get("data", [])
                        
                        # CORREÇÃO PÓS-PROCESSAMENTO
                        for f in fixtures:
                            league_name = f.get("league", {}).get("name")
                            if league_name in MANUAL_COUNTRY_MAP:
                                country_code = MANUAL_COUNTRY_MAP[league_name]
                                f['league']['country'] = {'code': country_code}
                                for p in f.get('participants', []):
                                    if 'country' not in p or not p['country'].get('code'):
                                        p['country'] = {'code': country_code}

                        print(f"✅ Jogos futuros encontrados (Todas as Ligas): {len(fixtures)}")
                        return fixtures
                    
                    elif response.status == 429 and attempt < max_retries - 1:
                        wait_time = 2 ** attempt 
                        print(f"⚠ Rate Limit atingido (429). Tentando novamente em {wait_time}s...")
                        await asyncio.sleep(wait_time)
                    else:
                        print(f"❌ Erro ao buscar fixtures: {response.status} - {await response.text()}")
                        return []
                        
            return []
                
    except Exception as e:
        print(f"❌ Erro na requisição de fixtures: {e}")
        return []

# ----------------------------------------------------------------------
# FUNÇÕES AUXILIARES DE DATA
# ----------------------------------------------------------------------

def kickoff_time_local(fixture, tz, return_datetime=False):
    """Converte a string de horário UTC da API para horário local (BRT) e formata."""
    
    # String da API está no formato: YYYY-MM-DD HH:MM:SS
    starting_at_str = fixture.get("starting_at") 
    
    if not starting_at_str:
        return "N/A"
        
    try:
        # 1. Parsear como UTC
        dt_utc = datetime.strptime(starting_at_str, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
        
        # 2. Converter para o fuso horário local (BRT)
        dt_local = dt_utc.astimezone(tz)
        
        if return_datetime:
            return dt_local
        
        # 3. Formatar
        now_local = datetime.now(tz).date()
        if dt_local.date() == now_local:
            return dt_local.strftime("%H:%M")
        else:
            return dt_local.strftime("%H:%M — %d/%m")
            
    except Exception as e:
        print(f"Erro ao processar data {starting_at_str}: {e}")
        if return_datetime:
            return datetime.now(tz)
        return "Erro de data"

# ----------------------------------------------------------------------
# FUNÇÃO PRINCIPAL DE EXECUÇÃO
# ----------------------------------------------------------------------

async def main(api_token):
    """Função principal para buscar, analisar e exibir as sugestões de apostas."""
    if api_token == "API_TOKEN":
        print("\n🚨 ERRO: Por favor, substitua 'YOUR_SPORTMONKS_API_TOKEN' pelo seu token real da SportMonks para executar a busca na API.")
        return

    # Configuração de Fuso Horário Local (Brasil - São Paulo)
    try:
        tz_local = pytz.timezone("America/Sao_Paulo")
    except pytz.exceptions.UnknownTimeZoneError:
        print("⚠ Fuso horário 'America/Sao_Paulo' não encontrado. Usando UTC.")
        tz_local = timezone.utc
        
    execution_time = datetime.now(tz_local)
    today_date = execution_time.strftime("%Y-%m-%d") 
    
    # >>> MUDANÇA AQUI: Define o limite exato de 48 horas a partir do momento da execução
    time_limit_48h = execution_time + timedelta(hours=48)


    # 1. Busca os jogos futuros
    fixtures = await fetch_upcoming_fixtures(api_token, today_date, per_page=150)
    
    if not fixtures:
        print("\nNão foram encontrados jogos futuros para análise.")
        return

    # 2. FILTRO RIGOROSO DE 48 HORAS
    # Remove todos os jogos que estão fora da nova janela de 48h
    filtered_fixtures = []
    for f in fixtures:
        kickoff_dt = kickoff_time_local(f, tz_local, return_datetime=True)
        # >>> MUDANÇA AQUI: Compara com o novo limite de 48h
        if kickoff_dt <= time_limit_48h: 
            filtered_fixtures.append(f)
            
    print(f"✅ Jogos filtrados para 48h: {len(filtered_fixtures)} de {len(fixtures)} encontrados.")
    
    if not filtered_fixtures:
        print("\nNenhum jogo encontrado dentro da janela de 48 horas (mesmo sem aplicar o filtro de confiança).")
        return


    # 3. Prepara e executa a análise dos jogos filtrados em paralelo
    async def analyze_fixture_task(fixture):
        """Função auxiliar para analisar um único jogo."""
        
        # Tenta extrair participantes
        home_team = next((p for p in fixture.get("participants", []) if p["meta"]["location"] == "home"), None)
        away_team = next((p for p in fixture.get("participants", []) if p["meta"]["location"] == "away"), None)

        if not home_team or not away_team:
            return None 

        # 3.1. Simula as métricas dos times (em paralelo para o Home e Away)
        try:
            home_metrics, away_metrics = await asyncio.gather(
                compute_team_metrics(api_token, home_team["id"]),
                compute_team_metrics(api_token, away_team["id"])
            )
        except Exception as e:
            print(f"❌ Erro ao calcular métricas para jogo ID {fixture.get('id')}: {e}. Ignorando.")
            return None
        
        # 3.2. Decisão de mercado
        suggestion, confidence = decide_best_market(home_metrics, away_metrics)
        
        # 3.3. Filtra resultados de alta confiança (>= 70%)
        if confidence < 50:
            return None

        # 3.4. Formatação do resultado
        league = fixture.get("league", {})
        league_name = league.get("name", "Liga Desconhecida")
        country_code = league.get("country", {}).get("code")
        flag_emoji = get_flag_emoji(country_code or '??')
        time_local = kickoff_time_local(fixture, tz_local)
        match_str = f"{home_team.get('name', 'Casa')} vs {away_team.get('name', 'Fora')}"
        
        return {
            "time": kickoff_time_local(fixture, tz_local, return_datetime=True),
            "output_line": (
                f"⏰ {time_local} | {flag_emoji} {league_name} \n"
                f"   ⚽ {match_str}\n"
                f"   📈 SUGERIDO: {suggestion} (Confiança: {confidence}%)\n"
                f"   ---\n"
            ),
        }
        
    # Executa todas as tarefas de análise concorrentemente nos jogos FILTRADOS
    analysis_tasks = [analyze_fixture_task(f) for f in filtered_fixtures]
    
    raw_results = await asyncio.gather(*analysis_tasks)
    valid_results = [res for res in raw_results if res is not None]
    
    if not valid_results:
        print("\nNenhum jogo de alta confiança (>= 70%) encontrado dentro das próximas 48 horas.")
        return
    
    # 4. Ordena os resultados por horário
    sorted_results = sorted(valid_results, key=lambda x: x['time'])
    
    # 5. Exibe os resultados
    print("\n" + "="*80)
    # >>> MUDANÇA AQUI: Título do relatório
    print(f"🏆 ANÁLISE DE JOGOS FUTUROS (PRÓXIMAS 48H) - SINAL FORTE (>= 70%) 🏆") 
    print(f"Data/Hora de Referência (BRT): {execution_time.strftime('%d/%m/%Y %H:%M:%S')}")
    print("="*80)
    
    for result in sorted_results:
        print(result["output_line"], end='')
        
    print("="*80)
    print("Fim da Análise. Lembre-se: As métricas de time são SIMULADAS.")

if __name__ == "__main__":
    
    token = API_TOKEN
    if len(sys.argv) > 1:
        token = sys.argv[1]
    
    try:
        asyncio.run(main(token))
    except KeyboardInterrupt:
        print("\nExecução interrompida pelo usuário.")

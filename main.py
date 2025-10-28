import asyncio
import aiohttp
from datetime import datetime, timezone
import pytz
import sys
import random
import os # Novo import para ler variáveis de ambiente

# CONFIGURAÇÃO: O script agora tentará ler o token da variável de ambiente 'SPORTMONKS_API_TOKEN'.
# Se não encontrar, ele usará o placeholder.
ENV_TOKEN = os.environ.get('SPORTMONKS_API_TOKEN')
API_TOKEN = ENV_TOKEN if ENV_TOKEN else "YOUR_SPORTMONKS_API_TOKEN" 

# Configurações Base
BASE_URL = "https://api.sportmonks.com/v3/football"
STATE_FUTURE_IDS = "1,3" # 1=Awaiting, 3=Scheduled 
# Removido o filtro de ligas confiáveis (TRUSTED_LEAGUE_IDS). O bot buscará TODAS as ligas.

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
    # chr(127462 + offset) é o ponto de código Unicode para o caractere de bandeira regional
    return "".join(chr(0x1F1E6 + ord(char) - ord('A')) for char in country_code.upper())


# ----------------------------------------------------------------------
# FUNÇÕES DE BUSCA DA API
# ----------------------------------------------------------------------

async def fetch_upcoming_fixtures(api_token, start_date, per_page=150):
    """Busca jogos futuros na API da SportMonks, filtrando apenas por data e estado (TODAS AS LIGAS)."""
    
    # Filtro de data e estado (AGORA SEM O FILTRO DE LEAGUE IDS)
    main_filters = f"dates:{start_date};fixtureStates:{STATE_FUTURE_IDS}"
    
    url = (
        f"{BASE_URL}/fixtures"
        f"?api_token={api_token}"
        f"&include=participants;league;season;participants.country;league.country"
        f"&filters={main_filters}"
        f"&per_page={per_page}"
    )
    
    # DEBUG: URL de Requisição (token omitido por segurança)
    print(f"DEBUG: Buscando jogos de {start_date} em TODAS as ligas.")
    print(f"DEBUG: URL de Requisição: {url.split('api_token=')[0]}... (token omitido) - TESTE ESTA URL NO NAVEGADOR!")
    
    try:
        async with aiohttp.ClientSession() as session:
            # Implementação básica de backoff para lidar com rate limits, se necessário
            max_retries = 3
            for attempt in range(max_retries):
                async with session.get(url) as response:
                    if response.status == 200:
                        data = await response.json()
                        fixtures = data.get("data", [])
                        
                        # CORREÇÃO PÓS-PROCESSAMENTO: Injetar códigos de país se ausentes (Bandeiras)
                        for f in fixtures:
                            league_name = f.get("league", {}).get("name")
                            
                            # 1. Tenta usar mapeamento manual para a liga
                            if league_name in MANUAL_COUNTRY_MAP:
                                country_code = MANUAL_COUNTRY_MAP[league_name]
                                f['league']['country'] = {'code': country_code}
                                
                                # 2. Injeta o código do país da liga nos times (se o time não tiver)
                                for p in f.get('participants', []):
                                    if 'country' not in p or not p['country'].get('code'):
                                        p['country'] = {'code': country_code}

                        print(f"✅ Jogos futuros encontrados (Todas as Ligas): {len(fixtures)}")
                        return fixtures
                    
                    elif response.status == 429 and attempt < max_retries - 1:
                        # Too Many Requests - esperar e tentar novamente
                        wait_time = 2 ** attempt 
                        print(f"⚠ Rate Limit atingido (429). Tentando novamente em {wait_time}s...")
                        await asyncio.sleep(wait_time)
                    else:
                        print(f"❌ Erro ao buscar fixtures: {response.status} - {await response.text()}")
                        return []
                        
            return [] # Retorna vazio se todas as tentativas falharem
                
    except Exception as e:
        print(f"❌ Erro na requisição de fixtures: {e}")
        return []

async def compute_team_metrics(api_token, team_id, last=5):
    """
    Simula a busca e cálculo de métricas de uma equipe.
    (Em uma versão real, este seria o ponto onde você buscar a performance real do time)
    """
    # AWAIT AQUI É NECESSÁRIO PARA SIMULAR O TEMPO DE REQUISIÇÃO REAL
    await asyncio.sleep(random.uniform(0.1, 0.5)) 
    
    # Simulação: Retornamos dados simulados com variações para que a ordenação funcione.
    
    # Gera uma pequena variação para simular diferentes estatísticas de times
    if random.random() < 0.1: # 10% de chance de ter um time ruim
        gols_marcados = random.randint(0, 5)
        gols_sofridos = random.randint(5, 10)
        vitorias = random.randint(0, 2)
    else: # 90% de chance de ter um time mediano/bom
        gols_marcados = random.randint(5, 10)
        gols_sofridos = random.randint(3, 7)
        vitorias = random.randint(2, 4)
        
    return {
        "team_id": team_id,
        "goals_scored": gols_marcados,
        "goals_conceded": gols_sofridos,
        "wins": vitorias,
        "avg_gs": gols_marcados / last,
        "avg_gc": gols_sofridos / last,
        "form_score": (vitorias / last) * 100 # Pontuação baseada em vitórias
    }


# ----------------------------------------------------------------------
# FUNÇÕES DE ANÁLISE E DECISÃO
# ----------------------------------------------------------------------

def decide_best_market(home_metrics, away_metrics):
    """
    Decide a melhor sugestão de aposta e calcula a confiança.
    (Lógica altamente simplificada para demonstração)
    """
    
    # 1. CÁLCULO DE FORÇA
    
    # Média de gols esperados do jogo (baseado em GS Home + GC Away e GS Away + GC Home)
    total_avg_goals = home_metrics["avg_gs"] + away_metrics["avg_gc"] + \
                      away_metrics["avg_gs"] + home_metrics["avg_gc"]
                      
    total_avg_goals /= 2 # Média por partida
    
    # Força relativa de cada time
    home_form = home_metrics["form_score"]
    away_form = away_metrics["form_score"]
    
    form_diff = abs(home_form - away_form)
    
    
    # 2. DECISÃO (SIMPLIFICADA)
    
    suggestion = "Sem sinal forte — evite aposta"
    confidence = 50 # Base (Mínimo para ser listado)
    
    # Analisando o mercado de Gols
    if total_avg_goals >= 2.8:
        suggestion = "Mais de 2.5 Gols (Over 2.5)"
        confidence += int(min(total_avg_goals * 10, 40)) # Aumenta confiança com a média
    elif total_avg_goals >= 2.0:
        suggestion = "Mais de 1.5 Gols (Over 1.5)"
        confidence += int(min(total_avg_goals * 10, 30))
        
    # Analisando o mercado de Vencedor (se a diferença de forma é grande)
    if form_diff > 40:
        winner = "Casa" if home_form > away_form else "Fora"
        
        # O time mais forte precisa ter boa média de ataque para justificar a vitória
        if winner == "Casa" and home_metrics["avg_gs"] > 2.0:
            suggestion = f"Vitória do Time da Casa (ML Home)"
            confidence = max(confidence, 85) # Sobe a confiança para alto
        elif winner == "Fora" and away_metrics["avg_gs"] > 1.8:
            suggestion = f"Vitória do Time Visitante (ML Away)"
            confidence = max(confidence, 85)
        # Se a sugestão for vitória e a sugestão anterior for over 2.5, mantém a vitória.
        # Caso contrário, mantém a melhor sugestão com maior confiança.


    # Garante que a confiança fique entre 50% e 99%
    confidence = min(99, max(50, confidence))

    return suggestion, confidence

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
        # Se for HOJE, mostra apenas a hora. Se for amanhã ou depois, mostra hora e data.
        now_local = datetime.now(tz).date()
        if dt_local.date() == now_local:
            return dt_local.strftime("%H:%M")
        else:
            return dt_local.strftime("%H:%M — %d/%m")
            
    except Exception as e:
        print(f"Erro ao processar data {starting_at_str}: {e}")
        if return_datetime:
            # Retorna a data atual como fallback em caso de erro (para evitar quebras no filtro)
            return datetime.now(tz)
        return "Erro de data"

# ----------------------------------------------------------------------
# FUNÇÃO PRINCIPAL DE EXECUÇÃO
# ----------------------------------------------------------------------

async def main(api_token):
    """Função principal para buscar, analisar e exibir as sugestões de apostas."""
    if api_token == "YOUR_SPORTMONKS_API_TOKEN":
        print("\n🚨 ERRO: Por favor, substitua 'YOUR_SPORTMONKS_API_TOKEN' pelo seu token real da SportMonks para executar a busca na API.")
        # Se o token não foi encontrado em lugar nenhum, saímos aqui.
        return

    # Configuração de Fuso Horário Local (Brasil - São Paulo)
    try:
        tz_local = pytz.timezone("America/Sao_Paulo")
    except pytz.exceptions.UnknownTimeZoneError:
        print("⚠ Fuso horário 'America/Sao_Paulo' não encontrado. Usando UTC.")
        tz_local = pytz.utc
        
    today_date = datetime.now(tz_local).strftime("%Y-%m-%d")

    # 1. Busca os jogos futuros
    fixtures = await fetch_upcoming_fixtures(api_token, today_date, per_page=150)
    
    if not fixtures:
        print("\nNão foram encontrados jogos futuros para análise.")
        return

    # 2. Prepara e executa a análise de todos os jogos em paralelo
    async def analyze_fixture_task(fixture):
        """Função auxiliar para analisar um único jogo."""
        
        # Tenta extrair participantes
        home_team = next((p for p in fixture.get("participants", []) if p["meta"]["location"] == "home"), None)
        away_team = next((p for p in fixture.get("participants", []) if p["meta"]["location"] == "away"), None)

        if not home_team or not away_team:
            # print(f"⚠ Jogos sem participantes claros (ID: {fixture.get('id')}). Ignorando.")
            return None 

        # 2.1. Simula as métricas dos times (em paralelo para o Home e Away)
        try:
            # A chamada para compute_team_metrics simula a busca de dados de performance
            home_metrics, away_metrics = await asyncio.gather(
                compute_team_metrics(api_token, home_team["id"]),
                compute_team_metrics(api_token, away_team["id"])
            )
        except Exception as e:
            print(f"❌ Erro ao calcular métricas para jogo ID {fixture.get('id')}: {e}. Ignorando.")
            return None
        
        # 2.2. Decisão de mercado
        suggestion, confidence = decide_best_market(home_metrics, away_metrics)
        
        # 2.3. Filtra resultados de alta confiança
        # MANTENHO O 70% ORIGINAL AQUI, mas podemos reduzir para testar (ex: 50)
        if confidence < 50:
            return None

        # 2.4. Formatação do resultado
        
        # Informações da Liga
        league = fixture.get("league", {})
        league_name = league.get("name", "Liga Desconhecida")
        
        # Código do país da liga (com fallback para '??' se não for encontrado)
        country_code = league.get("country", {}).get("code")
        flag_emoji = get_flag_emoji(country_code or '??')
        
        time_local = kickoff_time_local(fixture, tz_local)
        
        match_str = f"{home_team.get('name', 'Casa')} vs {away_team.get('name', 'Fora')}"
        
        # Retorna um dicionário para fácil ordenação e exibição
        return {
            "time": kickoff_time_local(fixture, tz_local, return_datetime=True),
            "output_line": (
                f"⏰ {time_local} | {flag_emoji} {league_name} \n"
                f"   ⚽ {match_str}\n"
                f"   📈 SUGERIDO: {suggestion} (Confiança: {confidence}%)\n"
                f"   ---\n"
            ),
        }
        
    # Executa todas as tarefas de análise concorrentemente
    analysis_tasks = [analyze_fixture_task(f) for f in fixtures]
    
    # Filtra os resultados válidos (aqueles que não retornaram None)
    raw_results = await asyncio.gather(*analysis_tasks)
    valid_results = [res for res in raw_results if res is not None]
    
    if not valid_results:
        # Esta é a mensagem que você verá se o filtro de 70% for muito rigoroso
        print("\nNenhum jogo de alta confiança (>= 70%) encontrado para a data de hoje/próximos dias.")
        return
    
    # 3. Ordena os resultados por horário (do mais cedo para o mais tarde)
    sorted_results = sorted(valid_results, key=lambda x: x['time'])
    
    # 4. Exibe os resultados
    print("\n" + "="*80)
    print(f"🏆 ANÁLISE DE JOGOS FUTUROS - SINAL FORTE (>= 70%) 🏆")
    print(f"Data de Referência (BRT): {datetime.now(tz_local).strftime('%d/%m/%Y %H:%M:%S')}")
    print("="*80)
    
    for result in sorted_results:
        # A linha já está formatada no analyze_fixture_task
        print(result["output_line"], end='')
        
    print("="*80)
    print("Fim da Análise. Lembre-se: As métricas de time são SIMULADAS.")

if __name__ == "__main__":
    
    token = API_TOKEN
    # Permite passar o token como argumento de linha de comando
    if len(sys.argv) > 1:
        token = sys.argv[1]
    
    try:
        # Rodar a função principal assíncrona
        asyncio.run(main(token))
    except KeyboardInterrupt:
        print("\nExecução interrompida pelo usuário.")

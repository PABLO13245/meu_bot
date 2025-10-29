# ======================================================================
# BLOCO PRINCIPAL DE EXECUÇÃO
# ======================================================================

async def main(api_token: str):
    """
    Função principal que orquestra a busca de jogos, cálculo de métricas e análise de mercado.
    """
    
    # Define o Fuso Horário Local (ex: BRT - Brasília Time)
    LOCAL_TIMEZONE = pytz.timezone('America/Sao_Paulo')
    
    print("🤖 Iniciando o Bot de Análise de Apostas (football-data.org) ⚽\n")
    
    # 1. Busca de Jogos Futuros
    try:
        upcoming_fixtures = await fetch_upcoming_fixtures(api_token)
    except Exception as e:
        print(f"❌ Erro fatal ao buscar jogos futuros: {e}")
        return

    if not upcoming_fixtures:
        print("⏸ Nenhuma partida encontrada nas próximas 48 horas nas ligas filtradas.")
        return

    print(f"\n⚙ Processando análise para {len(upcoming_fixtures)} jogos encontrados...\n")
    
    # Lista para armazenar as tarefas de cálculo de métricas
    tasks = []
    
    # Mapeamento para armazenar métricas já calculadas e evitar chamadas duplicadas
    # Chave: ID do Time (int), Valor: Dicionário de Métricas
    team_metrics_cache: Dict[int, Dict[str, Any]] = {}
    
    # 2. Criação de Tarefas de Cálculo de Métricas (Home & Away)
    
    async with aiohttp.ClientSession() as session:
        # Itera sobre os jogos para extrair os IDs dos times
        for fixture in upcoming_fixtures:
            home_team = fixture["participants"][0]
            away_team = fixture["participants"][1]
            
            home_id = home_team["id"]
            away_id = away_team["id"]
            
            # Garante que a tarefa de métricas seja criada apenas se o ID não estiver em cache
            # Isso é crucial para a eficiência.
            if home_id not in team_metrics_cache:
                # Criamos uma 'task' com o ID do time e o objeto de sessão
                tasks.append(
                    asyncio.create_task(compute_team_metrics(api_token, home_id))
                )
                team_metrics_cache[home_id] = None # Marca como "em processamento"
                
            if away_id not in team_metrics_cache:
                tasks.append(
                    asyncio.create_task(compute_team_metrics(api_token, away_id))
                )
                team_metrics_cache[away_id] = None # Marca como "em processamento"
                
    # 3. Execução Paralela das Tarefas de Métricas
    print(f"⏳ Executando {len(tasks)} chamadas de API para histórico de times em paralelo...")
    results = await asyncio.gather(*tasks, return_exceptions=True)
    print("✅ Todas as chamadas históricas concluídas.\n")
    
    # Popula o cache com os resultados
    for res in results:
        if not isinstance(res, Exception) and res.get("team_id") is not None:
            team_metrics_cache[res["team_id"]] = res
        elif isinstance(res, Exception):
            print(f"⚠ Uma tarefa de métricas falhou: {res}")
            
    # 4. Análise e Formatação dos Resultados
    
    final_analysis: List[Dict[str, Any]] = []
    
    for fixture in upcoming_fixtures:
        
        home_team = fixture["participants"][0]
        away_team = fixture["participants"][1]
        
        # Recupera as métricas do cache
        home_metrics = team_metrics_cache.get(home_team["id"], {"games_count": 0})
        away_metrics = team_metrics_cache.get(away_team["id"], {"games_count": 0})
        
        # Ignora jogos onde a coleta de histórico falhou para um ou ambos os times
        if home_metrics.get("games_count", 0) == 0 or away_metrics.get("games_count", 0) == 0:
            print(f"⚠ Pulando {home_team['name']} vs {away_team['name']}: Dados insuficientes/falha no histórico.")
            continue
            
        # Executa o algoritmo de decisão
        market, confidence = decide_best_market(home_metrics, away_metrics)
        
        # Obtém o horário formatado
        kickoff = kickoff_time_local(fixture, LOCAL_TIMEZONE)
        
        # Formata o resultado
        final_analysis.append({
            "fixture_id": fixture["id"],
            "date": kickoff,
            "league": f"{get_flag_emoji(fixture['league']['country']['code'])} {fixture['league']['name']}",
            "matchup": f"{home_team['name']} vs {away_team['name']}",
            "suggestion": market,
            "confidence": confidence,
            "home_metrics": home_metrics,
            "away_metrics": away_metrics
        })


    # 5. Apresentação dos Resultados
    
    print("\n" + "="*80)
    print("🏆 ANÁLISE DE SUGESTÕES DE APOSTAS PARA AS PRÓXIMAS 48H")
    print("="*80 + "\n")
    
    # Filtra por sugestões com alta confiança
    high_confidence_suggestions = sorted([
        a for a in final_analysis if a["confidence"] >= 65
    ], key=lambda x: x["confidence"], reverse=True)
    
    low_confidence_games = len(final_analysis) - len(high_confidence_suggestions)
    
    
    if high_confidence_suggestions:
        print(f"🌟 *{len(high_confidence_suggestions)} Sugestões de Alta Confiança (>= 65%)*\n")
        
        for idx, analysis in enumerate(high_confidence_suggestions):
            print(f"{idx+1}. {analysis['matchup']}** ({analysis['date']})")
            print(f"   LIGA: {analysis['league']}")
            print(f"   📈 SUGESTÃO: *{analysis['suggestion']}*")
            print(f"   🔥 CONFIANÇA: *{analysis['confidence']}%*\n")
        
        print(f"\nℹ Há {low_confidence_games} jogos adicionais com sugestões de baixa confiança (< 65%).")
    else:
        print("❌ Nenhuma sugestão com alta confiança (>= 65%) foi encontrada. Tente mais tarde.")


# ======================================================================
# EXECUÇÃO DO BLOCO PRINCIPAL
# ======================================================================

# ATENÇÃO: SUBSTITUA 'SUA_CHAVE_AQUI' PELA SUA CHAVE REAL DA API football-data.org
API_KEY = "SUA_CHAVE_AQUI" 

if _name_ == "_main_":
    if API_KEY == "SUA_CHAVE_AQUI":
        print("\n🚨 ERRO: Por favor, substitua 'SUA_CHAVE_AQUI' pelo seu token da API football-data.org antes de executar.")
    else:
        # Para executar uma função 'async' em Python
        # O bot só deve ser executado com Python 3.7+
        import platform
        if platform.system() == 'Windows':
            # Necessário no Windows para algumas versões do Python
            asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
            
        asyncio.run(main(API_KEY))

import random
import asyncio

# ----------------------------------------------------------------------
# FUNÇÕES DE ANÁLISE E DECISÃO
# ----------------------------------------------------------------------

async def compute_team_metrics(api_token, team_id, last=5):
    """
    Simula a busca e cálculo de métricas de uma equipe.
    (Em uma versão real, este seria o ponto onde você buscar a performance real do time)
    """
    # AWAIT AQUI É NECESSÁRIO PARA SIMULAR O TEMPO DE REQUISIÇÃO REAL
    # O token é apenas um placeholder aqui, pois não é usado na simulação.
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


    # Garante que a confiança fique entre 50% e 99%
    confidence = min(99, max(50, confidence))

    return suggestion, confidence

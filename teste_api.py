import requests
from datetime import date

# Seu token da Sportmonks
SPORTMONKS_TOKEN = "EI7WanytFQuS2LmHvbBQ1fMDJjzcbXfsCmgWBQ62enNgPDaYCbwRjH5fj36W"

# URL base da API
BASE_URL = "https://api.sportmonks.com/v3/football"

# Data de hoje
hoje = date.today()

# Endpoint para buscar partidas de hoje
url = f"{BASE_URL}/fixtures/date/{hoje}?api_token={SPORTMONKS_TOKEN}"

# Fazendo requisição
response = requests.get(url)

# Mostra o status da resposta
print("Status da resposta:", response.status_code)

# Se der certo (200), mostra as partidas
if response.status_code == 200:
    data = response.json()
    if data.get("data"):
        print(f"\n📅 Jogos de hoje ({hoje}):\n")
        for jogo in data["data"]:
            home = jogo["participants"][0]["name"] if jogo.get("participants") else "Time A"
            away = jogo["participants"][1]["name"] if len(jogo.get("participants", [])) > 1 else "Time B"
            print(f"{home} x {away}")
    else:
        print(f"Nenhum jogo encontrado para hoje ({hoje}).")
else:
    print("Erro ao consultar a API:", response.text)

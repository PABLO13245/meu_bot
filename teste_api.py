import requests
from datetime import date, timedelta

# Seu token da Sportmonks
SPORTMONKS_TOKEN = "EI7WanytFQuS2LmHvbBQ1fMDJjzcbXfsCmgWBQ62enNgPDaYCbwRjH5fj36W"

# URL base da API
BASE_URL = "https://api.sportmonks.com/v3/football"

# Datas: hoje e daqui a 3 dias
hoje = date.today()
futuro = hoje + timedelta(days=3)

# Endpoint para buscar partidas entre hoje e os próximos 3 dias
url = f"{BASE_URL}/fixtures/between/{hoje}/{futuro}?api_token={SPORTMONKS_TOKEN}"

# Fazendo requisição
response = requests.get(url)
print("Status da resposta:", response.status_code)

# Se der certo (200), mostra as partidas
if response.status_code == 200:
    data = response.json()
    if data.get("data"):
        print(f"\n📅 Jogos entre {hoje} e {futuro}:\n")
        for jogo in data["data"]:
            home = jogo["participants"][0]["name"] if jogo.get("participants") else "Time A"
            away = jogo["participants"][1]["name"] if len(jogo.get("participants", [])) > 1 else "Time B"
            start_time = jogo.get("starting_at", {}).get("date_time", "Sem horário definido")
            print(f"{home} x {away} — {start_time}")
    else:
        print(f"Nenhum jogo encontrado entre {hoje} e {futuro}.")
else:
    print("Erro ao consultar a API:", response.text)

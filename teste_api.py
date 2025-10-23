import requests
from datetime import date, timedelta

# Seu token da SportMonks
SPORTMONKS_TOKEN = "ETInavyFtcus2IwhybB041wDijZobXf4e6mgMB02a6mlpqDa1vCHpjH5t436iW"
BASE_URL = "https://api.sportmonks.com/v3/football"

# Datas: hoje e daqui a 3 dias
hoje = date.today()
futuro = hoje + timedelta(days=3)

# Endpoint
url = f"{BASE_URL}/fixtures/between/{hoje}/{futuro}?api_token={SPORTMONKS_TOKEN}"

# Requisição
resposta = requests.get(url)

print("Status da resposta:", resposta.status_code)
print("URL usada:", url)
print("Resposta bruta:", resposta.text)

if resposta.status_code == 200:
    dados = resposta.json()
    if "data" in dados and len(dados["data"]) > 0:
        print(f"📅 Jogos entre {hoje} e {futuro}:")
        for jogo in dados["data"]:
            time_casa = jogo["home_team"]["name"]
            time_fora = jogo["away_team"]["name"]
            horario = jogo.get("starting_at", "Sem horário definido")
            print(f"{time_casa} x {time_fora} — {horario}")
    else:
        print(f"Nenhum jogo encontrado entre {hoje} e {futuro}.")
else:
    print("❌ Erro ao consultar a API.")

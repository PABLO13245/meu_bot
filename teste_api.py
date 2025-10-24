import os
import requests

API_TOKEN = os.getenv("SPORTMONKS_TOKEN")

# Pega apenas 5 partidas para testar
url = f"https://api.sportmonks.com/v3/football/fixtures?api_token={API_TOKEN}&include=league&per_page=5"

response = requests.get(url)
print("Status:", response.status_code)

if response.status_code == 200:
    data = response.json()
    for fixture in data["data"]:
        name = fixture.get("name")
        date = fixture.get("starting_at")
        print(f"📅 {name} — {date}")
else:
    print("Erro:", response.text)

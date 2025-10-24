import os
import requests

# Tokens e IDs
API_TOKEN = os.getenv("SPORTMONKS_TOKEN")  # seu token da SportMonks
TELEGRAM_TOKEN = "8444936746:AAE5JjO5vhrqb-HL7wWr-8kGpOjaCQybmgE"
CHAT_ID = "5245918045"

# URL da API da SportMonks (5 partidas)
url = f"https://api.sportmonks.com/v3/football/fixtures?api_token={API_TOKEN}&include=league;season&page=1"

response = requests.get(url)
print("Status:", response.status_code)

if response.status_code == 200:
    data = response.json()
    fixtures = data["data"][:5]  # pega apenas 5 partidas

    mensagens = []
    for fixture in fixtures:
        name = fixture.get("name", "Sem nome")
        date = fixture.get("starting_at", "Sem data")
        mensagens.append(f"🏆 {name}\n📅 {date}")

    texto = "\n\n".join(mensagens)

    # Envia a mensagem para o Telegram
    telegram_url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": texto}

    r = requests.post(telegram_url, data=payload)
    print("Mensagem enviada:", r.status_code)
else:
    print("Erro:", response.text)

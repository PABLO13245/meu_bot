import requests

API_TOKEN = "2HkQn0wO1VKISuHJfb2ZTdA7BMxXqiK0A0xZ6UZ2ewnro1HNJ2P7NPee28D1"
url = f"https://api.sportmonks.com/v3/football/fixtures?api_token={API_TOKEN}&include=participants;league;season"

response = requests.get(url)
print("Status code:", response.status_code)

if response.status_code == 200:
    data = response.json()
    print("✅ Conexão bem-sucedida! Exemplo de retorno:")
    print(data)
else:
    print("❌ Erro da API:", response.text)

import requests

API_TOKEN = "eNQYLjIAtZ5co7oMxlzyTPd4fb3s2lzRpDnQpNm9hoBL7sDoYr1HNHQKhPul"

url = f"https://api.sportmonks.com/v3/football/fixtures?api_token={API_TOKEN}&include=league,season,participants"

response = requests.get(url)
print("Status code:", response.status_code)

if response.status_code == 200:
    data = response.json()
    print("✅ Conexão bem-sucedida! Exemplo de retorno:")
    print(data)
else:
    print("❌ Erro da API:", response.text)

import requests

API_TOKEN = "JtleZ8exFFGvZQWYxRfjmqqWdmxkxKG6FrVGPOAVRpsqyRNAoPfezreZka64"
url = f"https://api.sportmonks.com/v3/football/fixtures?api_token={API_TOKEN}&include=participants;league;season"

response = requests.get(url)
print("Status code:", response.status_code)

if response.status_code == 200:
    data = response.json()
    print("✅ Conexão bem-sucedida! Exemplo de retorno:")
    print(data)
else:
    print("❌ Erro da API:", response.text)

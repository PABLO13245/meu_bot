import requests

# Seu token da SportMonks
SPORTMONKS_TOKEN = "EI7WanytFQuS2LmHvbBQ1fMDJjzcbXfsCmgWBQ62enNgPDaYCbwRjH5fj36W"

# URL base da API
BASE_URL = "https://api.sportmonks.com/v3/football"

# Endpoint para buscar partidas ao vivo
url = f"{BASE_URL}/livescores?api_token={SPORTMONKS_TOKEN}"

# Faz a requisição
response = requests.get(url)

# Mostra o resultado
print("Status da resposta:", response.status_code)
print("Resultado:")
print(response.json())

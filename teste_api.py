import requests

# Seu token da SportMonks
SPORTMONKS_TOKEN = "EI7WanytFQuS2LmHvbBQ1fMDJjzcbXfsCmgWBQ62enNgPDaYCbwRjH5fj36W"

# URL base da API
BASE_URL = "https://api.sportmonks.com/v3/football"

# Exemplo de endpoint para buscar partidas de hoje
url = f"{BASE_URL}/fixtures/date/2025-10-23?api_token={SPORTMONKS_TOKEN}"

# Fazendo requisição
response = requests.get(url)

# Exibindo resultado
print("Status da resposta:", response.status_code)
print("Resultado:")
print(response.json())

import requests

API_TOKEN = "eNQYLjIAtZ5co7oMxlzyTPd4fb3s2lzRpDnQpNm9hoBL7sDoYr1HNHQKhPul"
url = f"https://api.sportmonks.com/v3/football/fixtures/between/2025-10-23/2025-10-26?api_token={API_TOKEN}"

print("Solicitação à SportMonks...")

response = requests.get(url)
data = response.json()

if "data" in data and len(data["data"]) > 0:
    for jogo in data["data"]:
        print(f"ID do jogo: {jogo.get('id')}")
        print(f"Data: {jogo.get('starting_at')}")
        print(f"Liga ID: {jogo.get('league_id')}")
        print("-" * 30)
else:
    print("Nenhum jogo encontrado ou erro na resposta:")
    print(data)
import asyncio, aiohttp

async def main():
    url = "https://api.sportmonks.com/v3/football/fixtures/date/2025-10-26?api_token=eNQYLjIAtZ5co7oMxlzyTPd4fb3s2lzRpDnQpNm9hoBL7sDoYr1HNHQKhPul"
    async with aiohttp.ClientSession() as s:
        async with s.get(url) as r:
            print("Status:", r.status)
            print(await r.text())

asyncio.run(main())

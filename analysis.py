import os
import asyncio
from datetime import datetime, timedelta
from main import fetch_upcoming_fixtures, build_message, bot, CHAT_ID

async def test_real_message():
    print("🚀 Teste real iniciado...")

    # Pegando token e definindo intervalo de 48h
    API_TOKEN = os.getenv("API_TOKEN")
    if not API_TOKEN:
        print("❌ ERRO: Variável de ambiente API_TOKEN não encontrada.")
        return

    now = datetime.utcnow()
    start_str = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    end_str = (now + timedelta(hours=48)).strftime("%Y-%m-%dT%H:%M:%SZ")

    try:
        fixtures = fetch_upcoming_fixtures(API_TOKEN, start_str, end_str)
        if not fixtures:
            await bot.send_message(CHAT_ID, "⚠ Nenhuma partida encontrada nas próximas 48h.")
            return

        fixtures = sorted(fixtures, key=lambda x: x["starting_at"])
        message = await asyncio.to_thread(build_message, fixtures, 3)
        await bot.send_message(CHAT_ID, message, parse_mode="Markdown")

        print("✅ Mensagem enviada com sucesso!")

    except Exception as e:
        print(f"❌ Erro durante o teste: {e}")

if __name__ == "__main__":
    asyncio.run(test_real_message())

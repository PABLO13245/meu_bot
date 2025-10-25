import asyncio
from datetime import datetime, timedelta
from main import fetch_upcoming_fixtures, build_message, bot, CHAT_ID, API_TOKEN

async def test_real_message():
    print("🚀 Teste real iniciado...")
    now = datetime.utcnow()
    start_str = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    end_str = (now + timedelta(hours=48)).strftime("%Y-%m-%dT%H:%M:%SZ")

    try:
        fixtures = fetch_upcoming_fixtures(API_TOKEN, start_str, end_str)
        if not fixtures:
            await bot.send_message(CHAT_ID, "⚠ Nenhuma partida encontrada nas próximas 48h.")
            print("⚠ Nenhuma partida encontrada.")
            return

        fixtures = sorted(fixtures, key=lambda x: x["starting_at"])
        message = await asyncio.to_thread(build_message, fixtures, 3)
        await bot.send_message(CHAT_ID, message, parse_mode="Markdown")
        print("✅ Mensagem enviada com sucesso!")

    except Exception as e:
        print(f"❌ Erro durante o teste: {e}")

if __name__ == "__main__":
    asyncio.run(test_real_message())

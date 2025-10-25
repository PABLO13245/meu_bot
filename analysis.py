import asyncio
from main import fetch_upcoming_fixtures, build_message, bot, CHAT_ID

async def test_real_message():
    print("🚀 Teste real iniciado...")
    try:
        fixtures = fetch_upcoming_fixtures()
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

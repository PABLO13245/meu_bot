import asyncio
from datetime import datetime, timedelta
from main import fetch_upcoming_fixtures, build_message, bot, CHAT_ID, API_TOKEN

async def test_real_message():
    print("✅ Teste real iniciado...")

    now = datetime.utcnow()
    start_str = now.strftime("%Y-%m-%d")
    end_str = (now + timedelta(days=2)).strftime("%Y-%m-%d")

    try:
        print(f"🔵 Buscando partidas entre {start_str} e {end_str}...")
        fixtures = await asyncio.to_thread(fetch_upcoming_fixtures, API_TOKEN, start_str, end_str)

        if not fixtures:
            await bot.send_message(CHAT_ID, "⚠ Nenhuma partida encontrada nas próximas 48h.")
            print("⚠ Nenhuma partida encontrada nas próximas 48h.")
            return

        # Ordena as partidas por data de início
        fixtures = sorted(fixtures, key=lambda x: x["starting_at"])
        message = build_message(fixtures[:3])

        await bot.send_message(CHAT_ID, message)
        print("✅ Mensagem enviada com sucesso!")

    except Exception as e:
        print(f"❌ Erro durante o teste: {e}")

if _name_ == "_main_":
    asyncio.run(test_real_message())

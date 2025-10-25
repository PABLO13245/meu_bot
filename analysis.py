import requests
import os

# Função que simula envio de análise
async def run_analysis_send(num):
    print(f"🔍 Rodando análise número {num}...")

    TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
    CHAT_ID = os.getenv("CHAT_ID")

    if not TELEGRAM_TOKEN or not CHAT_ID:
        print("⚠ Variáveis TELEGRAM_TOKEN ou CHAT_ID não definidas.")
        return

    texto = f"📊 Análise automática número {num} concluída com sucesso!"

    # Envia pro Telegram
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    data = {"chat_id": CHAT_ID, "text": texto}
    response = requests.post(url, data=data)

    print("📨 Envio para Telegram:", response.status_code)

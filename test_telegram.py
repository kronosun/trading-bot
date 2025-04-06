import os
import requests
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

def send_telegram(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    data = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message
    }
    print("🔧 Données envoyées :", data)
    response = requests.post(url, data=data)
    print("📡 Réponse Telegram :", response.status_code, response.text)

send_telegram("✅ Test : Message de test depuis test_telegram.py")


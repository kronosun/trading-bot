import time
import hashlib
import hmac
import json
import requests
import os
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("COINEX_API_KEY")
API_SECRET = os.getenv("COINEX_API_SECRET")
BASE_URL = "https://api.coinex.com/v2"
MARKET = os.getenv("MARKET", "BTCUSDT")
TAKE_PROFIT = float(os.getenv("TAKE_PROFIT", 0.015))
STOP_LOSS = float(os.getenv("STOP_LOSS", 0.0075))
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")


def send_telegram(msg):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    data = {"chat_id": TELEGRAM_CHAT_ID, "text": msg}
    requests.post(url, data=data)


def generate_signature(req_time, params_str):
    to_sign = str(req_time) + params_str
    return hmac.new(API_SECRET.encode(), to_sign.encode(), hashlib.sha256).hexdigest()


def headers_with_signature(params):
    req_time = str(int(time.time() * 1000))
    params_str = json.dumps(params, separators=(',', ':'), ensure_ascii=False)
    signature = generate_signature(req_time, params_str)
    headers = {
        "Content-Type": "application/json",
        "X-CoinEX-Key": API_KEY,
        "X-CoinEX-Sign": signature,
        "X-CoinEX-Timestamp": req_time
    }
    return headers


def place_stop_orders_v2(direction: str, entry_price: float, amount: float):
    try:
        tp_price = round(entry_price * (1 + TAKE_PROFIT), 2) if direction == 'long' else round(entry_price * (1 - TAKE_PROFIT), 2)
        sl_price = round(entry_price * (1 - STOP_LOSS), 2) if direction == 'long' else round(entry_price * (1 + STOP_LOSS), 2)

        results = []

        for label, price, t_type in [("TP", tp_price, "take_profit"), ("SL", sl_price, "stop_loss")]:
            stop_order = {
                "market": MARKET,
                "side": "sell" if direction == "long" else "buy",
                "amount": str(amount),
                "stop_type": t_type,
                "stop_price": str(price),
                "order_type": "market",
                "position_id": 0
            }
            headers = headers_with_signature(stop_order)
            r = requests.post(f"{BASE_URL}/futures/put_stop_order", headers=headers, data=json.dumps(stop_order))
            results.append((label, r.status_code, r.text))

        return results

    except Exception as e:
        send_telegram(f"❌ Erreur API v2 CoinEx : {e}")
        return [("ERROR", 500, str(e))]


def get_index_price():
    try:
        r = requests.get(f"{BASE_URL}/futures/market_ticker?market={MARKET}")
        data = r.json()
        price = float(data['data']['index_price'])
        return price
    except Exception as e:
        send_telegram(f"⚠️ Erreur récupération prix index : {e}\nRéponse brute : {r.text if 'r' in locals() else 'N/A'}")
        return None


def adjust_amount_for_market(direction: str, desired_usdt: float):
    index_price = get_index_price()
    if not index_price:
        send_telegram("⚠️ Impossible de récupérer le prix d’index pour ajuster la position.")
        return None, None

    for attempt in range(5):
        amount = desired_usdt / index_price
        test_order = {
            "market": MARKET,
            "side": "buy" if direction == "long" else "sell",
            "amount": str(amount),
            "order_type": "market",
            "position_id": 0
        }
        headers = headers_with_signature(test_order)
        r = requests.post(f"{BASE_URL}/futures/put_order", headers=headers, data=json.dumps(test_order))
        response = r.json()

        if response['code'] == 0:
            deal_price = float(response['data']['deal_price'])
            send_telegram(f"✅ Position {direction.upper()} ouverte à {deal_price} (après ajustement)")
            return deal_price, amount
        elif "deviation" in response.get("message", ""):
            desired_usdt *= 0.5
            continue
        else:
            send_telegram(f"❌ Erreur ouverture position : {response}")
            return None, None

    send_telegram("🚫 Impossible d’ouvrir une position sans dépasser la limite de 1% d’écart.")
    return None, None

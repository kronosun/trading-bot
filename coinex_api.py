import time
import hmac
import hashlib
import requests
import os
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("COINEX_API_KEY")
API_SECRET = os.getenv("COINEX_API_SECRET")
API_BASE = "https://api.coinex.com/v1"
MARKET = os.getenv("MARKET", "BTCUSDT")
TAKE_PROFIT = float(os.getenv("TAKE_PROFIT", 0.015))
STOP_LOSS = float(os.getenv("STOP_LOSS", 0.0075))
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

def send_telegram(msg):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    data = {"chat_id": TELEGRAM_CHAT_ID, "text": msg}
    requests.post(url, data=data)

def sign(params: dict) -> dict:
    params['access_id'] = API_KEY
    params['tonce'] = str(int(time.time() * 1000))
    sorted_params = sorted(params.items())
    query = "&".join([f"{k}={v}" for k, v in sorted_params])
    sign_str = query + f"&secret_key={API_SECRET}"
    signature = hashlib.md5(sign_str.encode()).hexdigest().upper()
    headers = {
        "Authorization": signature,
        "Content-Type": "application/json"
    }
    return headers, params

def place_tp_sl(direction: str, entry_price: float, amount: float):
    try:
        headers = {}
        results = []

        if direction == 'long':
            tp_price = round(entry_price * (1 + TAKE_PROFIT), 2)
            sl_price = round(entry_price * (1 - STOP_LOSS), 2)
            tp_type = 'sell'
            sl_type = 'sell'
        else:
            tp_price = round(entry_price * (1 - TAKE_PROFIT), 2)
            sl_price = round(entry_price * (1 + STOP_LOSS), 2)
            tp_type = 'buy'
            sl_type = 'buy'

        timestamp = int(time.time())
        tp_id = f"tp_{timestamp}"
        sl_id = f"sl_{timestamp}"

        # Take Profit (limit order)
        tp_params = {
            "market": MARKET,
            "type": tp_type,
            "amount": amount,
            "price": tp_price,
            "client_id": tp_id
        }
        headers, signed_tp = sign(tp_params)
        r1 = requests.post(f"{API_BASE}/order/limit", json=signed_tp, headers=headers)
        results.append(("TP", r1.status_code, r1.text))

        # Stop Loss (stop market order)
        sl_params = {
            "market": MARKET,
            "type": sl_type,
            "amount": amount,
            "stop_price": sl_price,
            "stop_type": "loss",
            "client_id": sl_id
        }
        headers, signed_sl = sign(sl_params)
        r2 = requests.post(f"{API_BASE}/order/stop/market", json=signed_sl, headers=headers)
        results.append(("SL", r2.status_code, r2.text))

        # Lancer la surveillance
        threading.Thread(target=monitor_tp_sl, args=(tp_id, sl_id)).start()

        return results

    except Exception as e:
        return [("ERROR", 500, str(e))]

import threading

def monitor_tp_sl(tp_id: str, sl_id: str):
    try:
        while True:
            time.sleep(10)
            for client_id in [tp_id, sl_id]:
                headers, _ = sign({})
                r = requests.get(f"{API_BASE}/order/status?market={MARKET}&client_id={client_id}", headers=headers)
                if r.status_code == 200:
                    data = r.json()
                    if data['code'] == 0 and data['data']['status'] == 'done':
                        label = "Take Profit" if client_id.startswith("tp") else "Stop Loss"
                        executed_price = data['data']['deal_price']
                        send_telegram(f"✅ {label} exécuté à {executed_price} USDT")
                        cancel_other = sl_id if client_id == tp_id else tp_id
                        cancel_order(cancel_other)
                        return
    except Exception as e:
        send_telegram(f"❌ Erreur dans monitor_tp_sl: {e}")

def cancel_order(client_id: str):
    try:
        headers, signed = sign({"market": MARKET, "client_id": client_id})
        requests.delete(f"{API_BASE}/order/pending", headers=headers, params=signed)
    except Exception as e:
        send_telegram(f"⚠️ Erreur annulation {client_id} : {e}")

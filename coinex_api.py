import time
import json
import requests
import os
import ccxt
import hashlib
import hmac
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("API_KEY")
API_SECRET = os.getenv("API_SECRET")
MARKET = os.getenv("MARKET", "BTCUSDT")
TAKE_PROFIT = float(os.getenv("TAKE_PROFIT", 0.015))
STOP_LOSS = float(os.getenv("STOP_LOSS", 0.0075))
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

BASE_URL = "https://api.coinex.com/v2"

ccxt_exchange = ccxt.coinex({
    'apiKey': API_KEY,
    'secret': API_SECRET,
    'enableRateLimit': True,
    'options': {'defaultType': 'swap'}
})


def send_telegram(msg):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    data = {"chat_id": TELEGRAM_CHAT_ID, "text": msg}
    requests.post(url, data=data)


def sign_payload(payload):
    req_time = str(int(time.time() * 1000))
    payload_str = json.dumps(payload, separators=(',', ':'), ensure_ascii=False)
    signature = hmac.new(API_SECRET.encode(), (req_time + payload_str).encode(), hashlib.sha256).hexdigest()
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

        side = 'sell' if direction == 'long' else 'buy'
        stop_orders = []

        for label, price, stop_type in [("TP", tp_price, "take_profit"), ("SL", sl_price, "stop_loss")]:
            payload = {
                "market": MARKET,
                "side": side,
                "amount": str(amount),
                "stop_type": stop_type,
                "stop_price": str(price),
                "order_type": "market",
                "position_id": 0
            }
            headers = sign_payload(payload)
            r = requests.post(f"{BASE_URL}/futures/put_stop_order", headers=headers, data=json.dumps(payload))
            stop_orders.append((label, r.status_code, r.text))

        return stop_orders

    except Exception as e:
        send_telegram(f"❌ Erreur REST TP/SL : {e}")
        return [("ERROR", 500, str(e))]


def get_index_price():
    try:
        ticker = ccxt_exchange.fetch_ticker('BTC/USDT:USDT')
        mark_price = float(ticker['info'].get('mark_price') or ticker['last'])
        send_telegram(f"📈 Prix d’index actuel : {mark_price:.2f} USDT")
        return mark_price
    except Exception as e:
        send_telegram(f"⚠️ Erreur récupération prix index : {e}")
        return None


def adjust_amount_for_market(direction: str, desired_usdt_raw: float):
    index_price = get_index_price()
    if not index_price:
        send_telegram("⚠️ Impossible de récupérer le prix d’index pour ajuster la position.")
        return None, None

    try:
        try:
            desired_usdt = float(desired_usdt_raw)
            if desired_usdt <= 0:
                raise ValueError
        except:
            desired_usdt = 100
            send_telegram("⚠️ TRADE_AMOUNT invalide. Valeur par défaut 100 USDT utilisée.")

        symbol = 'BTC/USDT:USDT'
        market = ccxt_exchange.market(symbol)
        raw_amount = desired_usdt / index_price
        min_amount = float(market['limits']['amount']['min'])

        if raw_amount < min_amount:
            send_telegram(f"🚫 Montant brut trop faible : {raw_amount:.8f} BTC < min {min_amount} BTC. Trade ignoré.")
            return None, None

        amount = float(ccxt_exchange.amount_to_precision(symbol, raw_amount))
        side = 'buy' if direction == 'long' else 'sell'
        order = ccxt_exchange.create_market_order(symbol, side, amount, params={'reduceOnly': False})
        deal_price = float(order['average']) if order.get('average') else index_price
        send_telegram(f"✅ Position {direction.upper()} ouverte à {deal_price:.2f} USDT (via CCXT)")
        return deal_price, amount

    except Exception as e:
        send_telegram(f"❌ Erreur ouverture position : {e}")
        return None, None

import time
import json
import requests
import os
import ccxt
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("API_KEY")
API_SECRET = os.getenv("API_SECRET")
MARKET = os.getenv("MARKET", "BTCUSDT")
TAKE_PROFIT = float(os.getenv("TAKE_PROFIT", 0.015))
STOP_LOSS = float(os.getenv("STOP_LOSS", 0.0075))
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

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


def place_stop_orders_v2(direction: str, entry_price: float, amount: float):
    try:
        tp_price = round(entry_price * (1 + TAKE_PROFIT), 2) if direction == 'long' else round(entry_price * (1 - TAKE_PROFIT), 2)
        sl_price = round(entry_price * (1 - STOP_LOSS), 2) if direction == 'long' else round(entry_price * (1 + STOP_LOSS), 2)

        symbol = 'BTC/USDT:USDT'
        side = 'sell' if direction == 'long' else 'buy'
        stop_orders = []

        # TP
        tp_params = {
            'stopPrice': tp_price,
            'triggerPrice': tp_price,
            'reduceOnly': True,
            'type': 'market'
        }
        order_tp = ccxt_exchange.create_order(symbol, 'market', side, amount, None, tp_params)
        stop_orders.append(('TP', 200, str(order_tp)))

        # SL
        sl_params = {
            'stopPrice': sl_price,
            'triggerPrice': sl_price,
            'reduceOnly': True,
            'type': 'market'
        }
        order_sl = ccxt_exchange.create_order(symbol, 'market', side, amount, None, sl_params)
        stop_orders.append(('SL', 200, str(order_sl)))

        return stop_orders

    except Exception as e:
        send_telegram(f"❌ Erreur lors de la création des ordres TP/SL via CCXT : {e}")
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

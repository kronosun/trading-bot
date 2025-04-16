import os
import ccxt
import requests
import pandas as pd
import datetime
from dotenv import load_dotenv
from coinex_api import adjust_amount_for_market, place_stop_orders_v2

load_dotenv()

API_KEY = os.getenv("API_KEY")
API_SECRET = os.getenv("API_SECRET")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

exchange = ccxt.coinex({
    'apiKey': API_KEY,
    'secret': API_SECRET,
    'enableRateLimit': True
})

symbol = 'BTC/USDT'
leverage = int(os.getenv("LEVERAGE", 9))
usdt_amount = os.getenv("TRADE_AMOUNT", 100)
timeframe = os.getenv("TIMEFRAME", "1h")

def send_telegram(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    data = {"chat_id": TELEGRAM_CHAT_ID, "text": message}
    requests.post(url, data=data)

def fetch_ohlcv():
    send_telegram("📊 Récupération des données...")
    candles = exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=100)
    df = pd.DataFrame(candles, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
    return df

def calculate_indicators(df):
    send_telegram("📊 Analyse des indicateurs...")
    df['EMA20'] = df['close'].ewm(span=20).mean()
    df['EMA50'] = df['close'].ewm(span=50).mean()
    delta = df['close'].diff()
    gain = delta.where(delta > 0, 0).rolling(window=14).mean()
    loss = -delta.where(delta < 0, 0).rolling(window=14).mean()
    rs = gain / loss
    df['RSI'] = 100 - (100 / (1 + rs))
    return df

def decide_trade(df):
    rsi_oversold = int(os.getenv("RSI_OVERSOLD", 45))
    rsi_overbought = int(os.getenv("RSI_OVERBOUGHT", 65))

    latest = df.iloc[-1]

    if latest['EMA20'] > latest['EMA50'] and latest['RSI'] < rsi_oversold:
        return 'long'
    elif latest['EMA20'] < latest['EMA50'] and latest['RSI'] > rsi_overbought:
        return 'short'
    else:
        return None

def format_signal_explanation(df):
    rsi_oversold = int(os.getenv("RSI_OVERSOLD", 45))
    rsi_overbought = int(os.getenv("RSI_OVERBOUGHT", 65))
    latest = df.iloc[-1]

    rsi = latest['RSI']
    ema20 = latest['EMA20']
    ema50 = latest['EMA50']

    # Détection du signal
    if ema20 > ema50 and rsi < rsi_oversold:
        tendance = f"📈 EMA20 > EMA50 et RSI ({rsi:.2f}) < {rsi_oversold}"
        interpretation = "Tendance haussière possible. Signal LONG."
    elif ema20 < ema50 and rsi > rsi_overbought:
        tendance = f"📉 EMA20 < EMA50 et RSI ({rsi:.2f}) > {rsi_overbought}"
        interpretation = "Tendance baissière possible. Signal SHORT."
    else:
        if rsi < rsi_oversold:
            rsi_info = f"RSI ({rsi:.2f}) < {rsi_oversold}"
        elif rsi > rsi_overbought:
            rsi_info = f"RSI ({rsi:.2f}) > {rsi_overbought}"
        else:
            rsi_info = f"RSI ({rsi:.2f}) dans la zone neutre"
        tendance = f"➖ Pas de croisement EMA clair. {rsi_info}"
        interpretation = "Pas de signal."

    return f"""
📊 Analyse des moyennes mobiles :

- EMA20 : {ema20:.2f}
- EMA50 : {ema50:.2f}
- RSI : {rsi:.2f}

{tendance}
{interpretation}
"""

def place_order(direction):
    try:
        balance = exchange.fetch_balance()
        usdt_balance = balance['USDT']['free']
        leverage = int(os.getenv("LEVERAGE", 8))
        trade_amount_usdt = float(os.getenv("TRADE_AMOUNT", 100))
        amount_usdt = min(usdt_balance, trade_amount_usdt)

        entry_price, qty = adjust_amount_for_market(direction, amount_usdt)
        if not entry_price or not qty:
            return None, None

        result = place_stop_orders_v2(direction, entry_price, qty)
        for label, code, body in result:
            send_telegram(f"📋 {label} => HTTP {code}: {body}")

        tp_ratio = float(os.getenv("TAKE_PROFIT", 0.015))
        sl_ratio = float(os.getenv("STOP_LOSS", 0.0075))

        tp = round(entry_price * (1 + tp_ratio), 2) if direction == 'long' else round(entry_price * (1 - tp_ratio), 2)
        sl = round(entry_price * (1 - sl_ratio), 2) if direction == 'long' else round(entry_price * (1 + sl_ratio), 2)

        est_gain = abs(tp - entry_price) * qty
        est_loss = abs(entry_price - sl) * qty

        send_telegram(f"📌 Nouvelle position {direction.upper()} ouverte\n\nPrix d'entrée : {entry_price} USDT\nQuantité : {qty:.6f} BTC\nTP : {tp} USDT\nSL : {sl} USDT\nEffet de levier : x{leverage}\n\n🎯 Gain potentiel : {est_gain:.2f} USDT\n🛑 Risque max : {est_loss:.2f} USDT")

        return entry_price, direction

    except Exception as e:
        send_telegram(f"❌ Erreur place_order : {e}")
        return None, None

def close_position(direction):
    try:
        positions = exchange.fetch_positions([symbol])
        pos = next((p for p in positions if p['symbol'] == symbol), None)

        if pos and pos['contracts'] > 0:
            qty = pos['contracts']
            params = {'reduceOnly': True}
            if direction == 'long':
                send_telegram("🔄 Fermeture LONG")
                exchange.create_market_sell_order(symbol, qty, params)
            else:
                send_telegram("🔄 Fermeture SHORT")
                exchange.create_market_buy_order(symbol, qty, params)
        else:
            send_telegram("⚠️ Aucune position trouvée.")
    except Exception as e:
        send_telegram(f"❌ Erreur close_position : {e}")

def log_trade(direction, entry_price, profit):
    with open("trades_log.csv", "a") as file:
        line = f"{datetime.datetime.now()},{direction},{entry_price},{round(profit*100, 2)}%\n"
        file.write(line)

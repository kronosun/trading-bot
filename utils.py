import os
import ccxt
import requests
import pandas as pd
import datetime
from dotenv import load_dotenv
load_dotenv()


API_KEY = os.getenv("API_KEY")
API_SECRET = os.getenv("API_SECRET")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")


exchange = ccxt.bybit({
    'apiKey': API_KEY,
    'secret': API_SECRET,
    'enableRateLimit': True
})

symbol = 'BTC/USDT'
leverage = 9
usdt_amount = 100
timeframe = '1h'

def send_telegram(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    data = {"chat_id": TELEGRAM_CHAT_ID, "text": message}
    requests.post(url, data=data)

def fetch_ohlcv():
    send_telegram("Fetch ohlcv")
    candles = exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=100)
    df = pd.DataFrame(candles, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
    return df

def calculate_indicators(df):
    df['EMA20'] = df['close'].ewm(span=20).mean()
    df['EMA50'] = df['close'].ewm(span=50).mean()
    return df

def decide_trade(df):
    latest = df.iloc[-1]
    if latest['EMA20'] > latest['EMA50']:
        return 'long'
    elif latest['EMA20'] < latest['EMA50']:
        return 'short'
    return None


def place_order(direction):
    send_telegram("Place Order")
    price = exchange.fetch_ticker(symbol)['last']
    amount = usdt_amount / price
    params = {'leverage': leverage}
    send_telegram("Place Order")
    if direction == 'long':
        exchange.create_market_buy_order(symbol, amount, params)
    else:
        exchange.create_market_sell_order(symbol, amount, params)
    send_telegram(f"{direction.upper()} position ouverte à {price}")
    return price, direction


def format_signal_explanation(df):
    latest = df.iloc[-1]
    ema20 = latest['EMA20']
    ema50 = latest['EMA50']

    tendance = ""
    interpretation = ""

    if ema20 > ema50:
        tendance = "📈 La moyenne mobile courte (EMA20) est au-dessus de la longue (EMA50)."
        interpretation = "Cela indique une dynamique haussière. Le bot pourrait envisager une position LONG (achat)."
    elif ema20 < ema50:
        tendance = "📉 La moyenne mobile courte (EMA20) est en dessous de la longue (EMA50)."
        interpretation = "Cela reflète une dynamique baissière. Le bot pourrait envisager une position SHORT (vente)."
    else:
        tendance = "➖ Les deux moyennes sont égales."
        interpretation = "Il n'y a pas de signal clair. Le bot reste en attente."

    return f"""
📊 Analyse des moyennes mobiles :

- EMA20 (court terme) : {ema20:.2f}
- EMA50 (long terme) : {ema50:.2f}

{tendance}
{interpretation}
"""



def check_profit(entry_price, direction):
    TP_PERCENT = float(os.getenv("TP_PERCENT", 1.5))  # objectif de gain
    SL_PERCENT = float(os.getenv("SL_PERCENT", 1.0))  # stop loss

    current_price = exchange.fetch_ticker(symbol)['last']
    if direction == 'long':
        profit_percent = ((current_price - entry_price) / entry_price) * 100
    else:
        profit_percent = ((entry_price - current_price) / entry_price) * 100

    send_telegram(f"📉 Variation actuelle : {profit_percent:.2f}%")

    if profit_percent >= TP_PERCENT:
        send_telegram(f"🎯 Objectif de gain atteint : +{profit_percent:.2f}% ✅")
    elif profit_percent <= -SL_PERCENT:
        send_telegram(f"🛑 Limite de perte atteinte : {profit_percent:.2f}% ❌")

    return profit_percent

    if direction == 'long':
        profit_percent = ((current_price - entry_price) / entry_price) * 100
    else:
        profit_percent = ((entry_price - current_price) / entry_price) * 100

    # Affiche uniquement le pourcentage de variation
    send_telegram(f"📉 Variation actuelle : {profit_percent:.2f}%")

    return profit_percent

    SL_PERCENT = float(os.getenv("SL_PERCENT", 1.0))  # 1.0% par défaut

    current_price = exchange.fetch_ticker(symbol)['last']
    if direction == 'long':
        profit_percent = ((current_price - entry_price) / entry_price) * 100
    else:
        profit_percent = ((entry_price - current_price) / entry_price) * 100

    # Affichage dans les logs (Telegram ou fichier selon DEBUG)
    send_telegram(f"📉 Variation actuelle : {profit_percent:.2f}%")

    # Vérifie si le TP ou le SL est atteint
    if profit_percent >= TP_PERCENT:
        send_telegram(f"🎯 Objectif TP atteint ({profit_percent:.2f}%) ✅")
    elif profit_percent <= -SL_PERCENT:
        send_telegram(f"🛑 Stop Loss atteint ({profit_percent:.2f}%) ❌")

    return profit_percent

    return (current_price - entry_price) / entry_price if direction == 'long' else (entry_price - current_price) / entry_price

def log_trade(direction, entry_price, profit):
    with open("trades_log.csv", "a") as file:
        line = f"{datetime.datetime.now()},{direction},{entry_price},{round(profit*100, 2)}%\n"
        file.write(line)

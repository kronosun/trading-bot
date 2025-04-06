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
    send_telegram("Calculate indicators")
    EMA_FAST = int(os.getenv('EMA_FAST', 20))
    df['EMA_FAST'] = df['close'].ewm(span=EMA_FAST).mean()
    EMA_SLOW = int(os.getenv('EMA_SLOW', 50))
    df['EMA_SLOW'] = df['close'].ewm(span=EMA_SLOW).mean()
    delta = df['close'].diff()
    gain = delta.where(delta > 0, 0).rolling(window=14).mean()
    loss = -delta.where(delta < 0, 0).rolling(window=14).mean()
    rs = gain / loss
    df['RSI'] = 100 - (100 / (1 + rs))
    dm = ((df['high'] + df['low']) / 2).diff()
    br = df['volume'] / (df['high'] - df['low']).replace(0, 1)
    df['EMV'] = dm / br
    df['EMV'] = df['EMV'].rolling(window=14).mean()
    return df

def decide_trade(df):
    send_telegram("Decide Trade")
    latest = df.iloc[-1]
    if latest['RSI'] < 30 and latest['EMA_FAST'] > latest['EMA_SLOW'] and latest['EMV'] > 0:
        return 'long'
    elif latest['RSI'] > 70 and latest['EMA_FAST'] < latest['EMA_SLOW'] and latest['EMV'] < 0:
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
    return f"""
RSI : {latest['RSI']}
EMA_FAST : {latest['EMA_FAST']}
EMA_SLOW : {latest['EMA_SLOW']}
EMV : {latest['EMV']}
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

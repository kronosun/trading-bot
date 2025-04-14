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

exchange = ccxt.coinex({
    'apiKey': API_KEY,
    'secret': API_SECRET,
    'enableRateLimit': True,
    'options': {
        'defaultType': 'swap'
    }
})

symbol = 'BTC/USDT:USDT'
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
    latest = df.iloc[-1]
    rsi_oversold = int(os.getenv("RSI_OVERSOLD", 45))
    rsi_overbought = int(os.getenv("RSI_OVERBOUGHT", 65))

    if latest['RSI'] < rsi_oversold:
        return 'long'
    elif latest['RSI'] > rsi_overbought:
        return 'short'
    return None


def format_signal_explanation(df):
    rsi_oversold = int(os.getenv("RSI_OVERSOLD", 45))
    rsi_overbought = int(os.getenv("RSI_OVERBOUGHT", 65))
    latest = df.iloc[-1]

    if latest['RSI'] < rsi_oversold:
        tendance = "📈 RSI < 45"
        interpretation = "Tendance haussière possible. Signal LONG."
    elif latest['RSI'] > rsi_overbought:
        tendance = "📉 RSI > 65"
        interpretation = "Tendance baissière possible. Signal SHORT."
    else:
        tendance = "➖ Pas de tendance claire."
        interpretation = "Pas de signal."

    return f"""
📊 Analyse des moyennes mobiles :

- EMA20 : {latest['EMA20']:.2f}
- EMA50 : {latest['EMA50']:.2f}
- RSI : {latest['RSI']:.2f}

{tendance}
{interpretation}
"""

def place_order(direction):
    try:
        balance = exchange.fetch_balance()
        send_telegram(f"[DEBUG] Balance = {balance}")
        usdt_balance = balance['free']['USDT']
        leverage = int(os.getenv("LEVERAGE", 9))
        trade_amount_usdt = float(os.getenv("TRADE_AMOUNT", 100))
        amount_usdt = min(usdt_balance, trade_amount_usdt)

        market_price = exchange.fetch_ticker(symbol)['last']
        qty = amount_usdt / market_price
        params = {'leverage': leverage}
        send_telegram("📤 Place Order [REEL]")

        if direction == 'long':
            send_telegram("ℹ️ LONG Buy Order")
            exchange.options['createMarketBuyOrderRequiresPrice'] = False
            exchange.create_order(symbol, 'market', 'buy', amount_usdt, None, params)
        else:
            send_telegram("ℹ️ SHORT Sell Order")
            exchange.create_market_sell_order(symbol, qty, params)

        send_telegram(f"{direction.upper()} position ouverte à {market_price}")
        return market_price, direction

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

def check_profit(entry_price, direction):
    try:
        current_price = exchange.fetch_ticker(symbol)['last']
        send_telegram(f"Prix actuel : {current_price}")

        if direction == 'long':
            return (current_price - entry_price) / entry_price
        else:
            return (entry_price - current_price) / entry_price
    except Exception as e:
        send_telegram(f"[ERREUR] check_profit: {e}")
        return 0

def log_trade(direction, entry_price, profit):
    with open("trades_log.csv", "a") as file:
        line = f"{datetime.datetime.now()},{direction},{entry_price},{round(profit*100, 2)}%\n"
        file.write(line)

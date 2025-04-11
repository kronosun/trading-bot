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
    'enableRateLimit': True
})

symbol = 'BTC/USDT'
leverage = int(os.getenv("LEVERAGE", 9))
usdt_amount = os.getenv("TRADE_AMOUNT", 100)
timeframe = '1h'

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
    dm = ((df['high'] + df['low']) / 2).diff()
    br = df['volume'] / (df['high'] - df['low']).replace(0, 1)
    df['EMV'] = dm / br
    df['EMV'] = df['EMV'].rolling(window=14).mean()
    return df

def decide_trade(df):
    rsi_oversold = int(os.getenv("RSI_OVERSOLD", 30))
    rsi_overbought = int(os.getenv("RSI_OVERBOUGHT", 70))
    emv_threshold = float(os.getenv("EMV_THRESHOLD", 0))

    latest = df.iloc[-1]
    rsi = round(latest['RSI'], 2)
    ema20 = latest['EMA20']
    ema50 = latest['EMA50']
    emv = round(latest['EMV'], 4)

    if rsi < rsi_oversold and ema20 > ema50 and emv > emv_threshold:
        return 'long'
    elif rsi > rsi_overbought and ema20 < ema50 and emv < -emv_threshold:
        return 'short'
    else:
        return None

def format_signal_explanation(df):
    rsi_oversold = int(os.getenv("RSI_OVERSOLD", 30))
    rsi_overbought = int(os.getenv("RSI_OVERBOUGHT", 70))
    emv_threshold = float(os.getenv("EMV_THRESHOLD", 0))

    latest = df.iloc[-1]
    rsi = round(latest['RSI'], 2)
    ema20 = latest['EMA20']
    ema50 = latest['EMA50']
    emv = round(latest['EMV'], 4)

    tendance = ""
    interpretation = ""

    if rsi < rsi_oversold and ema20 > ema50 and emv > emv_threshold:
        tendance = "📈 La moyenne mobile courte (EMA20) est au-dessus de la longue (EMA50)."
        interpretation = "Cela indique une dynamique haussière. Le bot pourrait envisager une position LONG (achat)."
    elif rsi > rsi_overbought and ema20 < ema50 and emv < -emv_threshold:
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

def place_order(direction):
    try:
        # Chargement du marché pour obtenir la limite minimale
        # markets = exchange.load_markets()
        # min_qty = markets[symbol]['limits']['amount']['min']

        balance = exchange.fetch_balance()
        usdt_balance = balance['USDT']['free']
        leverage = int(os.getenv("LEVERAGE", 9))
        trade_amount_usdt = float(os.getenv("TRADE_AMOUNT", 100))
        amount_usdt = min(usdt_balance, trade_amount_usdt)

        market_price = exchange.fetch_ticker(symbol)['last']
        #qty = round((amount_usdt * leverage) / market_price, 6)

        # Assure un minimum requis par la plateforme
        #if qty < min_qty:
        #    send_telegram(f"❌ Quantité {qty:.6f} inférieure au minimum autorisé {min_qty} pour {symbol}")
        #    return None, None

        params = {'leverage': leverage}
        qty = amount_usdt / market_price
        #send_telegram(f"⚠️ ATTENTION : Levier utilisé = {leverage}x. Tu risques une liquidation plus rapide si le marché va dans le mauvais sens.")
        #send_telegram(f"💵 Montant estimé de l’ordre : {amount_usdt:.2f} USDT → {qty:.6f} {symbol.split('/')[0]} à {market_price:.2f} USD")
        ##send_telegram(f"ℹ️ Quantité minimale autorisée : {min_qty}")          
        send_telegram("📤 Place Order [REEL]")

        if direction == 'long':
            send_telegram("ℹ️ LONG Buy Order")
            exchange.options['createMarketBuyOrderRequiresPrice'] = False
            exchange.create_order(symbol, 'market', 'buy', amount_usdt, None, params)
            #exchange.create_market_buy_order(symbol, qty, params)
        else:
            send_telegram("ℹ️ SHORT Sell Order")
            exchange.create_market_sell_order(symbol, qty, params)

        send_telegram(f"{direction.upper()} position ouverte à {market_price}")
        return market_price, direction

    except Exception as e:
        send_telegram(f"❌ Erreur place_order : {e}")
        return None, None


def check_profit(entry_price, direction):
    try:
        current_price = exchange.fetch_ticker(symbol)['last']
        send_telegram(f"Prix actuel : {current_price}")

        if direction == 'long':
            profit_percent = ((current_price - entry_price) / entry_price) * 100
        else:
            profit_percent = ((entry_price - current_price) / entry_price) * 100

        send_telegram(f"📉 Variation actuelle : {profit_percent:.2f}%")

        return (current_price - entry_price) / entry_price if direction == 'long' else (entry_price - current_price) / entry_price
    except Exception as e:
        send_telegram(f"[ERREUR] check_profit: {e}")
        return 0


def log_trade(direction, entry_price, profit):
    with open("trades_log.csv", "a") as file:
        line = f"{datetime.datetime.now()},{direction},{entry_price},{round(profit*100, 2)}%\n"
        file.write(line)

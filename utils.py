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
    try:
        # Chargement du marché pour obtenir la limite minimale
        markets = exchange.load_markets()
        min_qty = markets[symbol]['limits']['amount']['min']

        balance = exchange.fetch_balance()
        usdt_balance = balance['USDT']['free']
        leverage = int(os.getenv("LEVERAGE", 9))
        trade_amount_usdt = float(os.getenv("TRADE_AMOUNT", 100))
        amount_usdt = min(usdt_balance, trade_amount_usdt)

        market_price = exchange.fetch_ticker(symbol)['last']
        qty = round((amount_usdt * leverage) / market_price, 6)

        # Assure un minimum requis par la plateforme
        if qty < min_qty:
            send_telegram(f"❌ Quantité {qty:.6f} inférieure au minimum autorisé {min_qty} pour {symbol}")
            return None, None

        params = {'leverage': leverage}

        send_telegram("📤 Place Order")
        send_telegram(f"⚠️ ATTENTION : Levier utilisé = {leverage}x. Tu risques une liquidation plus rapide si le marché va dans le mauvais sens.")
        send_telegram(f"💵 Montant estimé de l’ordre : {amount_usdt:.2f} USDT → {qty:.6f} {symbol.split('/')[0]} à {market_price:.2f} USD")
        send_telegram(f"ℹ️ Quantité minimale autorisée : {min_qty}")

        if direction == 'long':
            exchange.create_market_buy_order(symbol, qty, params)
        else:
            exchange.create_market_sell_order(symbol, qty, params)

        send_telegram(f"{direction.upper()} position ouverte à {market_price}")
        return market_price, direction

    except Exception as e:
        send_telegram(f"❌ Erreur place_order : {e}")
        return None, None


def check_profit(entry_price, direction):
    TP_PERCENT = float(os.getenv("TP_PERCENT", 2.0))
    SL_PERCENT = float(os.getenv("SL_PERCENT", 1.0))

    current_price = exchange.fetch_ticker(symbol)['last']
    if direction == 'long':
        profit_percent = ((current_price - entry_price) / entry_price) * 100
    else:
        profit_percent = ((entry_price - current_price) / entry_price) * 100

    send_telegram(f"📉 Variation actuelle : {profit_percent:.2f}%")

    if profit_percent >= TP_PERCENT:
        send_telegram(f"[TAKE PROFIT] +{profit_percent:.2f}% ✅")
        log_trade(direction, entry_price, profit_percent)
        return 'tp'

    elif profit_percent <= -SL_PERCENT:
        send_telegram(f"[STOP LOSS] {profit_percent:.2f}% ❌")
        log_trade(direction, entry_price, profit_percent)
        return 'sl'

    return None


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


def log_trade(direction, entry_price, profit):
    with open("trades_log.csv", "a") as file:
        line = f"{datetime.datetime.now()},{direction},{entry_price},{round(profit*100, 2)}%\n"
        file.write(line)

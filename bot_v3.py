
import os
import time
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Updater, CommandHandler, CallbackContext



def balance_command(update: Update, context: CallbackContext):
    try:
        balance = exchange.fetch_balance()
        usdt_balance = balance['total'].get('USDT', 0)
        update.message.reply_text(f"💰 Balance USDT : {usdt_balance:.2f}")
    except Exception as e:
        update.message.reply_text(f"Erreur dans /balance : {e}")



def config_command(update: Update, context: CallbackContext):
    try:
        with open(".env", "r") as f:
            lines = f.readlines()
        response = "🛠️ Configuration actuelle :\n" + "".join(lines)
        update.message.reply_text(response)
    except Exception as e:
        update.message.reply_text(f"Erreur dans /config : {e}")

def set_command(update: Update, context: CallbackContext):
    try:
        args = context.args
        if len(args) < 2:
            update.message.reply_text("Usage : /set <clé> <valeur>")
            return
        key, value = args[0], " ".join(args[1:])
        lines = []
        found = False
        with open(".env", "r") as f:
            for line in f:
                if line.startswith(f"{key}="):
                    lines.append(f"{key}={value}\n")
                    found = True
                else:
                    lines.append(line)
        if not found:
            lines.append(f"{key}={value}\n")
        with open(".env", "w") as f:
            f.writelines(lines)
        update.message.reply_text(f"✅ Modifié : {key} = {value}")
    except Exception as e:
        update.message.reply_text(f"Erreur dans /set : {e}")

def restart_command(update: Update, context: CallbackContext):
    update.message.reply_text("♻️ Redémarrage du bot...")
    os.execv(__file__, ['python'] + sys.argv)

def stop_command(update: Update, context: CallbackContext):
    update.message.reply_text("🛑 Bot arrêté par commande /stop.")
    remove_lock()
    os._exit(0)


def signal_command(update: Update, context: CallbackContext):
    try:
        df = fetch_ohlcv()
        df = calculate_indicators(df)
        explanation = format_signal_explanation(df)
        update.message.reply_text(explanation)
    except Exception as e:
        update.message.reply_text(f"Erreur dans /signal : {e}")

from utils import (
    fetch_ohlcv, calculate_indicators, decide_trade,
    place_order, check_profit, send_telegram, log_trade, format_signal_explanation
)

LOCKFILE = "bot.lock"

load_dotenv()
CHECK_INTERVAL_MINUTES = int(os.getenv("CHECK_INTERVAL_MINUTES", 60))
DEBUG = os.getenv("DEBUG", "true").lower() == "true"


def is_already_running():
    return os.path.exists(LOCKFILE)

def create_lock():
    with open(LOCKFILE, "w") as f:
        f.write("running")

def remove_lock():
    if os.path.exists(LOCKFILE):
        os.remove(LOCKFILE)

def run_bot():
    if is_already_running():
        print("Bot already running. Exiting.")
        return

    create_lock()
    send_telegram("🤖 BOT V3 lancé en mode daemon.")
    try:
        while True:
            try:
                df = fetch_ohlcv()
                df = calculate_indicators(df)
                
                
                signal = decide_trade(df)
                explanation = format_signal_explanation(df)
                send_telegram(f"📊 Analyse complète :\n\n{explanation}")

                
                if signal:
                    explanation = format_signal_explanation(df)
                    send_telegram(f"📊 Analyse complète :\n\n{explanation}")

                    if DEBUG:
                        send_telegram(f"🔧 DEBUG : Simulation de trade {signal.upper()}")
                    else:
                        send_telegram("📤 Placement d'un ordre réel...")
                        try:
                            entry_price, direction = place_order(signal)
                            if not entry_price or not direction:
                                send_telegram("⚠️ Le trade n’a pas été exécuté. Passage au cycle suivant.")
                                return
                            send_telegram(f"Trade {direction.upper()} exécuté à {entry_price}")
                            for _ in range(60):  # 60 minutes de suivi
                                time.sleep(60)
                                profit = check_profit(entry_price, direction)
                                send_telegram(f"💰 Profit actuel : {profit:.2f}%")
                                log_trade(entry_price, profit, direction)
                        except Exception as e:
                            send_telegram(f"❌ Erreur place_order : {e}")
                else:
                    send_telegram("❌ Aucun signal valide pour ce cycle.")

            except Exception as e:
                send_telegram(f"❌ Erreur pendant l'exécution : {str(e)}")

            send_telegram(f"⏳ Nouvelle vérification dans {CHECK_INTERVAL_MINUTES} min.")
            time.sleep(CHECK_INTERVAL_MINUTES * 60)
    finally:
        remove_lock()

if __name__ == '__main__':
    from telegram.ext import Updater

    TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
    updater = Updater(token=TELEGRAM_TOKEN, use_context=True)
    dispatcher = updater.dispatcher

    dispatcher.add_handler(CommandHandler("signal", signal_command))
    dispatcher.add_handler(CommandHandler("balance", balance_command))
    dispatcher.add_handler(CommandHandler("config", config_command))
    dispatcher.add_handler(CommandHandler("set", set_command))
    dispatcher.add_handler(CommandHandler("restart", restart_command))
    dispatcher.add_handler(CommandHandler("stop", stop_command))

    updater.start_polling()
    run_bot()
    updater.idle()

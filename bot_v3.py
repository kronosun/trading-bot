import os
import time
import threading
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Updater, CommandHandler, CallbackContext
from utils import (
    fetch_ohlcv, calculate_indicators, decide_trade,
    place_order, send_telegram, log_trade, format_signal_explanation,
    close_position, exchange
)
from coinex_api import place_stop_orders_v2

LOCKFILE = "bot.lock"
PAUSE_FILE = "bot.pause"

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

def is_paused():
    return os.path.exists(PAUSE_FILE)

def pause_command(update: Update, context: CallbackContext):
    with open(PAUSE_FILE, "w") as f:
        f.write("paused")
    update.message.reply_text("⏸️ Bot mis en pause.")

def resume_command(update: Update, context: CallbackContext):
    if os.path.exists(PAUSE_FILE):
        os.remove(PAUSE_FILE)
    update.message.reply_text("▶️ Bot relancé.")

def stop_command(update: Update, context: CallbackContext):
    update.message.reply_text("🛑 Arrêt du bot demandé.")
    remove_lock()
    os._exit(0)

def restart_command(update: Update, context: CallbackContext):
    update.message.reply_text("♻️ Redémarrage du bot...")
    remove_lock()
    os.execv(sys.executable, [sys.executable] + sys.argv)

def status_command(update: Update, context: CallbackContext):
    paused = os.path.exists("bot.pause")
    try:
        with open(".last_trade", "r") as f:
            last = f.read().strip()
    except:
        last = "aucun"
    msg = f"🟡 Bot {'⏸️ en pause' if paused else '✅ actif'}\n📅 Dernier trade : {last}"
    update.message.reply_text(msg)

def balance_command(update: Update, context: CallbackContext):
    try:
        balance = exchange.fetch_balance()
        usdt = balance['total'].get('USDT', 0)
        btc = balance['total'].get('BTC', 0)
        update.message.reply_text(f"💰 Solde :\n- USDT : {usdt:.2f}\n- BTC : {btc:.6f}")
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
        updated = False
        lines = []
        if os.path.exists(".env"):
            with open(".env", "r") as f:
                for line in f:
                    if line.strip().startswith(f"{key}="):
                        lines.append(f"{key}={value}\n")
                        updated = True
                    else:
                        lines.append(line)
        if not updated:
            lines.append(f"{key}={value}\n")
        with open(".env", "w") as f:
            f.writelines(lines)
        update.message.reply_text(f"✅ Modifié : {key} = {value}")
    except Exception as e:
        update.message.reply_text(f"Erreur dans /set : {e}")

def signal_command(update: Update, context: CallbackContext):
    try:
        df = fetch_ohlcv()
        df = calculate_indicators(df)
        explanation = format_signal_explanation(df)
        update.message.reply_text(explanation)
    except Exception as e:
        update.message.reply_text(f"Erreur dans /signal : {e}")

def run_bot():
    if is_already_running():
        print("Bot already running. Exiting.")
        return

    create_lock()
    send_telegram("🤖 BOT V3 lancé en mode daemon.")

    try:
        while True:
            if is_paused():
                send_telegram("⏸️ Bot en pause. Nouvelle vérification dans 1 minute.")
                time.sleep(60)
                continue

            try:
                df = fetch_ohlcv()
                df = calculate_indicators(df)
                signal = decide_trade(df)
                explanation = format_signal_explanation(df)
                send_telegram(f"📊 Analyse complète :\n\n{explanation}")

                if signal:
                    if DEBUG:
                        send_telegram(f"🔧 DEBUG : Simulation de trade {signal.upper()}")
                    else:
                        send_telegram("📤 Placement d'un ordre réel...")
                        try:
                            entry_price, direction = place_order(signal)
                            if not entry_price or not direction:
                                send_telegram("⚠️ Le trade n’a pas été exécuté.")
                            else:
                                if entry_price == 0:
                                    send_telegram("🚫 Solde insuffisant pour ouvrir une position.")
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
    import sys
    TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
    updater = Updater(token=TELEGRAM_TOKEN, use_context=True)
    dispatcher = updater.dispatcher

    dispatcher.add_handler(CommandHandler("signal", signal_command))
    dispatcher.add_handler(CommandHandler("balance", balance_command))
    dispatcher.add_handler(CommandHandler("config", config_command))
    dispatcher.add_handler(CommandHandler("set", set_command))
    dispatcher.add_handler(CommandHandler("restart", restart_command))
    dispatcher.add_handler(CommandHandler("stop", stop_command))
    dispatcher.add_handler(CommandHandler("pause", pause_command))
    dispatcher.add_handler(CommandHandler("resume", resume_command))
    dispatcher.add_handler(CommandHandler("status", status_command))

    updater.start_polling()

    thread = threading.Thread(target=run_bot)
    thread.start()

    updater.idle()

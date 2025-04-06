
# 🤖 Bot de Trading Bybit (Telegram + Analyse Technique)

Ce bot réalise des analyses techniques automatisées sur Bybit, prend des décisions de trade, et te tient informé en temps réel via Telegram.

---

## 🚀 Fonctionnalités

- Mode daemon (intervalle régulier configurable)
- Analyse technique complète (RSI, EMA20/50, EMV)
- Interprétation pédagogique après chaque analyse
- Passage d'ordre réel ou simulation (mode debug)
- Commandes Telegram : `/signal`, `/balance`, `/config`, `/set`, `/restart`, `/stop`
- Suivi des trades en live avec calcul du profit
- Notifications en cas de TP ou SL atteint

---

## ⚙️ Configuration `.env`

Voici un exemple de fichier `.env` :

```env
# Clés API Bybit
API_KEY=your_api_key_here
API_SECRET=your_api_secret_here

# Bot Telegram
TELEGRAM_TOKEN=your_telegram_bot_token
TELEGRAM_CHAT_ID=your_chat_id

# Fonctionnement général
DEBUG=true
CHECK_INTERVAL_MINUTES=60
TRADE_AMOUNT=100
TRADE_AMOUNT_MODE=fixed  # ou percent

# Indicateurs techniques
RSI_PERIOD=14
EMA_FAST=20
EMA_SLOW=50

# Paramètres Take Profit / Stop Loss
TP_PERCENT=2
SL_PERCENT=1
```

---

## 📦 Déploiement Render.com

1. Crée un repo GitHub avec ces fichiers :
   - `bot_v3.py`
   - `utils.py`
   - `.env`
   - `requirements.txt`
   - `render.yaml`

2. Va sur [https://render.com](https://render.com) → "New" → "Web Service"  
3. Connecte ton repo, Render détectera automatiquement le type de projet

---

## 📬 Commandes Telegram disponibles

| Commande    | Description                                  |
|-------------|----------------------------------------------|
| `/signal`   | Affiche l'analyse technique actuelle         |
| `/balance`  | Affiche la balance USDT                      |
| `/profit`   | Affiche le PnL cumulé (à ajouter si besoin)  |
| `/config`   | Affiche la configuration actuelle du bot     |
| `/set`      | Modifie un paramètre `.env` à distance       |
| `/restart`  | Redémarre le bot                             |
| `/stop`     | Stoppe le bot                                |

---

## 📈 À savoir

- Le bot n’intervient **pas automatiquement** pour fermer les positions (TP/SL)
- Il envoie simplement des **notifications pédagogiques** via Telegram


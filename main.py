import os
import time
import json
import requests
from flask import Flask, request
from telegram import Bot, Update, ReplyKeyboardMarkup
from telegram.ext import Dispatcher, CommandHandler, MessageHandler, Filters

TOKEN = os.environ.get("TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")
WEBHOOK_URL = os.environ.get("WEBHOOK_URL")

app = Flask(__name__)
bot = Bot(token=TOKEN)
dispatcher = Dispatcher(bot=bot, update_queue=None, workers=1, use_context=True)

# Клавиатура
keyboard = ReplyKeyboardMarkup(
    keyboard=[
        ["📡 Проверить курс", "📊 Диапазон 52 недель"]
    ],
    resize_keyboard=True,
    one_time_keyboard=False
)

def get_current_ratio():
    url = "https://api.coingecko.com/api/v3/simple/price?ids=ripple,stellar&vs_currencies=usd"
    response = requests.get(url).json()
    try:
        price_xrp = response["ripple"]["usd"]
        price_xlm = response["stellar"]["usd"]
        return round(price_xrp / price_xlm, 2), price_xrp
    except KeyError:
        return None, None

def get_52_week_range():
    now = int(time.time())
    year_ago = now - 365 * 24 * 60 * 60
    xlm_url = f"https://api.coingecko.com/api/v3/coins/stellar/market_chart/range?vs_currency=usd&from={year_ago}&to={now}"
    xrp_url = f"https://api.coingecko.com/api/v3/coins/ripple/market_chart/range?vs_currency=usd&from={year_ago}&to={now}"
    try:
        xlm_prices = requests.get(xlm_url).json().get("prices", [])
        xrp_prices = requests.get(xrp_url).json().get("prices", [])
        ratios = [round(xrp[1] / xlm[1], 2) for xrp, xlm in zip(xrp_prices, xlm_prices)]
        return min(ratios), max(ratios)
    except:
        return None, None

def get_usd_to_rub():
    try:
        url = "https://api.coingecko.com/api/v3/simple/price?ids=usd&vs_currencies=rub"
        return requests.get(url).json()["usd"]["rub"]
    except:
        return None

def start(update, context):
    update.message.reply_text(
        "Выберите действие:",
        reply_markup=keyboard
    )

def handle_message(update, context):
    text = update.message.text

    if text == "📡 Проверить курс":
        ratio, xrp_price = get_current_ratio()
        rub = get_usd_to_rub()
        if ratio and rub:
            rub_price = round(xrp_price * rub, 2)
            usd_price = round(xrp_price, 2)
            update.message.reply_text(
                f"📡 1 XRP = {ratio} XLM ≈ {usd_price} USD ≈ {rub_price} ₽",
                reply_markup=keyboard
            )
        else:
            update.message.reply_text("⚠️ Не удалось получить данные.", reply_markup=keyboard)

    elif text == "📊 Диапазон 52 недель":
        low, high = get_52_week_range()
        if low and high:
            update.message.reply_text(
                f"📊 Диапазон за 52 недели:\nМинимум: {low} XLM\nМаксимум: {high} XLM",
                reply_markup=keyboard
            )
        else:
            update.message.reply_text("⚠️ Не удалось получить данные за 52 недели.", reply_markup=keyboard)
    else:
        update.message.reply_text("Выберите кнопку ниже ⬇️", reply_markup=keyboard)

@app.route("/")
def index():
    return "Bot is alive"

@app.route("/webhook", methods=["POST"])
def webhook():
    update = Update.de_json(request.get_json(force=True), bot)
    dispatcher.process_update(update)
    return "OK"

def setup():
    bot.set_webhook(url=f"{WEBHOOK_URL}/webhook")
    dispatcher.add_handler(CommandHandler("start", start))
    dispatcher.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_message))

if __name__ == "__main__":
    setup()
    app.run(host="0.0.0.0", port=10000)


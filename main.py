import os
import time
import json
import requests
import logging
from flask import Flask, request
from telegram import Bot, Update, ReplyKeyboardMarkup
from telegram.ext import Dispatcher, CommandHandler, MessageHandler, Filters

# Логирование
logging.basicConfig(level=logging.INFO)

# Переменные окружения
TOKEN = os.environ.get("TOKEN")
WEBHOOK_URL = os.environ.get("WEBHOOK_URL")

# Telegram
app = Flask(__name__)
bot = Bot(token=TOKEN)
dispatcher = Dispatcher(bot, update_queue=None, workers=1, use_context=True)

# Клавиатура
keyboard = ReplyKeyboardMarkup(
    [["📡 Проверить курс", "📊 Диапазон 52 недель"]],
    resize_keyboard=True
)

# Кэш
cache = {
    "week_range": None,
    "week_cached_at": 0
}

# Получение курсов
def get_current_ratio():
    try:
        url = "https://api.coingecko.com/api/v3/simple/price?ids=ripple,stellar&vs_currencies=usd"
        response = requests.get(url, timeout=10).json()
        price_xrp = response["ripple"]["usd"]
        price_xlm = response["stellar"]["usd"]
        return round(price_xrp / price_xlm, 2), price_xrp
    except Exception as e:
        logging.warning(f"Ошибка в get_current_ratio: {e}")
        return None, None

def get_usd_to_rub():
    try:
        data = requests.get("https://api.coingecko.com/api/v3/simple/price?ids=usd&vs_currencies=rub", timeout=10).json()
        return data["usd"]["rub"]
    except Exception as e:
        logging.warning(f"Ошибка в get_usd_to_rub: {e}")
        return None

def get_52_week_range():
    now = int(time.time())
    if now - cache["week_cached_at"] < 86400 and cache["week_range"]:
        return cache["week_range"]

    year_ago = now - 365 * 24 * 60 * 60
    try:
        xlm_url = f"https://api.coingecko.com/api/v3/coins/stellar/market_chart/range?vs_currency=usd&from={year_ago}&to={now}"
        xrp_url = f"https://api.coingecko.com/api/v3/coins/ripple/market_chart/range?vs_currency=usd&from={year_ago}&to={now}"

        xlm_data = requests.get(xlm_url, timeout=20).json().get("prices", [])
        xrp_data = requests.get(xrp_url, timeout=20).json().get("prices", [])

        ratios = [round(y[1] / x[1], 2) for x, y in zip(xlm_data, xrp_data) if x[1] and y[1]]
        if not ratios:
            raise ValueError("Пустой массив ratios")

        cache["week_range"] = (min(ratios), max(ratios))
        cache["week_cached_at"] = now
        return cache["week_range"]
    except Exception as e:
        logging.error(f"Ошибка в get_52_week_range: {e}")
        return None, None

# Команды
def start(update, context):
    update.message.reply_text("Выберите действие:", reply_markup=keyboard)

def handle_message(update, context):
    text = update.message.text

    if text == "📡 Проверить курс":
        ratio, price = get_current_ratio()
        rub = get_usd_to_rub()
        if ratio and rub:
            rub_value = round(price * rub, 2)
            usd_value = round(price, 2)
            update.message.reply_text(f"📡 1 XRP = {ratio} XLM ≈ {usd_value} USD ≈ {rub_value} ₽", reply_markup=keyboard)
        else:
            update.message.reply_text("⚠️ Не удалось получить курс. Попробуйте позже.", reply_markup=keyboard)

    elif text == "📊 Диапазон 52 недель":
        low, high = get_52_week_range()
        if low and high:
            update.message.reply_text(f"📊 Диапазон за 52 недели:\nМин: {low} XLM\nМакс: {high} XLM", reply_markup=keyboard)
        else:
            update.message.reply_text("⚠️ Не удалось получить диапазон. Попробуйте позже.", reply_markup=keyboard)

    else:
        update.message.reply_text("Нажмите кнопку ниже ⬇️", reply_markup=keyboard)

# Webhook
@app.route("/")
def home():
    return "OK"

@app.route("/webhook", methods=["POST"])
def webhook():
    update = Update.de_json(request.get_json(force=True), bot)
    dispatcher.process_update(update)
    return "OK"

def setup():
    bot.set_webhook(f"{WEBHOOK_URL}/webhook")
    dispatcher.add_handler(CommandHandler("start", start))
    dispatcher.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_message))

if __name__ == "__main__":
    setup()
    app.run(host="0.0.0.0", port=10000)



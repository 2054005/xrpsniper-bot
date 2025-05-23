import os
import time
import json
import requests
from flask import Flask, request
from telegram import Bot, Update, ReplyKeyboardMarkup
from telegram.ext import Dispatcher, CommandHandler, MessageHandler, Filters

TOKEN = os.environ.get("TOKEN")
WEBHOOK_URL = os.environ.get("WEBHOOK_URL")

app = Flask(__name__)
bot = Bot(token=TOKEN)
dispatcher = Dispatcher(bot, update_queue=None, workers=1, use_context=True)

keyboard = ReplyKeyboardMarkup(
    [["📡 Проверить курс", "📊 Диапазон 52 недель"]],
    resize_keyboard=True
)

CACHE_FILE = "cache.json"

def load_cache():
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE, "r") as f:
            return json.load(f)
    return {}

def save_cache(data):
    with open(CACHE_FILE, "w") as f:
        json.dump(data, f)

def get_current_ratio():
    cache = load_cache()
    now = time.time()

    if "ratio" in cache and now - cache["ratio"]["ts"] < 300:
        return cache["ratio"]["value"], cache["ratio"]["price"]

    try:
        url = "https://api.coingecko.com/api/v3/simple/price?ids=ripple,stellar&vs_currencies=usd"
        response = requests.get(url, timeout=5).json()
        price_xrp = response["ripple"]["usd"]
        price_xlm = response["stellar"]["usd"]
        ratio = round(price_xrp / price_xlm, 2)

        cache["ratio"] = {"value": ratio, "price": price_xrp, "ts": now}
        save_cache(cache)
        return ratio, price_xrp
    except Exception as e:
        if "ratio" in cache:
            return cache["ratio"]["value"], cache["ratio"]["price"]
        return None, None

def get_usd_to_rub():
    try:
        data = requests.get("https://api.coingecko.com/api/v3/simple/price?ids=usd&vs_currencies=rub", timeout=5).json()
        return data["usd"]["rub"]
    except:
        return None

def get_52_week_range():
    cache = load_cache()
    now = time.time()

    if "range" in cache and now - cache["range"]["ts"] < 6 * 3600:
        return cache["range"]["low"], cache["range"]["high"]

    try:
        year_ago = now - 365 * 24 * 60 * 60
        xlm_url = f"https://api.coingecko.com/api/v3/coins/stellar/market_chart/range?vs_currency=usd&from={year_ago}&to={now}"
        xrp_url = f"https://api.coingecko.com/api/v3/coins/ripple/market_chart/range?vs_currency=usd&from={year_ago}&to={now}"

        xlm_data = requests.get(xlm_url, timeout=10).json().get("prices", [])
        xrp_data = requests.get(xrp_url, timeout=10).json().get("prices", [])

        ratios = []
        for x, y in zip(xlm_data, xrp_data):
            if x[1] > 0:
                ratios.append(round(y[1] / x[1], 2))

        if ratios:
            low = min(ratios)
            high = max(ratios)
            cache["range"] = {"low": low, "high": high, "ts": now}
            save_cache(cache)
            return low, high
    except Exception as e:
        print("Ошибка диапазона:", e)

    if "range" in cache:
        return cache["range"]["low"], cache["range"]["high"]

    return None, None

def start(update, context):
    update.message.reply_text(
        "Выберите действие:",
        reply_markup=keyboard
    )

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
            update.message.reply_text("⚠️ Не удалось получить курс.", reply_markup=keyboard)

    elif text == "📊 Диапазон 52 недель":
        low, high = get_52_week_range()
        if low and high:
            update.message.reply_text(f"📊 Диапазон 52 недель:\nМин: {low} XLM\nМакс: {high} XLM", reply_markup=keyboard)
        else:
            update.message.reply_text("⚠️ Ошибка получения диапазона", reply_markup=keyboard)
    else:
        update.message.reply_text("Нажмите кнопку ниже ⬇️", reply_markup=keyboard)

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


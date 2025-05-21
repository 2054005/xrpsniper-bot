import os
import json
import requests
from flask import Flask, request
from telegram import Bot, Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Dispatcher, CommandHandler, CallbackQueryHandler

TOKEN = os.environ.get("TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")

bot = Bot(token=TOKEN)
app = Flask(__name__)
dispatcher = Dispatcher(bot=bot, update_queue=None, workers=1, use_context=True)

STATE_FILE = "state.json"


def get_current_ratio():
    url = "https://api.coingecko.com/api/v3/simple/price?ids=ripple,stellar&vs_currencies=usd"
    data = requests.get(url).json()
    if "ripple" not in data or "stellar" not in data:
        raise ValueError(f"Ошибка API CoinGecko: {data}")
    price_xrp = data["ripple"]["usd"]
    price_xlm = data["stellar"]["usd"]
    return round(price_xrp / price_xlm, 2), price_xrp


def get_usd_to_rub():
    try:
        url = "https://api.coingecko.com/api/v3/simple/price?ids=usd&vs_currencies=rub"
        return requests.get(url).json()["usd"]["rub"]
    except:
        return None


def start(update, context):
    keyboard = [[
        InlineKeyboardButton("📡 Проверить курс", callback_data="scan")
    ], [InlineKeyboardButton("📊 Диапазон 52 недель", callback_data="stats")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    update.message.reply_text("Выберите действие:", reply_markup=reply_markup)


def scan(update, context):
    try:
        ratio, xrp_price = get_current_ratio()
        usd = round(xrp_price, 2)
        rub = get_usd_to_rub()
        rub_value = round(xrp_price * rub, 2) if rub else "?"
        update.message.reply_text(f"📡 1 XRP = {ratio} XLM ≈ {usd} USD ≈ {rub_value} ₽")
    except Exception as e:
        update.message.reply_text(f"⚠️ Ошибка: {e}")


def button_callback(update, context):
    query = update.callback_query
    query.answer()
    try:
        if query.data == "scan":
            ratio, xrp_price = get_current_ratio()
            usd = round(xrp_price, 2)
            rub = get_usd_to_rub()
            rub_value = round(xrp_price * rub, 2) if rub else "?"
            query.edit_message_text(f"📡 1 XRP = {ratio} XLM ≈ {usd} USD ≈ {rub_value} ₽")
        elif query.data == "stats":
            query.edit_message_text("⚠️ 52-недельный диапазон не реализован в Webhook-версии.")
    except Exception as e:
        query.edit_message_text(f"⚠️ Ошибка: {e}")


@app.route('/')
def hello():
    return '✅ Бот работает через Webhook!'


@app.route(f"/webhook", methods=["POST"])
def webhook():
    update = Update.de_json(request.get_json(force=True), bot)
    dispatcher.process_update(update)
    return 'ok'


def setup_handlers():
    dispatcher.add_handler(CommandHandler("start", start))
    dispatcher.add_handler(CommandHandler("scan", scan))
    dispatcher.add_handler(CallbackQueryHandler(button_callback))


if __name__ == '__main__':
    setup_handlers()
    webhook_url = os.environ.get("WEBHOOK_URL")  # задаётся в Render
    if webhook_url:
        bot.set_webhook(f"{webhook_url}/webhook")
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))

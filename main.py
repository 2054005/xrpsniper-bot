
import requests
import json
import time
import logging
import asyncio
import nest_asyncio
from flask import Flask
from threading import Thread
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram import Bot as TelegramBot
from telegram.ext import (
    ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes
)

nest_asyncio.apply()

TOKEN = "PASTE_YOUR_TELEGRAM_BOT_TOKEN_HERE"
CHAT_ID = "PASTE_YOUR_TELEGRAM_CHAT_ID"
STATE_FILE = "state.json"

app = Flask("")

@app.route("/")
def home():
    return "Bot is alive!"

def run():
    app.run(host="0.0.0.0", port=8080)

def keep_alive():
    Thread(target=run).start()

def get_current_ratio():
    url = "https://api.coingecko.com/api/v3/simple/price?ids=ripple,stellar&vs_currencies=usd"
    response = requests.get(url)
    data = response.json()
    price_xrp = data["ripple"]["usd"]
    price_xlm = data["stellar"]["usd"]
    return round(price_xrp / price_xlm, 2), price_xrp

def get_52_week_range():
    now = int(time.time())
    year_ago = now - 365 * 24 * 60 * 60
    xlm_url = f"https://api.coingecko.com/api/v3/coins/stellar/market_chart/range?vs_currency=usd&from={year_ago}&to={now}"
    xrp_url = f"https://api.coingecko.com/api/v3/coins/ripple/market_chart/range?vs_currency=usd&from={year_ago}&to={now}"
    try:
        xlm_data = requests.get(xlm_url).json().get("prices", [])
        xrp_data = requests.get(xrp_url).json().get("prices", [])
        ratios = []
        for i in range(min(len(xlm_data), len(xrp_data))):
            try:
                xlm_price = xlm_data[i][1]
                xrp_price = xrp_data[i][1]
                ratio = round(xrp_price / xlm_price, 2)
                ratios.append(ratio)
            except:
                continue
        return (min(ratios), max(ratios)) if ratios else (None, None)
    except:
        return None, None

def get_usd_to_rub():
    try:
        url = "https://api.coingecko.com/api/v3/simple/price?ids=usd&vs_currencies=rub"
        return requests.get(url).json()["usd"]["rub"]
    except:
        return None

def load_state():
    try:
        with open(STATE_FILE, "r") as f:
            return json.load(f)
    except FileNotFoundError:
        return {"last_ratio": None}

def save_state(state):
    with open(STATE_FILE, "w") as f:
        json.dump(state, f)

def get_main_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📡 Проверить курс", callback_data="scan")],
        [InlineKeyboardButton("📊 Диапазон 52 недель", callback_data="stats")]
    ])

async def check_ratio(bot: TelegramBot):
    current_ratio, xrp_price = get_current_ratio()
    state = load_state()
    last_ratio = state.get("last_ratio")
    if last_ratio is None:
        state["last_ratio"] = current_ratio
        save_state(state)
        return
    if int(current_ratio) != int(last_ratio):
        low, high = get_52_week_range()
        usd_to_rub = get_usd_to_rub()
        rub_price = round(xrp_price * usd_to_rub, 2) if usd_to_rub else "?"
        usd_price = round(xrp_price, 2)
        message = (
            f"📢 Изменение курса XLM/XRP:
"
            f"Было: 1 XRP = {last_ratio} XLM
"
            f"Стало: 1 XRP = {current_ratio} XLM
"
            f"💵 ≈ {usd_price} USD ≈ {rub_price} ₽\n\n"
        )
        if low and high:
            message += (
                f"📊 52-недельный минимум: {low} XLM\n"
                f"📈 52-недельный максимум: {high} XLM"
            )
        await bot.send_message(chat_id=CHAT_ID, text=message)
        state["last_ratio"] = current_ratio
        save_state(state)

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Выберите действие:", reply_markup=get_main_keyboard())

async def scan_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ratio, xrp_price = get_current_ratio()
    rub = get_usd_to_rub()
    usd = round(xrp_price, 2)
    rub_value = round(xrp_price * rub, 2) if rub else "?"
    text = f"📡 1 XRP = {ratio} XLM\n💵 ≈ {usd} USD ≈ {rub_value} ₽"
    await update.message.reply_text(text, reply_markup=get_main_keyboard())

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data == "scan":
        ratio, xrp_price = get_current_ratio()
        rub = get_usd_to_rub()
        usd = round(xrp_price, 2)
        rub_value = round(xrp_price * rub, 2) if rub else "?"
        text = f"📡 1 XRP = {ratio} XLM\n💵 ≈ {usd} USD ≈ {rub_value} ₽"
        await query.edit_message_text(text, reply_markup=get_main_keyboard())
    elif query.data == "stats":
        low, high = get_52_week_range()
        if low and high:
            text = f"📊 Диапазон за 52 недели:\n🔻 Минимум: {low} XLM\n🔺 Максимум: {high} XLM"
        else:
            text = "⚠️ Не удалось получить данные за 52 недели."
        await query.edit_message_text(text, reply_markup=get_main_keyboard())

async def background_loop(bot: TelegramBot):
    while True:
        await check_ratio(bot)
        await asyncio.sleep(3600)

async def main():
    logging.basicConfig(level=logging.INFO)
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("scan", scan_command))
    app.add_handler(CallbackQueryHandler(button_callback))
    asyncio.create_task(background_loop(app.bot))
    await app.run_polling()

if __name__ == "__main__":
    keep_alive()
    asyncio.get_event_loop().run_until_complete(main())

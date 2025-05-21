import requests
import json
import time
import logging
import asyncio
import nest_asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram import Bot as TelegramBot
from telegram.ext import (ApplicationBuilder, CommandHandler,
                          CallbackQueryHandler, ContextTypes)

nest_asyncio.apply()

import os
TOKEN = os.environ["TOKEN"]
CHAT_ID = os.environ["CHAT_ID"]
STATE_FILE = "state.json"

def get_current_ratio():
    url = "https://api.coingecko.com/api/v3/simple/price?ids=ripple,stellar&vs_currencies=usd"
    response = requests.get(url)
    data = response.json()

    # Защита от ошибки отсутствия данных
    if "ripple" not in data or "stellar" not in data:
        raise ValueError(f"Не удалось получить данные. Ответ: {data}")

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

def load_state():
    try:
        with open(STATE_FILE, "r") as f:
            return json.load(f)
    except FileNotFoundError:
        return {"last_ratio": None}

def save_state(state):
    with open(STATE_FILE, "w") as f:
        json.dump(state, f)

def get_usd_to_rub():
    try:
        url = "https://api.coingecko.com/api/v3/simple/price?ids=usd&vs_currencies=rub"
        return requests.get(url).json()["usd"]["rub"]
    except:
        return None

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
        usd_price = round(xrp_price, 2)
        rub_price = round(xrp_price * usd_to_rub, 2) if usd_to_rub else "?"

        message = (
            f"📢 Изменение курса XLM/XRP:\n"
            f"Было: 1 XRP = {last_ratio} XLM\n"
            f"Стало: 1 XRP = {current_ratio} XLM\n"
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

# Команды и кнопки
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [[
        InlineKeyboardButton("📡 Проверить курс", callback_data="scan")
    ], [InlineKeyboardButton("📊 Диапазон 52 недель", callback_data="stats")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Выберите действие:", reply_markup=reply_markup)

async def scan_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ratio, xrp_price = get_current_ratio()
    rub = get_usd_to_rub()
    usd_value = round(xrp_price, 2)
    rub_value = round(xrp_price * rub, 2) if rub else "?"
    await update.message.reply_text(f"📡 1 XRP = {ratio} XLM ≈ {usd_value} USD ≈ {rub_value} ₽")

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "scan":
        ratio, xrp_price = get_current_ratio()
        rub = get_usd_to_rub()
        usd_value = round(xrp_price, 2)
        rub_value = round(xrp_price * rub, 2) if rub else "?"
        await query.edit_message_text(f"📡 1 XRP = {ratio} XLM ≈ {usd_value} USD ≈ {rub_value} ₽")

    elif query.data == "stats":
        low, high = get_52_week_range()
        if low and high:
            await query.edit_message_text(f"📊 Диапазон за 52 недели:\n"
                                          f"Минимум: {low} XLM\n"
                                          f"Максимум: {high} XLM")
        else:
            await query.edit_message_text("⚠️ Не удалось получить данные за 52 недели.")

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
    asyncio.get_event_loop().run_until_complete(main())


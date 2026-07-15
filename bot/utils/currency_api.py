import aiohttp
import logging
import re
from aiogram import types
from config import COMMAND_METADATA
from bot.utils.database import db
from bot.utils.helpers import format_styled_message, spend_tokens, get_raw_text

API_ICON = COMMAND_METADATA["!курс"]["icon"]
API_NAME = COMMAND_METADATA["!курс"]["name"]

logger = logging.getLogger(__name__)

CURRENCY_API_URL = "https://open.er-api.com/v6/latest/"

CURRENCY_MAP = {
    "RUB": ["rub", "руб", "рубль", "рублей", "рубля", "р", "₽"],
    "USD": ["usd", "доллар", "долларов", "доллара", "бакс", "баксов", "бакса", "$"],
    "EUR": ["eur", "евро", "euro", "€"],
    "KZT": ["kzt", "тенге", "тнг", "₸"],
    "UAH": ["uah", "гривна", "гривен", "гривну", "грн", "₴"],
    "BYN": ["byn", "белруб", "зайчик", "беларусь"],
    "GBP": ["gbp", "фунт", "фунтов", "£"],
    "CNY": ["cny", "юань", "юаней", "¥"],
}


def parse_currency_input(text: str):
    text = re.sub(r"\b(в|переведи|сколько|будет)\b", "", text.lower())
    words = text.split()

    amount = 1.0
    from_curr = None
    to_curr = None

    for i, word in enumerate(words):
        if re.match(r"^\d+(\.\d+)?$", word.replace(",", ".")):
            amount = float(word.replace(",", "."))
            words.pop(i)
            break

    def identify_currency(word):
        for code, synonyms in CURRENCY_MAP.items():
            if word in synonyms:
                return code
        return None

    found_currencies = []
    for word in words:
        code = identify_currency(word)
        if code and code not in found_currencies:
            found_currencies.append(code)

    if len(found_currencies) >= 2:
        from_curr, to_curr = found_currencies[0], found_currencies[1]
    elif len(found_currencies) == 1:
        from_curr = found_currencies[0]
        to_curr = "RUB" if from_curr != "RUB" else "USD"

    return amount, from_curr, to_curr


async def get_exchange_rate(base: str) -> dict:
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(f"{CURRENCY_API_URL}{base}") as response:
                if response.status == 200:
                    return await response.json()
                return None
        except Exception as e:
            logger.error(f"Ошибка API валют: {e}")
            return None


async def cmd_currency(message: types.Message):
    raw_text = get_raw_text(message)
    args = raw_text.split(maxsplit=1) if raw_text else []

    if len(args) < 2:
        error_msg = format_styled_message(
            emoji=API_ICON,
            title=API_NAME,
            message="❌ <b>Не указан запрос.</b>\n📝 Пример: <code>!курс 100 баксов в рубли</code>\nИли просто: <code>!курс 500 тенге</code>",
        )
        await message.reply(error_msg)
        return

    amount, from_curr, to_curr = parse_currency_input(args[1])

    if not from_curr or not to_curr:
        error_msg = format_styled_message(
            emoji=API_ICON,
            title=API_NAME,
            message="❌ <b>Не удалось распознать валюты.</b>\nПоддерживаются: $, €, ₽, ₸, ₴, £, ¥ и их текстовые названия.",
        )
        await message.reply(error_msg)
        return

    status_msg = await message.reply(
        format_styled_message(
            emoji="⏳", title=API_NAME, message="Запрашиваю свежий курс..."
        )
    )

    data = await get_exchange_rate(from_curr)

    if not data or "rates" not in data or to_curr not in data["rates"]:
        await status_msg.edit_text(
            format_styled_message(
                emoji="❌", title=API_NAME, message="Ошибка получения курса с сервера."
            )
        )
        return

    rate = data["rates"][to_curr]
    result = amount * rate

    amount_str = f"{amount:,.2f}".replace(",", " ").rstrip("0").rstrip(".")
    result_str = f"{result:,.2f}".replace(",", " ")

    text = (
        f"💸 <b>Конвертация:</b>\n"
        f"<code>{amount_str} {from_curr}</code> ➔ <code>{result_str} {to_curr}</code>\n\n"
        f"📊 <b>Курс:</b> 1 {from_curr} = {rate:.4f} {to_curr}\n"
        f"🕒 <i>Данные обновлены сегодня</i>"
    )

    await status_msg.edit_text(
        format_styled_message(emoji=API_ICON, title=API_NAME, message=text)
    )

    await db.increment_commands()
    await db.log_command("!курс", message.from_user.id)
    await spend_tokens(message, "!курс")

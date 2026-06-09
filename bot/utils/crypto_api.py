import aiohttp
import logging
import time
from aiogram import types
from config import COMMAND_METADATA
from aiogram.types import InlineKeyboardButton
from bot.utils.database import db
from bot.utils.helpers import format_styled_message, create_user_keyboard, spend_tokens

API_ICON = COMMAND_METADATA["!курс_крипты"]["icon"]
API_NAME = COMMAND_METADATA["!курс_крипты"]["name"]

logger = logging.getLogger(__name__)

_cache = {
    "rates": None,
    "timestamp": 0
}
CACHE_TTL = 30


async def get_top_crypto_rates(limit=5):
    current_time = time.time()

    if _cache["rates"] and (current_time - _cache["timestamp"] < CACHE_TTL):
        return _cache["rates"]

    url = "https://api.coingecko.com/api/v3/coins/markets"
    params = {
        "vs_currency": "usd",
        "order": "market_cap_desc",
        "per_page": 250,
        "page": 1,
        "sparkline": "false"
    }

    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()

                    exclude_symbols = {'usdt', 'usdc', 'dai', 'fdusd', 'wbtc', 'steth', 'reth', 'cbeth'}

                    valid_assets = []
                    for item in data:
                        symbol = item.get("symbol", "").lower()
                        price = item.get("current_price")

                        if price and symbol not in exclude_symbols:
                            valid_assets.append({
                                "name": item.get("name", "Unknown"),
                                "symbol": symbol.upper(),
                                "price": float(price)
                            })

                    valid_assets.sort(key=lambda x: x['price'], reverse=True)

                    rates_text = []
                    for item in valid_assets[:limit]:
                        price_str = f"{item['price']:,.2f}".replace(',', ' ')
                        rates_text.append(f"<b>{item['name']} [{item['symbol']}]</b> ➔ <code>${price_str}</code>")

                    _cache["rates"] = rates_text
                    _cache["timestamp"] = current_time

                    return rates_text
                elif response.status == 429:
                    logger.warning("CoinGecko API: Превышен лимит запросов (429).")
                    if _cache["rates"]:
                        return _cache["rates"]
        except Exception as e:
            logger.error(f"Ошибка API CoinGecko: {e}")
            if _cache["rates"]:
                return _cache["rates"]
            return None

    return None


def get_crypto_keyboard(user_id: int):
    return create_user_keyboard([
        [InlineKeyboardButton(text="🔄 Обновить курсы", callback_data="more_crypto")]
    ], user_id)


async def send_crypto(target, is_callback=False):
    rates_lines = await get_top_crypto_rates(limit=5)

    if not rates_lines:
        error_msg = format_styled_message(
            emoji="❌", 
            title="Ошибка", 
            message="Не удалось получить данные. API временно недоступно."
        )
        if is_callback:
            await target.message.answer(error_msg)
        else:
            await target.reply(error_msg)
        return False

    text = "\n".join(rates_lines)

    msg_text = format_styled_message(
        emoji=API_ICON,
        title=API_NAME,
        message=text
    )

    user_id = target.from_user.id
    keyboard = get_crypto_keyboard(user_id)

    try:
        message_obj = target.message if is_callback else target

        if is_callback:
            await message_obj.edit_text(msg_text, reply_markup=keyboard)
        else:
            await message_obj.reply(msg_text, reply_markup=keyboard)

        if not is_callback:
            await db.increment_commands()
            await db.log_command("!курс_крипты", user_id)
            await spend_tokens(message_obj, "!курс_крипты")

        return True
    except Exception as e:
        logger.error(f"Ошибка отправки крипты: {e}")
        return False


async def cmd_crypto(message: types.Message):
    await send_crypto(message)


async def more_crypto_callback(callback_query: types.CallbackQuery):
    await callback_query.answer("🔄 Запрашиваю свежие данные...")
    await send_crypto(callback_query, is_callback=True)

import aiohttp
import asyncio
import logging
import random
from aiogram import types
from config import COMMAND_METADATA
from aiogram.types import InlineKeyboardButton
from bot.utils.database import db
from bot.utils.helpers import format_styled_message, create_user_keyboard, spend_tokens

API_ICON = COMMAND_METADATA["!цитата"]["icon"]
API_NAME = COMMAND_METADATA["!цитата"]["name"]

logger = logging.getLogger(__name__)

BACKUP_QUOTES = [
    "Никогда не сдавайся, сдаются только квартиры. © Джейсон Стэйтем",
    "Делай, что должен, и будь, что будет. © Марк Аврелий",
    "Успех — это способность шагать от одной неудачи к другой, не теряя энтузиазма. © Уинстон Черчилль",
    "Нельзя вернуться в прошлое и изменить свой старт, но можно стартовать сейчас и изменить свой финиш. © Рой Джонс",
    "Чем умнее человек, тем легче он признает себя дураком. © Альберт Эйнштейн",
    "Если вы думаете, что на что-то способны, вы правы; если думаете, что ни на что не способны — вы тоже правы. © Генри Форд",
    "Лучший способ предсказать будущее — создать его. © Питер Друкер",
    "Сложнее всего начать действовать, все остальное зависит только от упорства. © Амелия Эрхарт",
]


async def get_random_quote():
    url = "http://api.forismatic.com/api/1.0/?method=getQuote&format=json&lang=ru"
    timeout = aiohttp.ClientTimeout(total=2.0)

    try:
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(url) as response:
                if response.status == 200:
                    data = await response.json(content_type=None)
                    quote = data.get("quoteText", "").strip()
                    author = data.get("quoteAuthor", "").strip() or "Неизвестный автор"
                    return f"{quote}\n\n© <i>{author}</i>"
    except asyncio.TimeoutError:
        logger.warning("API цитат долго отвечает (таймаут). Выдана резервная цитата.")
    except Exception as e:
        logger.error(f"Ошибка API цитат: {e}")

    return random.choice(BACKUP_QUOTES)


def get_quote_keyboard(user_id: int):
    return create_user_keyboard(
        [[InlineKeyboardButton(text="💭 Ещё цитата", callback_data="more_quote")]],
        user_id,
    )


async def send_quote(target, is_callback=False):
    quote_text = await get_random_quote()

    msg_text = format_styled_message(emoji=API_ICON, title=API_NAME, message=quote_text)

    user_id = target.from_user.id
    keyboard = get_quote_keyboard(user_id)

    try:
        message_obj = target.message if is_callback else target

        if is_callback:
            await message_obj.edit_text(msg_text, reply_markup=keyboard)
        else:
            await message_obj.reply(msg_text, reply_markup=keyboard)

        await db.increment_commands()
        await db.log_command("!цитата", user_id)
        await spend_tokens(message_obj, "!цитата")

    except Exception as e:
        logger.error(f"Ошибка отправки цитаты: {e}")


async def cmd_quote(message: types.Message):
    await send_quote(message)


async def more_quote_callback(callback_query: types.CallbackQuery):
    await callback_query.answer("🔄 Ищу порцию мудрости...")
    await send_quote(callback_query, is_callback=True)

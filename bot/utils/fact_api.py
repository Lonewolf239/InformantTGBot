import aiohttp
import logging
from aiogram import types
from config import COMMAND_METADATA
from aiogram.types import InlineKeyboardButton
from bot.utils.database import db
from bot.utils.helpers import format_styled_message, create_user_keyboard, spend_tokens

API_ICON = COMMAND_METADATA["!факт"]["icon"]
API_NAME = COMMAND_METADATA["!факт"]["name"]

logger = logging.getLogger(__name__)


async def get_random_fact():
    url = "https://ru.wikipedia.org/api/rest_v1/page/random/summary"
    headers = {
        "User-Agent": "InformantBot/1.0 (https://t.me/Lonewolf239_informantBOT) aiohttp/3.8"
    }

    async with aiohttp.ClientSession(headers=headers) as session:
        try:
            async with session.get(url) as response:
                if response.status == 200:
                    data = await response.json()
                    title = data.get("title", "")
                    extract = data.get("extract", "")
                    if extract:
                        return f"<b>{title}</b>\n\n{extract}"
                else:
                    logger.error(f"Ошибка API Википедии: HTTP {response.status}")
        except Exception as e:
            logger.error(f"Ошибка API Википедии: {e}")
            return None


def get_fact_keyboard(user_id: int):
    return create_user_keyboard([
        [InlineKeyboardButton(text="📖 Ещё факт", callback_data="more_fact")]
    ], user_id)


async def cmd_fact(message: types.Message):
    fact_text = await get_random_fact()

    if not fact_text:
        error_msg = format_styled_message(
            emoji="❌",
            title="Ошибка",
            message="Не удалось загрузить факт. Попробуй позже!"
        )
        await message.reply(error_msg)
        return True

    fact_msg = format_styled_message(
        emoji=API_ICON,
        title=API_NAME,
        message=fact_text
    )

    await message.reply(fact_msg, reply_markup=get_fact_keyboard(message.from_user.id))

    await db.increment_commands()
    await db.log_command("!факт", message.from_user.id)
    await spend_tokens(message, "!факт")
    return True


async def more_fact_callback(callback_query: types.CallbackQuery):
    await callback_query.answer("🔄 Загружаю новый факт...")

    fact_text = await get_random_fact()
    if fact_text:
        fact_msg = format_styled_message(
            emoji=API_ICON,
            title=API_NAME,
            message=fact_text
        )
        await callback_query.message.edit_text(
            fact_msg,
            reply_markup=get_fact_keyboard(callback_query.from_user.id)
        )

        await spend_tokens(message, "!факт")
    else:
        await callback_query.message.edit_text(
            format_styled_message(emoji="❌", title="Ошибка", message="API Википедии недоступен."),
            reply_markup=get_fact_keyboard(callback_query.from_user.id)
        )

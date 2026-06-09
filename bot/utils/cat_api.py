import aiohttp
import logging
from aiogram import types
from aiogram.types import InlineKeyboardButton
from config import COMMAND_METADATA
from bot.utils.database import db
from bot.utils.helpers import format_styled_message, create_user_keyboard, spend_tokens

API_ICON = COMMAND_METADATA["!кот"]["icon"]
API_NAME = COMMAND_METADATA["!кот"]["name"]

logger = logging.getLogger(__name__)


async def get_random_cat():
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get("https://api.thecatapi.com/v1/images/search") as response:
                if response.status == 200:
                    data = await response.json()
                    if data and isinstance(data, list) and "url" in data[0]:
                        return data[0]["url"]
        except Exception as e:
            logger.error(f"Ошибка API котиков: {e}")
            return None


def get_cat_keyboard(user_id: int):
    return create_user_keyboard([
        [InlineKeyboardButton(text="🐱 Ещё котика", callback_data="more_cat")]
    ], user_id)


async def send_cat(target, is_callback=False):
    url = await get_random_cat()

    if not url:
        error_msg = format_styled_message(
            emoji="❌",
            title=API_NAME,
            message="Котики спрятались! Попробуй позже."
        )
        if is_callback:
            await target.message.answer(error_msg)
        else:
            await target.reply(error_msg)
        return

    caption = format_styled_message(
        emoji=API_ICON,
        title=API_NAME,
        message="Держи пушистого!"
    )
    reply_markup = get_cat_keyboard(target.from_user.id)

    try:
        message_obj = target.message if is_callback else target

        if url.endswith(".gif"):
            await message_obj.reply_animation(animation=url, caption=caption, reply_markup=reply_markup)
        else:
            await message_obj.reply_photo(photo=url, caption=caption, reply_markup=reply_markup)

        await db.increment_commands()
        await db.log_command("!кот", target.from_user.id)
        await spend_tokens(message_obj, "!кот")

    except Exception as e:
        logger.error(f"Ошибка при отправке котика: {e}")


async def cmd_cat(message: types.Message):
    await send_cat(message)


async def more_cat_callback(callback_query: types.CallbackQuery):
    await callback_query.answer("🔄 Ищу нового котика...")
    await send_cat(callback_query, is_callback=True)

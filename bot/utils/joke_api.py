import random
import aiohttp
from aiogram import types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from config import USER_PROFILE, API_SETTINGS, BACKUP_JOKES
from bot.utils.database import db
from bot.utils.helpers import format_styled_message
import logging

API_ICON = "🎭"
API_NAME = "Анекдот"

logger = logging.getLogger(__name__)


async def get_joke_from_api():
    try:
        import asyncio
        import anecdotica as acalib

        loop = asyncio.get_event_loop()
        reply = await loop.run_in_executor(
            None, 
            lambda: acalib.RandomItemApi.get_reply(USER_PROFILE, API_SETTINGS)
        )

        if reply.is_error():
            error_msg = reply.get_result().get_error()
            logger.error(f"Ошибка API анекдотов: {error_msg}")
            return None

        joke_text = reply.get_item().get_text()
        joke_note = reply.get_item().get_note()

        if joke_note:
            return f"{joke_text}\n\n📝 {joke_note}"
        return joke_text

    except Exception as e:
        logger.error(f"Ошибка при получении анекдота: {e}")
        return None


def get_backup_joke():
    return random.choice(BACKUP_JOKES)


def get_joke_keyboard():
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎭 Ещё анекдот", callback_data="more_joke")]
    ])
    return keyboard


async def cmd_joke(message: types.Message):
    try:
        joke = await get_joke_from_api()
        if joke:
            joke_msg = format_styled_message(
                emoji=API_ICON,
                title=API_NAME,
                message=joke
            )
            await message.reply(joke_msg, reply_markup=get_joke_keyboard())
            db.increment_jokes()
            return True

        backup = get_backup_joke()
        backup_msg = format_styled_message(
            emoji=API_ICON,
            title=f"{API_NAME} (локальный)",
            message=f"{backup}\n⚠️ <i>API недоступен</i>"
        )
        await message.reply(backup_msg)
        db.increment_jokes()
        return True

    except Exception as e:
        logger.error(f"Ошибка в !анекдот: {e}")
        error_msg = format_styled_message(
            emoji="❌",
            title="Ошибка",
            message="Не удалось получить анекдот. Попробуй позже!"
        )
        await message.reply(error_msg)
        return True


async def more_joke_callback(callback_query: types.CallbackQuery):
    await callback_query.answer("🔄 Загружаю новый анекдот...")

    joke = await get_joke_from_api()
    if joke:
        joke_msg = format_styled_message(
            emoji=API_ICON,
            title=API_NAME,
            message=joke
        )
        await callback_query.message.edit_text(
            joke_msg,
            reply_markup=get_joke_keyboard()
        )
        db.increment_jokes()
    else:
        backup = get_backup_joke()
        backup_msg = format_styled_message(
            emoji=API_ICON,
            title=f"{API_NAME} (локальный)",
            message=f"{backup}\n⚠️ <i>API недоступен</i>"
        )
        await callback_query.message.edit_text(
            backup_msg,
            reply_markup=get_joke_keyboard()
        )
        db.increment_jokes()

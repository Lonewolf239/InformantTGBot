from aiogram import types
from aiogram.exceptions import TelegramNetworkError
from aiogram.fsm.context import FSMContext
from bot.handlers.owner import process_owner_commands
from bot.handlers.public import process_public_commands
from bot.handlers.rp import process_rp_command
from bot.handlers.auto_reply import check_auto_reply
from bot.links.handlers import process_incoming_link
from bot.utils.helpers import its_me
from config import WELCOME_TEXT
from bot.utils.database import db
from bot.state import AIChatMode
from bot.utils.ai_api import process_chat_message
import logging

logger = logging.getLogger(__name__)


async def safe_reply(message: types.Message, text: str, **kwargs):
    try:
        return await message.reply(text, **kwargs)
    except Exception as e:
        logger.error(
            f"Ошибка при отправке сообщения пользователю {message.from_user.id}: {e}"
        )
        return None


async def handle_all_messages(message: types.Message, state: FSMContext = None):
    if not message.from_user:
        return

    if state:
        current_state = await state.get_state()
        if current_state == AIChatMode.in_chat.state:
            await process_chat_message(message, state)
            return

    user = message.from_user
    user_id = message.from_user.id
    username = user.username or f"{user.first_name}_{user.id}"
    user_link = f"tg://user?id={user.id}"

    is_new_user = await db.get_user_stats(user_id) is None
    await db.increment_total_messages()
    await db.update_user_message(user.id, username, user_link)

    if is_new_user and not its_me(user_id):
        await safe_reply(message, WELCOME_TEXT)

    try:
        if message.text or message.caption:
            if its_me(user_id):
                if await process_owner_commands(message):
                    return

            if await process_public_commands(message, state):
                return

            if message.reply_to_message:
                if await process_rp_command(message):
                    return

            if not its_me(user_id):
                if await process_incoming_link(message):
                    return

        if not its_me(user_id):
            await check_auto_reply(message)

    except TelegramNetworkError as e:
        logger.warning(f"Сетевая ошибка Telegram API (таймаут): {e}")

    except Exception as e:
        logger.error(f"Ошибка в handle_all_messages: {e}", exc_info=True)
        await safe_reply(message, "❌ Произошла внутренняя ошибка")

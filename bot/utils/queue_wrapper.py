import logging
from aiogram import types
from bot.utils.helpers import format_styled_message
from bot.utils.task_queue import queue_manager

logger = logging.getLogger(__name__)


async def process_with_queue(message: types.Message, queue_name: str, icon: str, title: str, action_text: str, func, *args, **kwargs):
    status_msg = await message.reply(
        format_styled_message(
            emoji=icon,
            title=title,
            message=f"⏳ {action_text}...\n📍 Позиция: вычисляется"
        )
    )

    async def update_position(pos: int):
        try:
            if pos == 0:
                text = f"🔄 <b>В процессе...</b>\n{action_text}"
            else:
                text = f"⏳ <b>Запрос в очереди.</b>\n📍 Позиция перед вами: {pos}"

            await status_msg.edit_text(format_styled_message(emoji=icon, title=title, message=text))
        except Exception:
            pass

    try:
        future, queue_position = await queue_manager.add_task(queue_name, func, *args, update_cb=update_position, **kwargs)
        await update_position(queue_position)

        result = await future
        return result, status_msg

    except Exception as e:
        logger.error(f"Ошибка в процессе выполнения: {e}")
        error_msg = format_styled_message(emoji="❌", title=title, message="Произошла непредвиденная ошибка.")
        await status_msg.edit_text(error_msg)
        return None, status_msg

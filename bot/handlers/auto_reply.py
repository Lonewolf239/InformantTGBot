import random
from bot.state import state
from bot.utils.helpers import its_me
from config import AWAY_MESSAGES
from bot.utils.database import db


async def check_auto_reply(message):
    user_id = message.from_user.id

    if its_me(user_id):
        return

    if await state.is_away_mode:
        await state.add_awaiting_user(
            user_id,
            message.from_user.first_name or "Неизвестный",
            message.from_user.username
        )

        if await state.should_send_auto_reply(user_id):
            away_msg = f"<b>┌─ 🤖 АВТООТВЕТЧИК</b>\n└─ {random.choice(AWAY_MESSAGES)}"
            await message.reply(away_msg)
            await db.increment_auto_replies()
            await db.mark_auto_reply_sent(user_id, away_msg)

from aiogram import types
from aiogram.types import InlineKeyboardButton
from config import OWNER_ID
from bot.twin.database import twin_db
from bot.utils.helpers import create_user_keyboard
from bot.owner_settings.config_getters import is_twin_feedback_enabled

FEEDBACK_OPTIONS = [
    ("good", "✅ это я"),
    ("maybe", "🟡 мог бы так"),
    ("bad", "❌ не я"),
]
FEEDBACK_LABELS = dict(FEEDBACK_OPTIONS)


async def build_feedback_keyboard(
    user_id: int, user_prompt: str, generated_answer: str
) -> types.InlineKeyboardMarkup | None:
    if not await is_twin_feedback_enabled():
        return None

    feedback_id = await twin_db.log_feedback_candidate(
        user_id, user_prompt or "", generated_answer or ""
    )
    buttons = [
        [
            InlineKeyboardButton(
                text=label, callback_data=f"twin_fb:{feedback_id}:{key}"
            )
            for key, label in FEEDBACK_OPTIONS
        ]
    ]
    return create_user_keyboard(buttons, OWNER_ID)


async def handle_feedback_callback(callback_query: types.CallbackQuery, data: str) -> None:
    parts = data.split(":")
    if len(parts) != 3:
        await callback_query.answer("Ошибка данных", show_alert=True)
        return

    try:
        feedback_id = int(parts[1])
    except ValueError:
        await callback_query.answer("Ошибка данных", show_alert=True)
        return

    rating = parts[2]
    if rating not in FEEDBACK_LABELS:
        await callback_query.answer("Неизвестная оценка", show_alert=True)
        return

    ok = await twin_db.set_feedback_rating(feedback_id, rating)
    if ok:
        await callback_query.answer(f"Принято: {FEEDBACK_LABELS[rating]}")
    else:
        await callback_query.answer("Не удалось сохранить оценку", show_alert=True)

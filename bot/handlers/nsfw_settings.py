from aiogram import types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from config import NSFW_RP_ACTIONS
from bot.utils.user_settings import user_settings_db
from bot.utils.database import db
from aiogram.exceptions import TelegramBadRequest


async def get_nsfw_settings_keyboard(user_id: int) -> InlineKeyboardMarkup:
    current = await user_settings_db.get_nsfw_setting(user_id)

    button = []
    if current:
        button.append(
            [
                InlineKeyboardButton(
                    text="🔞 ВЫКЛЮЧИТЬ NSFW", callback_data=f"nsfw_disable_{user_id}"
                )
            ]
        )
    else:
        button.append(
            [
                InlineKeyboardButton(
                    text="✅ ВКЛЮЧИТЬ NSFW", callback_data=f"nsfw_enable_{user_id}"
                )
            ]
        )

    keyboard = InlineKeyboardMarkup(inline_keyboard=button)
    return keyboard


async def get_nsfw_status_text(user_id: int, username: str) -> str:
    enabled = await user_settings_db.get_nsfw_setting(user_id)
    status = "🔞 ВКЛЮЧЕНЫ" if enabled else "✅ ВЫКЛЮЧЕНЫ"

    rp_commands_list = []
    for cmd, action in NSFW_RP_ACTIONS.items():
        emoji = action[0] if action else "🔞"
        rp_commands_list.append(f"<b>├─ {emoji}</b> <code>{cmd}</code>")

    rp_commands_text = "\n".join(rp_commands_list)
    display_name = f"@{username}" if username else f"id{user_id}"

    return (
        f"<b>┌─ 🔞 НАСТРОЙКИ NSFW ({display_name})</b>\n"
        f"<b>├─ 📊 Текущий статус:</b> {status}\n"
        "<b>│</b>\n"
        "<b>├─ 🔞 NSFW команды:</b>\n"
        f"{rp_commands_text}\n"
        "<b>│</b>\n"
        "<b>└─ 🔘 Используй кнопки ниже для изменения</b>"
    )


async def cmd_nsfw_settings(message: types.Message):
    user_id = message.from_user.id
    status_text = await get_nsfw_status_text(user_id, message.from_user.username)
    keyboard = await get_nsfw_settings_keyboard(user_id)

    await message.reply(status_text, reply_markup=keyboard)
    await db.increment_commands()
    await db.log_command("!настройки", user_id)
    return True


async def nsfw_callback_handler(callback_query: types.CallbackQuery):
    data = callback_query.data
    user_id = callback_query.from_user.id

    if not data.startswith("nsfw_"):
        return

    parts = data.split("_")
    if len(parts) != 3:
        await callback_query.answer("❌ Неверный формат", show_alert=True)
        return

    action = parts[1]
    target_user_id = int(parts[2])

    if user_id != target_user_id:
        await callback_query.answer(
            "❌ Ты не можешь менять чужие настройки!", show_alert=True
        )
        return

    if action == "enable":
        await user_settings_db.set_nsfw_setting(target_user_id, True)
        await callback_query.answer("✅ NSFW команды ВКЛЮЧЕНЫ!")
    else:
        await user_settings_db.set_nsfw_setting(target_user_id, False)
        await callback_query.answer("🔞 NSFW команды ВЫКЛЮЧЕНЫ!")

    new_text = await get_nsfw_status_text(
        target_user_id, callback_query.message.from_user.username
    )
    new_keyboard = await get_nsfw_settings_keyboard(target_user_id)
    try:
        await callback_query.message.edit_text(new_text, reply_markup=new_keyboard)
    except TelegramBadRequest:
        pass

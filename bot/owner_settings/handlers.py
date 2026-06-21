from aiogram import types
from aiogram.utils.keyboard import InlineKeyboardBuilder
from bot.owner_settings.database import owner_settings_db
from bot.utils.database import db

SETTINGS_NAMES = {
    "payments_enabled": "💳 Платежи (Токены)",
    "auto_reply_enabled": "🤖 Автоответ",
    "reply_to_owner": "👑 Отвечать владельцу"
}


async def cmd_system_settings(message: types.Message):
    await send_settings_menu(message)
    await db.increment_commands()
    return True


async def send_settings_menu(message: types.Message | types.CallbackQuery):
    settings = await owner_settings_db.get_all_settings()
    builder = InlineKeyboardBuilder()

    for key, name in SETTINGS_NAMES.items():
        status_emoji = "✅" if settings.get(key, False) else "❌"
        builder.button(text=f"{status_emoji} {name}", callback_data=f"sys_set:{key}")

    builder.adjust(1)

    text = "<b>┌─ ⚙️ СИСТЕМНЫЕ НАСТРОЙКИ БОТА</b>\n└─ Нажми на кнопку, чтобы переключить:"

    if isinstance(message, types.CallbackQuery):
        await message.message.edit_text(text, reply_markup=builder.as_markup())
    else:
        await message.reply(text, reply_markup=builder.as_markup())


async def system_settings_callback(callback_query: types.CallbackQuery):
    key = callback_query.data.split(":")[1]

    new_status = await owner_settings_db.toggle_setting(key)

    await send_settings_menu(callback_query)

    status_text = "Включено" if new_status else "Выключено"
    await callback_query.answer(f"Настройка обновлена: {status_text}")

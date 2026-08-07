from aiogram import types
from bot.utils.database import db
from bot.utils.user_settings import user_settings_db
from config import SFW_RP_ACTIONS, NSFW_RP_ACTIONS
from bot.utils.helpers import get_raw_text, format_styled_message


async def process_rp_command(message: types.Message):
    raw_text = get_raw_text(message)
    if not raw_text:
        return False

    text = raw_text

    parts = text.split(maxsplit=1)
    command = parts[0].lower() if parts else ""

    if command in SFW_RP_ACTIONS:
        return await execute_rp_action(
            message, command, SFW_RP_ACTIONS[command], parts, is_nsfw=False
        )

    if command in NSFW_RP_ACTIONS:
        sender_id = message.from_user.id
        target_id = message.reply_to_message.from_user.id

        sender_nsfw_enabled = await user_settings_db.get_nsfw_setting(sender_id)
        target_nsfw_enabled = await user_settings_db.get_nsfw_setting(target_id)

        if not sender_nsfw_enabled:
            await message.reply(
                format_styled_message(
                    "🔞",
                    "NSFW БЛОКИРОВКА",
                    "У тебя отключены NSFW команды в <code>!настройках</code>\n"
                    "🔘 Включи их чтобы использовать",
                )
            )
            return True

        if not target_nsfw_enabled:
            await message.reply(
                format_styled_message(
                    "🔞",
                    "NSFW БЛОКИРОВКА",
                    "У пользователя, которому ты адресуешь это действие,\n"
                    "NSFW команды ОТКЛЮЧЕНЫ в его настройках!\n\n"
                    "🔘 Уважай выбор других пользователей",
                )
            )
            return True

        return await execute_rp_action(
            message, command, NSFW_RP_ACTIONS[command], parts, is_nsfw=True
        )

    return False


async def execute_rp_action(
    message: types.Message,
    command: str,
    action: str,
    parts: list,
    is_nsfw: bool = False,
):
    target = message.reply_to_message.from_user

    if target.id == message.from_user.id:
        await message.reply(
            format_styled_message("❌", "Ошибка", "Нельзя использовать на себе!")
        )
        return True

    sender_name = message.from_user.first_name or "Неизвестный"
    target_name = target.first_name or "Неизвестный"

    emoji = "🔞" if is_nsfw else "🎭"
    body = f"{sender_name} {action} {target_name}"

    custom_text = parts[1] if len(parts) > 1 else ""
    if custom_text:
        body += f" со словами: <i>«{custom_text}»</i>"

    await message.reply(format_styled_message(emoji, "RP действие", body))
    await db.increment_rp_actions()
    await db.log_rp_action(message.from_user.id, target.id, command, custom_text)
    return True

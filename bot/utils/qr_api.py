import logging
from urllib.parse import quote
from aiogram import types
from config import COMMAND_METADATA
from bot.utils.database import db
from bot.utils.helpers import format_styled_message, spend_tokens, get_raw_text

API_ICON = COMMAND_METADATA["!qr"]["icon"]
API_NAME = COMMAND_METADATA["!qr"]["name"]

logger = logging.getLogger(__name__)


async def cmd_qr(message: types.Message):
    raw_text = get_raw_text(message)
    parts = raw_text.split(maxsplit=1) if raw_text else []
    text_data = ""

    if len(parts) > 1:
        text_data = parts[1].strip()
    elif message.reply_to_message:
        text_data = (
            message.reply_to_message.text or message.reply_to_message.caption or ""
        ).strip()

    if not text_data:
        await message.reply(
            format_styled_message(
                emoji=API_ICON,
                title=API_NAME,
                message="❌ <b>Не указан текст или ссылка.</b>\n📝 Пример: <code>!qr https://google.com</code> или ответом на сообщение.",
            )
        )
        return

    qr_url = f"https://api.qrserver.com/v1/create-qr-code/?size=450x450&data={quote(text_data)}"
    caption = format_styled_message(
        emoji=API_ICON,
        title=API_NAME,
        message=f"Готово! Твой QR-код для:\n<code>{text_data}</code>",
    )

    try:
        try:
            await message.reply_photo(photo=qr_url, caption=caption)
        except Exception:
            await message.reply(f"{caption}\n\n🔗 Скачать QR: {qr_url}")

        await db.increment_commands()
        await db.log_command("!qr", message.from_user.id)
        await spend_tokens(message, "!qr")

    except Exception as e:
        logger.error(f"Критическая ошибка генерации QR: {e}")

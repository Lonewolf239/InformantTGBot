import os
import tempfile
import logging
from aiogram import types
from aiogram.types import FSInputFile
from langdetect import detect, LangDetectException
from config import PAYMENTS_ENABLED, COMMAND_COSTS, VIP_IDS, COMMAND_METADATA
from bot.utils.database import db
from bot.utils.helpers import format_styled_message, spend_tokens
from bot.utils.translation_core import text_to_speech

logger = logging.getLogger(__name__)

VOICE_ICON = COMMAND_METADATA["!озвучка"]["icon"]
VOICE_NAME = COMMAND_METADATA["!озвучка"]["name"]


async def cmd_voiceover(message: types.Message):
    if not message.reply_to_message:
        usage_msg = format_styled_message(
            emoji=VOICE_ICON,
            title=VOICE_NAME,
            message=(
                "❌ <b>Ошибка использования!</b>\n\n"
                "📝 <b>Как использовать:</b>\n"
                "Ответь командой <code>!озвучка</code> на любое текстовое сообщение."
            )
        )
        await message.reply(usage_msg)
        return True

    reply_msg = message.reply_to_message

    target_text = reply_msg.text or reply_msg.caption

    if not target_text:
        error_msg = format_styled_message(
            emoji=VOICE_ICON,
            title=VOICE_NAME,
            message="❌ <b>В сообщении нет текста для озвучки!</b>"
        )
        await message.reply(error_msg)
        return True

    status_msg = await message.reply(
        format_styled_message(
            emoji=VOICE_ICON,
            title=VOICE_NAME,
            message="⏳ <b>Анализирую текст и генерирую озвучку...</b>"
        )
    )

    output_path = None
    try:
        try:
            detected_lang = detect(target_text)
        except LangDetectException:
            detected_lang = "ru"

        with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as tmp_file:
            output_path = tmp_file.name

        success = await text_to_speech(target_text, output_path, lang_code=detected_lang)

        if not success:
            await status_msg.edit_text(
                format_styled_message(
                    emoji=VOICE_ICON,
                    title=VOICE_NAME,
                    message=f"❌ <b>Не удалось сгенерировать озвучку.</b> Возможно, язык ({detected_lang}) не поддерживается."
                )
            )
            return True

        voice_file = FSInputFile(output_path)
        caption_text = target_text[:50] + "..." if len(target_text) > 50 else target_text
        await message.reply_voice(
            voice=voice_file,
            caption=f"<b>🗣️ Озвучено ({detected_lang}):</b>\n<i>{caption_text}</i>"
        )

        await status_msg.edit_text(
            format_styled_message(
                emoji=VOICE_ICON,
                title=VOICE_NAME,
                message="✅ <b>Успешно! Голосовое сообщение отправлено ниже.</b>"
            )
        )

        await db.increment_commands()
        await db.log_command("!озвучка", message.from_user.id)
        await spend_tokens(message, "!озвучка")
        return True

    except Exception as e:
        logger.error(f"❌ Ошибка в cmd_voiceover: {e}", exc_info=True)
        await status_msg.edit_text(
            format_styled_message(
                emoji=VOICE_ICON,
                title=VOICE_NAME,
                message="❌ <b>Произошла внутренняя ошибка при озвучке.</b>"
            )
        )
        return True

    finally:
        if output_path and os.path.exists(output_path):
            try:
                os.unlink(output_path)
            except:
                pass

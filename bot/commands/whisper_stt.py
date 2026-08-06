import logging
import os
from aiogram import types
import html
from aiogram.types import FSInputFile
from config import (
    WHISPER_MAX_DURATION_SECONDS,
    COMMAND_METADATA,
)
from bot.utils.database import db
from bot.utils.helpers import (
    format_styled_message,
    freeze_tokens,
    refund_tokens,
    get_raw_text,
)
from bot.utils.text_utils import split_text_to_chunks
from bot.utils.translation_core import resolve_lang_code, translate_text, text_to_speech
from bot.utils.media_core import (
    download_media_file,
    get_duration,
    adjust_audio_duration,
    replace_audio_in_video,
)
from bot.utils.whisper_core import transcribe_audio
from bot.utils.queue_wrapper import process_with_queue
from bot.utils.registry import register_command

logger = logging.getLogger(__name__)

API_ICON = COMMAND_METADATA["!расшифровка"]["icon"]
API_NAME = COMMAND_METADATA["!расшифровка"]["name"]
TRANS_ICON = COMMAND_METADATA["!перевести"]["icon"]
TRANS_NAME = COMMAND_METADATA["!перевести"]["name"]


async def _worker_transcribe(reply_msg, bot):
    file_path, media_type = await download_media_file(reply_msg, bot)
    if not file_path:
        return None, None

    text = await transcribe_audio(file_path=file_path, language="auto")
    return text, file_path


@register_command("!расшифровка")
async def cmd_transcribe(message: types.Message):
    user_id = message.from_user.id
    if not await freeze_tokens(message, user_id, "!расшифровка"):
        return

    if not message.reply_to_message:
        await refund_tokens(user_id, "!расшифровка")
        usage_msg = format_styled_message(
            emoji=API_ICON,
            title=API_NAME,
            message=(
                "❌ <b>Ошибка использования!</b>\n\n"
                "📝 <b>Как использовать:</b>\n"
                "1. Отправь медиафайл\n"
                "2. Ответь на него командой прямо в этом чате\n\n"
                f"🎯 <b>Поддерживаемые форматы (до {WHISPER_MAX_DURATION_SECONDS} сек):</b>\n"
                "• Голосовые сообщения 🎤\n"
                "• Аудиофайлы 🎵\n"
                "• Кружочки 📹\n"
                "• Короткие видео 🎬\n\n"
                "💡 <b>Пример:</b>\n"
                "<code>!расшифровка</code> (в ответ на сообщение)"
            ),
        )
        await message.reply(usage_msg)
        return

    reply_msg = message.reply_to_message
    has_media = any(
        [reply_msg.voice, reply_msg.video_note, reply_msg.video, reply_msg.audio]
    )

    if not has_media:
        await refund_tokens(user_id, "!расшифровка")
        error_type = format_styled_message(
            emoji=API_ICON,
            title=API_NAME,
            message=(
                "❌ <b>Неподдерживаемый тип сообщения!</b>\n\n"
                "🎯 Команда работает только для:\n"
                "• Голосовых сообщений и аудио\n"
                "• Видеосообщений (кружочков)\n"
                "• Коротких видео"
            ),
        )
        await message.reply(error_type)
        return

    media_type_text = "медиа"
    if reply_msg.voice:
        media_type_text = "голосовое сообщение"
    elif reply_msg.audio:
        media_type_text = "аудиофайл"
    elif reply_msg.video_note:
        media_type_text = "кружок"
    elif reply_msg.video:
        media_type_text = "видео"

    result, status_msg = await process_with_queue(
        message=message,
        queue_name="whisper",
        icon=API_ICON,
        title=API_NAME,
        action_text=f"Скачиваю и распознаю ({media_type_text})",
        func=_worker_transcribe,
        reply_msg=reply_msg,
        bot=message.bot,
    )

    if not result:
        await refund_tokens(user_id, "!расшифровка")
        if status_msg:
            await status_msg.edit_text(
                format_styled_message(
                    emoji=API_ICON,
                    title=API_NAME,
                    message="❌ <b>Не удалось загрузить или распознать файл!</b>\nУбедись, что файл не слишком большой.",
                )
            )
        return

    transcribed_text, file_path = result

    try:
        if file_path and os.path.exists(file_path):
            os.unlink(file_path)
    except Exception:
        pass

    if not transcribed_text:
        await refund_tokens(user_id, "!расшифровка")
        if status_msg:
            await status_msg.edit_text(
                format_styled_message(
                    emoji=API_ICON,
                    title=API_NAME,
                    message=(
                        "❌ <b>Не удалось распознать речь!</b>\n\n"
                        "Возможные причины:\n"
                        "• Плохое качество записи\n"
                        "• Тихая или неразборчивая речь\n"
                        "• Фоновый шум или музыка\n"
                        "• Неподдерживаемый язык"
                    ),
                )
            )
        return

    safe_text = html.escape(transcribed_text)
    text_chunks = split_text_to_chunks(safe_text, max_size=3700)

    first_chunk = format_styled_message(
        emoji=API_ICON,
        title=f"{API_NAME} ({media_type_text})",
        message=f"📝 <b>ТЕКСТ (Часть 1/{len(text_chunks)}):</b>\n<code>{text_chunks[0]}</code>",
    )

    if status_msg:
        await status_msg.edit_text(first_chunk)
    else:
        await message.reply(first_chunk)

    for i, chunk in enumerate(text_chunks[1:], start=2):
        await message.reply(
            f"<b>📝 ТЕКСТ (Часть {i}/{len(text_chunks)}):</b>\n<code>{chunk}</code>"
        )

    await db.increment_commands()
    await db.log_command("!расшифровка", user_id)


async def _worker_translate_stt(reply_msg, bot):
    file_path, media_type = await download_media_file(reply_msg, bot)
    if not file_path:
        return None, None, None

    original_text = await transcribe_audio(
        file_path=file_path, language="auto", task="translate"
    )
    return original_text, file_path, media_type


@register_command("!перевести")
async def cmd_translate(message: types.Message):
    user_id = message.from_user.id
    if not await freeze_tokens(message, user_id, "!перевести"):
        return

    if not message.reply_to_message:
        await refund_tokens(user_id, "!перевести")
        await message.reply(
            format_styled_message(
                emoji=TRANS_ICON,
                title=TRANS_NAME,
                message="❌ <b>Ошибка использования!</b>\n📝 Ответьте командой <code>!перевести</code> на иностранное аудио, голосовое или видео.",
            )
        )
        return

    reply_msg = message.reply_to_message
    has_media = any(
        [reply_msg.voice, reply_msg.video_note, reply_msg.video, reply_msg.audio]
    )
    has_text = bool(reply_msg.text)

    raw_text = get_raw_text(message)
    args = raw_text.split(maxsplit=1) if raw_text else []
    target_lang = resolve_lang_code(args[1].strip().lower() if len(args) > 1 else "ru")

    if has_text and not has_media:
        status_msg = await message.reply(
            format_styled_message(
                emoji=TRANS_ICON,
                title=TRANS_NAME,
                message="⏳ <b>Перевожу текст...</b>",
            )
        )
        try:
            translated_text = await translate_text(
                reply_msg.text, target_lang=target_lang
            )
            await status_msg.edit_text(
                format_styled_message(
                    emoji=TRANS_ICON,
                    title=TRANS_NAME,
                    message=f"<code>{translated_text}</code>",
                )
            )

            await db.increment_commands()
            await db.log_command("!перевести", user_id)
            return
        except Exception as e:
            await refund_tokens(user_id, "!перевести")
            logger.error(f"❌ Ошибка перевода текста: {e}")
            await status_msg.edit_text(
                format_styled_message(
                    emoji=TRANS_ICON,
                    title=TRANS_NAME,
                    message="❌ <b>Ошибка перевода.</b>",
                )
            )
            return

    if not has_media:
        await refund_tokens(user_id, "!перевести")
        await message.reply(
            format_styled_message(
                emoji=TRANS_ICON,
                title=TRANS_NAME,
                message="❌ <b>Команда работает только для текста, голосовых, аудио и видео!</b>",
            )
        )
        return

    result, status_msg = await process_with_queue(
        message=message,
        queue_name="heavyweights",
        icon=TRANS_ICON,
        title=TRANS_NAME,
        action_text="Скачиваю и распознаю",
        func=_worker_translate_stt,
        reply_msg=reply_msg,
        bot=message.bot,
    )

    if not result or not result[1]:
        await refund_tokens(user_id, "!перевести")
        if status_msg:
            await status_msg.edit_text(
                format_styled_message(
                    emoji=TRANS_ICON,
                    title=TRANS_NAME,
                    message="❌ <b>Не удалось загрузить или распознать файл!</b>",
                )
            )
        return

    original_text, file_path, media_type = result
    tts_path = output_path = None

    try:
        if not original_text:
            await refund_tokens(user_id, "!перевести")
            if status_msg:
                await status_msg.edit_text(
                    format_styled_message(
                        emoji=TRANS_ICON,
                        title=TRANS_NAME,
                        message="❌ <b>Не удалось распознать текст в медиа.</b>",
                    )
                )
            return

        if status_msg:
            await status_msg.edit_text(
                format_styled_message(
                    emoji=TRANS_ICON,
                    title=TRANS_NAME,
                    message="⏳ <b>Финальный перевод на русский...</b>",
                )
            )

        translated_text = await translate_text(original_text, target_lang=target_lang)

        if status_msg:
            await status_msg.edit_text(
                format_styled_message(
                    emoji=TRANS_ICON,
                    title=TRANS_NAME,
                    message="⏳ <b>Генерирую новую озвучку...</b>",
                )
            )

        tts_path = file_path + "_tts.mp3"

        if not await text_to_speech(translated_text, tts_path, lang_code=target_lang):
            await refund_tokens(user_id, "!перевести")
            if status_msg:
                await status_msg.edit_text(
                    format_styled_message(
                        emoji=TRANS_ICON,
                        title=TRANS_NAME,
                        message="❌ <b>Ошибка: Не удалось сгенерировать озвучку.</b>",
                    )
                )
            return

        original_duration = await get_duration(file_path)
        if original_duration > 0:
            adjusted_tts_path = file_path + "_tts_adjusted.mp3"
            if await adjust_audio_duration(
                tts_path, original_duration, adjusted_tts_path
            ):
                try:
                    if os.path.exists(tts_path):
                        os.unlink(tts_path)
                except Exception:
                    pass
                tts_path = adjusted_tts_path

        if status_msg:
            await status_msg.edit_text(
                format_styled_message(
                    emoji=TRANS_ICON,
                    title=TRANS_NAME,
                    message="⏳ <b>Собираю и отправляю файл...</b>",
                )
            )

        translated_text = html.escape(translated_text)
        orig_filename = None
        if reply_msg.audio and reply_msg.audio.file_name:
            orig_filename = reply_msg.audio.file_name
        elif reply_msg.video and reply_msg.video.file_name:
            orig_filename = reply_msg.video.file_name

        caption_text = translated_text
        additional_chunks = []

        if len(translated_text) > 800:
            caption_text = translated_text[:800] + "..."
            remaining_text = translated_text[800:]
            additional_chunks = split_text_to_chunks(remaining_text, max_size=4000)

        main_caption = f"<b>📝 Перевод:</b> {caption_text}"

        if media_type in ["voice", "audio"]:
            if media_type == "audio" and orig_filename:
                name, ext = os.path.splitext(orig_filename)
                new_filename = f"{name} (перевод){ext}"
                audio_file = FSInputFile(tts_path, filename=new_filename)
            else:
                audio_file = FSInputFile(tts_path)

            if media_type == "voice":
                await message.reply_voice(voice=audio_file, caption=main_caption)
            else:
                await message.reply_audio(audio=audio_file, caption=main_caption)

        elif media_type in ["video", "video_note"]:
            output_path = file_path + "_translated.mp4"
            if await replace_audio_in_video(file_path, tts_path, output_path):
                if media_type == "video" and orig_filename:
                    name, ext = os.path.splitext(orig_filename)
                    new_filename = f"{name} (перевод){ext}"
                    video_file = FSInputFile(output_path, filename=new_filename)
                else:
                    video_file = FSInputFile(output_path)

                if media_type == "video_note":
                    await message.reply_video_note(video_file)
                    additional_chunks = split_text_to_chunks(
                        translated_text, max_size=4000
                    )
                else:
                    await message.reply_video(video_file, caption=main_caption)
            else:
                await refund_tokens(user_id, "!перевести")
                if status_msg:
                    await status_msg.edit_text(
                        format_styled_message(
                            emoji=TRANS_ICON,
                            title=TRANS_NAME,
                            message="❌ <b>Ошибка при сборке видео-файла.</b>",
                        )
                    )
                return

        if additional_chunks:
            for i, chunk in enumerate(additional_chunks, start=1):
                await message.reply(
                    f"<b>📝 Продолжение перевода (Часть {i}):</b>\n{chunk}"
                )

        if status_msg:
            await status_msg.edit_text(
                format_styled_message(
                    emoji=TRANS_ICON,
                    title=TRANS_NAME,
                    message="✅ <b>Успешно! Медиа отправлено ниже.</b>",
                )
            )

        await db.increment_commands()
        await db.log_command("!перевести", user_id)

    except Exception as e:
        await refund_tokens(user_id, "!перевести")
        logger.error(f"❌ Критическая ошибка в cmd_translate: {e}", exc_info=True)
        if "status_msg" in locals() and status_msg:
            await status_msg.edit_text(
                format_styled_message(
                    emoji=TRANS_ICON,
                    title=TRANS_NAME,
                    message="❌ <b>Произошла внутренняя ошибка сервера.</b>",
                )
            )

    finally:
        for path in [file_path, tts_path, output_path]:
            if path and os.path.exists(path):
                try:
                    os.unlink(path)
                except Exception:
                    pass

import logging
import os
from aiogram import types
from aiogram.types import FSInputFile
from config import WHISPER_MAX_DURATION_SECONDS, WHISPER_MAX_FILE_SIZE_MB, PAYMENTS_ENABLED, COMMAND_COSTS, VIP_IDS, COMMAND_METADATA
from bot.utils.database import db
from bot.utils.ai_queue import get_queue, TaskType, ensure_queue_started
from bot.utils.helpers import format_styled_message, spend_tokens
from bot.utils.text_utils import split_text_to_chunks
from bot.utils.translation_core import resolve_lang_code, translate_text, text_to_speech
from bot.utils.media_core import download_media_file, get_duration, adjust_audio_duration, replace_audio_in_video
from bot.utils.whisper_core import transcribe_audio

logger = logging.getLogger(__name__)

API_ICON = COMMAND_METADATA["!расшифровка"]["icon"]
API_NAME = COMMAND_METADATA["!расшифровка"]["name"]
TRANS_ICON = COMMAND_METADATA["!перевести"]["icon"]
TRANS_NAME = COMMAND_METADATA["!перевести"]["name"]


async def cmd_transcribe(message: types.Message):
    ensure_queue_started()

    if not message.reply_to_message:
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
            )
        )
        await message.reply(usage_msg)
        return

    reply_msg = message.reply_to_message

    has_media = any([
        reply_msg.voice,
        reply_msg.video_note,
        reply_msg.video,
        reply_msg.audio
    ])

    if not has_media:
        error_type = format_styled_message(
            emoji=API_ICON,
            title=API_NAME,
            message=(
                "❌ <b>Неподдерживаемый тип сообщения!</b>\n\n"
                "🎯 Команда работает только для:\n"
                "• Голосовых сообщений и аудио\n"
                "• Видеосообщений (кружочков)\n"
                "• Коротких видео"
            )
        )
        await message.reply(error_type)
        return

    status_msg = await message.reply(
        format_styled_message(
            emoji=API_ICON,
            title=API_NAME,
            message="⏳ <b>Обработка сообщения...</b>\n📍 Позиция: вычисляется"
        )
    )

    file_path = None
    media_type_text = ""

    try:
        if reply_msg.voice:
            media_type_text = "голосовое сообщение"
        elif reply_msg.audio:
            media_type_text = "аудиофайл"
        elif reply_msg.video_note:
            media_type_text = "кружок"
        elif reply_msg.video:
            media_type_text = "видео"

        file_path, media_type = await download_media_file(reply_msg, message.bot)

        if not file_path:
            await status_msg.edit_text(
                format_styled_message(
                    emoji=API_ICON,
                    title=API_NAME,
                    message=(
                        "❌ <b>Не удалось загрузить файл!</b>\n\n"
                        "Возможные причины:\n"
                        f"• Слишком длинное сообщение (>{WHISPER_MAX_DURATION_SECONDS} сек)\n"
                        f"• Слишком большой файл (>{WHISPER_MAX_FILE_SIZE_MB} MB)\n"
                        "• Ошибка доступа к файлу"
                    )
                )
            )
            return

        queue = get_queue()

        async def update_position(pos: int):
            try:
                if pos == 0:
                    await status_msg.edit_text(
                        format_styled_message(
                            emoji=API_ICON,
                            title=API_NAME,
                            message=f"🔄 <b>Распознаю речь...</b>\n🎯 Тип: {media_type_text}"
                        )
                    )
                else:
                    await status_msg.edit_text(
                        format_styled_message(
                            emoji=API_ICON,
                            title=API_NAME,
                            message=f"⏳ <b>Очередь...</b>\n🎯 Тип: {media_type_text}\n📍 Позиция перед вами: {pos}"
                        )
                    )
            except Exception:
                pass

        task_future, queue_position = await queue.add_task(
            task_type=TaskType.WHISPER,
            data={"file_path": file_path, "language": "auto"},
            user_id=message.from_user.id,
            update_cb=update_position
        )

        await update_position(queue_position)

        transcribed_text = await task_future

        try:
            if file_path and os.path.exists(file_path):
                os.unlink(file_path)
        except:
            pass

        if not transcribed_text:
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
                    )
                )
            )
            return

        text_chunks = split_text_to_chunks(transcribed_text, max_size=3700)

        first_chunk = format_styled_message(
            emoji=API_ICON,
            title=f"{API_NAME} ({media_type_text})",
            message=f"📝 <b>ТЕКСТ (Часть 1/{len(text_chunks)}):</b>\n<code>{text_chunks[0]}</code>"
        )
        await status_msg.edit_text(first_chunk)

        for i, chunk in enumerate(text_chunks[1:], start=2):
            await message.reply(f"<b>📝 ТЕКСТ (Часть {i}/{len(text_chunks)}):</b>\n<code>{chunk}</code>")

        await db.increment_commands()
        await db.log_command("!расшифровка", message.from_user.id)
        await spend_tokens(message, "!расшифровка")

    except Exception as e:
        logger.error(f"❌ Критическая ошибка в cmd_transcribe: {e}", exc_info=True)

        try:
            if file_path and os.path.exists(file_path):
                os.unlink(file_path)
        except:
            pass

        await status_msg.edit_text(
            format_styled_message(
                emoji=API_ICON,
                title=API_NAME,
                message=(
                    "❌ <b>Внутренняя ошибка сервера!</b>\n\n"
                    "🔧 Попробуйте:\n"
                    "• Повторить попытку позже\n"
                    "• Отправить другое сообщение"
                )
            )
        )


async def cmd_translate(message: types.Message):
    ensure_queue_started()

    if not message.reply_to_message:
        await message.reply(
            format_styled_message(
                emoji=TRANS_ICON,
                title=TRANS_NAME,
                message="❌ <b>Ошибка использования!</b>\n📝 Ответьте командой <code>!перевести</code> на иностранное аудио, голосовое или видео."
            )
        )
        return

    reply_msg = message.reply_to_message
    has_media = any([reply_msg.voice, reply_msg.video_note, reply_msg.video, reply_msg.audio])
    has_text = bool(reply_msg.text)

    args = message.text.split(maxsplit=1)
    target_lang = resolve_lang_code(args[1].strip().lower() if len(args) > 1 else "ru")

    if has_text and not has_media:
        status_msg = await message.reply(format_styled_message(emoji=TRANS_ICON, title=TRANS_NAME, message="⏳ <b>Перевожу текст...</b>"))
        try:
            translated_text = await translate_text(reply_msg.text, target_lang=target_lang)
            await status_msg.edit_text(
                format_styled_message(
                    emoji=TRANS_ICON,
                    title=TRANS_NAME,
                    message=f"<code>{translated_text}</code>"
                )
            )

            from config import COMMAND_COSTS, VIP_IDS, PAYMENTS_ENABLED
            if PAYMENTS_ENABLED:
                from bot.utils.tokens_database import tokens_db
                cost = 1
                if cost > 0 and message.from_user.id not in VIP_IDS:
                    await tokens_db.spend_tokens(message.from_user.id, cost)

            await db.increment_commands()
            await db.log_command("!перевести", message.from_user.id)
            return
        except Exception as e:
            logger.error(f"❌ Ошибка перевода текста: {e}")
            await status_msg.edit_text(format_styled_message(emoji=TRANS_ICON, title=TRANS_NAME, message="❌ <b>Ошибка перевода.</b>"))
            return

    if not has_media:
        await message.reply(
            format_styled_message(
                emoji=TRANS_ICON,
                title=TRANS_NAME,
                message="❌ <b>Команда работает только для текста, голосовых, аудио и видео!</b>"
            )
        )
        return

    status_msg = await message.reply(
        format_styled_message(
            emoji=TRANS_ICON,
            title=TRANS_NAME,
            message="⏳ <b>Скачиваю и анализирую файл...</b>\n📍 Позиция: вычисляется"
        )
    )

    file_path = tts_path = output_path = None

    try:
        file_path, media_type = await download_media_file(reply_msg, message.bot)
        if not file_path:
            await status_msg.edit_text(
                format_styled_message(
                    emoji=TRANS_ICON,
                    title=TRANS_NAME,
                    message=(
                        "❌ <b>Не удалось загрузить файл!</b>\n\n"
                        "Возможные причины:\n"
                        f"• Слишком длинное сообщение (>{WHISPER_MAX_DURATION_SECONDS} сек)\n"
                        f"• Слишком большой файл (>{WHISPER_MAX_FILE_SIZE_MB} MB)\n"
                        "• Ошибка доступа к файлу"
                    )
                )
            )
            return

        queue = get_queue()

        async def update_position(pos: int):
            try:
                if pos == 0:
                    await status_msg.edit_text(
                        format_styled_message(
                            emoji=TRANS_ICON,
                            title=TRANS_NAME,
                            message="🔄 <b>Распознаю и перевожу...</b>\nОжидайте ответа модели."
                        )
                    )
                else:
                    await status_msg.edit_text(
                        format_styled_message(
                            emoji=TRANS_ICON,
                            title=TRANS_NAME,
                            message=f"⏳ <b>Очередь...</b>\n📍 Позиция перед вами: {pos}"
                        )
                    )
            except Exception:
                pass

        task_future, queue_position = await queue.add_task(
            task_type=TaskType.WHISPER,
            data={"file_path": file_path, "language": "auto", "task": "translate"},
            user_id=message.from_user.id,
            update_cb=update_position
        )

        await update_position(queue_position)

        original_text = await task_future

        if not original_text:
            await status_msg.edit_text(format_styled_message(emoji=TRANS_ICON, title=TRANS_NAME, message="❌ <b>Не удалось распознать текст в медиа.</b>"))
            return

        await status_msg.edit_text(format_styled_message(emoji=TRANS_ICON, title=TRANS_NAME, message="⏳ <b>Финальный перевод на русский...</b>"))
        translated_text = await translate_text(original_text, target_lang=target_lang)

        await status_msg.edit_text(format_styled_message(emoji=TRANS_ICON, title=TRANS_NAME, message="⏳ <b>Генерирую новую озвучку...</b>"))
        tts_path = file_path + "_tts.mp3"

        if not await text_to_speech(translated_text, tts_path, lang_code=target_lang):
            await status_msg.edit_text(format_styled_message(emoji=TRANS_ICON, title=TRANS_NAME, message="❌ <b>Ошибка: Не удалось сгенерировать озвучку.</b>"))
            return

        original_duration = await get_duration(file_path)
        if original_duration > 0:
            adjusted_tts_path = file_path + "_tts_adjusted.mp3"
            if await adjust_audio_duration(tts_path, original_duration, adjusted_tts_path):
                try:
                    if os.path.exists(tts_path):
                        os.unlink(tts_path)
                except:
                    pass
                tts_path = adjusted_tts_path

        await status_msg.edit_text(format_styled_message(emoji=TRANS_ICON, title=TRANS_NAME, message="⏳ <b>Собираю и отправляю файл...</b>"))

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
        media_sent_msg = None

        if media_type in ["voice", "audio"]:
            if media_type == "audio" and orig_filename:
                name, ext = os.path.splitext(orig_filename)
                new_filename = f"{name} (перевод){ext}"
                audio_file = FSInputFile(tts_path, filename=new_filename)
            else:
                audio_file = FSInputFile(tts_path)

            if media_type == "voice":
                media_sent_msg = await message.reply_voice(voice=audio_file, caption=main_caption)
            else:
                media_sent_msg = await message.reply_audio(audio=audio_file, caption=main_caption)

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
                    media_sent_msg = await message.reply_video_note(video_file)
                    additional_chunks = split_text_to_chunks(translated_text, max_size=4000)
                else:
                    media_sent_msg = await message.reply_video(video_file, caption=main_caption)
            else:
                await status_msg.edit_text(format_styled_message(emoji=TRANS_ICON, title=TRANS_NAME, message="❌ <b>Ошибка при сборке видео-файла.</b>"))
                return

        if additional_chunks:
            for i, chunk in enumerate(additional_chunks, start=1):
                await message.reply(f"<b>📝 Продолжение перевода (Часть {i}):</b>\n{chunk}")

        await status_msg.edit_text(format_styled_message(emoji=TRANS_ICON, title=TRANS_NAME, message="✅ <b>Успешно! Медиа отправлено ниже.</b>"))

        from config import COMMAND_COSTS, VIP_IDS, PAYMENTS_ENABLED
        if PAYMENTS_ENABLED:
            from bot.utils.tokens_database import tokens_db
            cost = COMMAND_COSTS.get("!перевести", 0)
            if cost > 0 and message.from_user.id not in VIP_IDS:
                await tokens_db.spend_tokens(message.from_user.id, cost)

        await db.increment_commands()
        await db.log_command("!перевести", message.from_user.id)

    except Exception as e:
        logger.error(f"❌ Критическая ошибка в cmd_translate: {e}", exc_info=True)
        await status_msg.edit_text(format_styled_message(emoji=TRANS_ICON, title=TRANS_NAME, message="❌ <b>Произошла внутренняя ошибка сервера.</b>"))

    finally:
        for path in [file_path, tts_path, output_path]:
            if path and os.path.exists(path):
                try: os.unlink(path)
                except: pass

import logging
import asyncio
import tempfile
import os
from typing import Optional, Tuple
from aiogram import types
from config import WHISPER_MODEL, WHISPER_MAX_DURATION_SECONDS, WHISPER_MAX_FILE_SIZE_MB
import whisper
from bot.utils.database import db
from bot.utils.ai_queue import get_queue, TaskType, ensure_queue_started

logger = logging.getLogger(__name__)

_model_instance = None
_model_lock = asyncio.Lock()


async def get_whisper_model():
    global _model_instance

    async with _model_lock:
        if _model_instance is None:
            logger.info(f"🔄 Загрузка модели Whisper: {WHISPER_MODEL}...")
            loop = asyncio.get_event_loop()
            _model_instance = await loop.run_in_executor(
                None,
                lambda: whisper.load_model(WHISPER_MODEL)
            )
            logger.info(f"✅ Модель Whisper ({WHISPER_MODEL}) загружена!")

        return _model_instance


async def transcribe_audio(file_path: str, language: str = "ru") -> Optional[str]:
    try:
        model = await get_whisper_model()

        options = {
            "language": language if language != "auto" else None,
            "task": "transcribe",
            "fp16": False,
            "verbose": False,
        }

        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None,
            lambda: model.transcribe(file_path, **options)
        )

        transcribed_text = result.get("text", "").strip()

        if transcribed_text:
            logger.info(f"✅ Распознано {len(transcribed_text)} символов")
            return transcribed_text
        else:
            logger.warning("⚠️ Распознавание не дало результатов")
            return None

    except Exception as e:
        logger.error(f"❌ Ошибка при распознавании речи: {e}", exc_info=True)
        return None


async def download_media_file(message: types.Message, bot) -> Tuple[Optional[str], Optional[str]]:
    file_id = None
    media_type = None
    extension = None

    if message.voice:
        file_id = message.voice.file_id
        media_type = "voice"
        extension = ".ogg"
        duration = message.voice.duration

    elif message.video_note:
        file_id = message.video_note.file_id
        media_type = "video_note"
        extension = ".mp4"
        duration = message.video_note.duration

    elif message.video:
        file_id = message.video.file_id
        media_type = "video"
        extension = ".mp4"
        duration = message.video.duration

    else:
        return None, None

    if duration and duration > WHISPER_MAX_DURATION_SECONDS:
        logger.warning(f"⚠️ Слишком длинное сообщение: {duration} сек (макс {WHISPER_MAX_DURATION_SECONDS})")
        return None, None

    file_size = getattr(message.voice, 'file_size', getattr(message.video, 'file_size', 0))
    if file_size and file_size > WHISPER_MAX_FILE_SIZE_MB * 1024 * 1024:
        logger.warning(f"⚠️ Слишком большой файл: {file_size // (1024*1024)} MB")
        return None, None

    try:
        file = await bot.get_file(file_id)
        file_bytes = await bot.download_file(file.file_path)

        with tempfile.NamedTemporaryFile(delete=False, suffix=extension) as tmp_file:
            tmp_file.write(file_bytes.getvalue())
            tmp_path = tmp_file.name

        logger.info(f"📥 Скачан файл: {tmp_path} ({file_size} bytes)")
        return tmp_path, media_type

    except Exception as e:
        logger.error(f"❌ Ошибка скачивания файла: {e}")
        return None, None


async def cmd_transcribe(message: types.Message):
    ensure_queue_started()

    if not message.reply_to_message:
        await message.reply(
            "<b>┌─ 🎙️ РАСШИФРОВКА РЕЧИ</b>\n"
            "├─ ❌ <b>Ошибка использования!</b>\n"
            "│\n"
            "├─ 📝 <b>Как использовать:</b>\n"
            "├─ 1. Отправь голосовое, кружок или короткое видео\n"
            "├─ 2. Ответь на него командой прямо в этом чате\n"
            "│\n"
            f"├─ 🎯 <b>Поддерживаемые форматы (до {WHISPER_MAX_DURATION_SECONDS} сек):</b>\n"
            "├─ • Голосовые сообщения 🎤\n"
            "├─ • Кружочки 📹\n"
            "├─ • Короткие видео 🎬\n"
            "│\n"
            "├─ 💡 <b>Пример:</b>\n"
            "└─ <code>!расшифровка</code> (в ответ на сообщение)"
        )
        return True

    reply_msg = message.reply_to_message

    has_media = any([
        reply_msg.voice,
        reply_msg.video_note,
        reply_msg.video
    ])

    if not has_media:
        await message.reply(
            "<b>┌─ 🎙️ РАСШИФРОВКА РЕЧИ</b>\n"
            "├─ ❌ <b>Неподдерживаемый тип сообщения!</b>\n"
            "│\n"
            "├─ 🎯 Команда работает только для:\n"
            "├─ • Голосовых сообщений\n"
            "├─ • Видеосообщений (кружочков)\n"
            "└─ • Коротких видео (до 60 секунд)"
        )
        return True

    status_msg = await message.reply(
        "<b>┌─ 🎙️ РАСШИФРОВКА РЕЧИ</b>\n"
        "├─ ⏳ <b>Обработка сообщения...</b>\n"
        "└─ ⏱️ Это займёт 5-15 секунд"
    )

    file_path = None
    media_type_text = ""

    try:
        if reply_msg.voice:
            media_type_text = "голосовое сообщение"
        elif reply_msg.video_note:
            media_type_text = "кружок"
        elif reply_msg.video:
            media_type_text = "видео"

        file_path, media_type = await download_media_file(reply_msg, message.bot)

        if not file_path:
            await status_msg.edit_text(
                "<b>┌─ 🎙️ РАСШИФРОВКА РЕЧИ</b>\n"
                "├─ ❌ <b>Не удалось загрузить файл!</b>\n"
                "│\n"
                "├─ Возможные причины:\n"
                "├─ • Слишком длинное сообщение (>60 сек)\n"
                "├─ • Слишком большой файл (>20 MB)\n"
                "└─ • Ошибка доступа к файлу"
            )
            return True

        queue = get_queue()
        queue_position = queue.queue.qsize() + 1

        await status_msg.edit_text(
            "<b>┌─ 🎙️ РАСШИФРОВКА РЕЧИ</b>\n"
            "├─ ⏳ <b>Распознаю речь...</b>\n"
            f"├─ 🎯 Тип: {media_type_text}\n"
            f"└─ 📍 Позиция в очереди: {queue_position}"
        )

        transcribed_text, _ = await queue.add_task(
            task_type=TaskType.WHISPER,
            data={"file_path": file_path, "language": "ru"},
            user_id=message.from_user.id
        )

        try:
            if file_path and os.path.exists(file_path):
                os.unlink(file_path)
        except:
            pass

        if not transcribed_text:
            await status_msg.edit_text(
                "<b>┌─ 🎙️ РАСШИФРОВКА РЕЧИ</b>\n"
                "├─ ❌ <b>Не удалось распознать речь!</b>\n"
                "│\n"
                "├─ Возможные причины:\n"
                "├─ • Плохое качество записи\n"
                "├─ • Тихая или неразборчивая речь\n"
                "├─ • Фоновый шум или музыка\n"
                "└─ • Неподдерживаемый язык\n"
            )
            return True

        result_text = (
            f"<b>┌─ 🎙️ РАСШИФРОВКА</b> <i>({media_type_text})</i>\n"
            f"<b>└─ 📝 ТЕКСТ:</b> <code>{transcribed_text}</code>"
        )

        if len(result_text) > 4000:
            first_chunk = result_text[:3500]
            await status_msg.edit_text(first_chunk)

            remaining = result_text[3500:]
            if remaining:
                await message.reply(remaining)
        else:
            await status_msg.edit_text(result_text)

        db.increment_commands()
        db.log_command("!расшифровка", message.from_user.id)
        return True

    except Exception as e:
        logger.error(f"❌ Критическая ошибка в cmd_transcribe: {e}", exc_info=True)

        try:
            if file_path and os.path.exists(file_path):
                os.unlink(file_path)
        except:
            pass

        await status_msg.edit_text(
            "<b>┌─ 🎙️ РАСШИФРОВКА РЕЧИ</b>\n"
            "├─ ❌ <b>Внутренняя ошибка сервера!</b>\n"
            "│\n"
            "├─ 🔧 Попробуйте:\n"
            "├─ • Повторить попытку позже\n"
            "└─ • Отправить другое сообщение\n"
        )
        return True

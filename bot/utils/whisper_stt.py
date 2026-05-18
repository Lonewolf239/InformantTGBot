import logging
import asyncio
import tempfile
import os
from typing import Optional, Tuple
from aiogram import types
from aiogram.types import FSInputFile
from config import WHISPER_MODEL, WHISPER_MAX_DURATION_SECONDS, WHISPER_MAX_FILE_SIZE_MB
import whisper
from bot.utils.database import db
from bot.utils.ai_queue import get_queue, TaskType, ensure_queue_started
import subprocess
from deep_translator import GoogleTranslator
import edge_tts

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
    duration = None

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

    elif message.audio:
        file_id = message.audio.file_id
        media_type = "audio"
        file_name = message.audio.file_name or "audio.mp3"
        _, extension = os.path.splitext(file_name)
        if not extension:
            extension = ".mp3"
        duration = message.audio.duration

    else:
        return None, None

    if duration and duration > WHISPER_MAX_DURATION_SECONDS:
        logger.warning(f"⚠️ Слишком длинное сообщение: {duration} сек (макс {WHISPER_MAX_DURATION_SECONDS})")
        return None, None

    media_obj = message.voice or message.video_note or message.video or message.audio
    file_size = getattr(media_obj, 'file_size', 0)

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
            "├─ 1. Отправь медиафайл\n"
            "├─ 2. Ответь на него командой прямо в этом чате\n"
            "│\n"
            f"├─ 🎯 <b>Поддерживаемые форматы (до {WHISPER_MAX_DURATION_SECONDS} сек):</b>\n"
            "├─ • Голосовые сообщения 🎤\n"
            "├─ • Аудиофайлы 🎵\n"
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
        reply_msg.video,
        reply_msg.audio
    ])

    if not has_media:
        await message.reply(
            "<b>┌─ 🎙️ РАСШИФРОВКА РЕЧИ</b>\n"
            "├─ ❌ <b>Неподдерживаемый тип сообщения!</b>\n"
            "│\n"
            "├─ 🎯 Команда работает только для:\n"
            "├─ • Голосовых сообщений и аудио\n"
            "├─ • Видеосообщений (кружочков)\n"
            "└─ • Коротких видео"
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
        elif reply_msg.audio:
            media_type_text = "аудиофайл"
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
                f"├─ • Слишком длинное сообщение (>{WHISPER_MAX_DURATION_SECONDS} сек)\n"
                f"├─ • Слишком большой файл (>{WHISPER_MAX_FILE_SIZE_MB} MB)\n"
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


async def translate_text(text: str, target_lang: str = "ru") -> str:
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(
        None, 
        lambda: GoogleTranslator(source='auto', target=target_lang).translate(text)
    )


async def text_to_speech(text: str, output_path: str) -> bool:
    if not text or not text.strip():
        logger.warning("⚠️ Попытка озвучить пустой текст")
        return False

    try:
        clean_text = text.strip()
        communicate = edge_tts.Communicate(clean_text, "ru-RU-DmitryNeural")
        await communicate.save(output_path)
        return True
    except edge_tts.exceptions.NoAudioReceived:
        logger.error("❌ edge_tts не вернул аудио (NoAudioReceived). Возможно, текст нечитаем или API недоступно.")
        return False
    except Exception as e:
        logger.error(f"❌ Ошибка генерации озвучки: {e}")
        return False


async def replace_audio_in_video(video_path: str, audio_path: str, output_path: str) -> bool:
    try:
        cmd = [
            'ffmpeg', '-y',
            '-i', video_path,
            '-i', audio_path,
            '-c:v', 'copy',
            '-c:a', 'aac',
            '-map', '0:v:0',
            '-map', '1:a:0',
            '-shortest',
            output_path
        ]

        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        await process.communicate()
        return process.returncode == 0
    except Exception as e:
        logger.error(f"❌ Ошибка FFmpeg: {e}")
        return False


async def cmd_translate(message: types.Message):
    ensure_queue_started()

    if not message.reply_to_message:
        await message.reply(
            "<b>┌─ 🌐 ПЕРЕВОД И ОЗВУЧКА</b>\n"
            "├─ ❌ <b>Ошибка использования!</b>\n"
            "└─ 📝 Ответьте командой <code>!перевести</code> на иностранное аудио, голосовое или видео."
        )
        return True

    reply_msg = message.reply_to_message
    if not any([reply_msg.voice, reply_msg.video_note, reply_msg.video, reply_msg.audio]):
        await message.reply("<b>┌─ 🌐 ПЕРЕВОД И ОЗВУЧКА</b>\n└─ ❌ <b>Команда работает только для голосовых, аудио и видео!</b>")
        return True

    status_msg = await message.reply("<b>┌─ 🌐 ПЕРЕВОД И ОЗВУЧКА</b>\n└─ ⏳ <b>Скачиваю и анализирую файл...</b>")
    file_path = tts_path = output_path = None

    try:
        file_path, media_type = await download_media_file(reply_msg, message.bot)
        if not file_path:
            await status_msg.edit_text(
                "<b>┌─ 🌐 ПЕРЕВОД И ОЗВУЧКА</b>\n"
                "├─ ❌ <b>Не удалось загрузить файл!</b>\n"
                "│\n"
                "├─ Возможные причины:\n"
                f"├─ • Слишком длинное сообщение (>{WHISPER_MAX_DURATION_SECONDS} сек)\n"
                f"├─ • Слишком большой файл (>{WHISPER_MAX_FILE_SIZE_MB} MB)\n"
                "└─ • Ошибка доступа к файлу"
            )
            return True

        await status_msg.edit_text("<b>┌─ 🌐 ПЕРЕВОД И ОЗВУЧКА</b>\n└─ ⏳ <b>Распознаю оригинальную речь...</b>")

        model = await get_whisper_model()
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, lambda: model.transcribe(file_path, task="transcribe", fp16=False, verbose=False))

        if result.get("language", "unknown") == "ru":
            await status_msg.edit_text("<b>┌─ 🌐 ПЕРЕВОД И ОЗВУЧКА</b>\n├─ ❌ <b>Обнаружен русский язык!</b>\n└─ Перевод не требуется.")
            return True

        if not result.get("text", "").strip():
            await status_msg.edit_text("<b>┌─ 🌐 ПЕРЕВОД И ОЗВУЧКА</b>\n└─ ❌ <b>Не удалось распознать текст в медиа.</b>")
            return True

        await status_msg.edit_text("<b>┌─ 🌐 ПЕРЕВОД И ОЗВУЧКА</b>\n└─ ⏳ <b>Перевожу на русский...</b>")
        translated_text = await translate_text(result.get("text", "").strip(), target_lang="ru")

        await status_msg.edit_text("<b>┌─ 🌐 ПЕРЕВОД И ОЗВУЧКА</b>\n└─ ⏳ <b>Генерирую новую озвучку...</b>")
        tts_path = file_path + "_tts.mp3"

        if not await text_to_speech(translated_text, tts_path):
            await status_msg.edit_text("<b>┌─ 🌐 ПЕРЕВОД И ОЗВУЧКА</b>\n└─ ❌ <b>Ошибка: Не удалось сгенерировать озвучку.</b>")
            return True

        await status_msg.edit_text("<b>┌─ 🌐 ПЕРЕВОД И ОЗВУЧКА</b>\n└─ ⏳ <b>Собираю и отправляю файл...</b>")

        if media_type in ["voice", "audio"]:
            audio_file = FSInputFile(tts_path)
            if media_type == "voice":
                await message.reply_voice(voice=audio_file, caption=f"<b>📝 Перевод:</b> {translated_text}")
            else:
                await message.reply_audio(audio=audio_file, caption=f"<b>📝 Перевод:</b> {translated_text}")

        elif media_type in ["video", "video_note"]:
            output_path = file_path + "_translated.mp4"
            if await replace_audio_in_video(file_path, tts_path, output_path):
                video_file = FSInputFile(output_path)
                if media_type == "video_note": await message.reply_video_note(video_file)
                else: await message.reply_video(video_file, caption=f"<b>📝 Перевод:</b> {translated_text}")
            else:
                await status_msg.edit_text("<b>┌─ 🌐 ПЕРЕВОД И ОЗВУЧКА</b>\n└─ ❌ <b>Ошибка при сборке видео-файла.</b>")
                return True

        await status_msg.edit_text("<b>┌─ 🌐 ПЕРЕВОД И ОЗВУЧКА</b>\n└─ ✅ <b>Успешно! Медиа отправлено ниже.</b>")

        db.increment_commands()
        db.log_command("!перевести", message.from_user.id)
        return True

    except Exception as e:
        logger.error(f"❌ Критическая ошибка в cmd_translate: {e}", exc_info=True)
        await status_msg.edit_text("<b>┌─ 🌐 ПЕРЕВОД И ОЗВУЧКА</b>\n└─ ❌ <b>Произошла внутренняя ошибка сервера.</b>")
        return True

    finally:
        for path in [file_path, tts_path, output_path]:
            if path and os.path.exists(path):
                try: os.unlink(path)
                except: pass

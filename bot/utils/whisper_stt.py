import logging
import asyncio
import tempfile
import os
from typing import Optional, Tuple, List
from aiogram import types
from aiogram.types import FSInputFile
from config import WHISPER_MODEL, WHISPER_MAX_DURATION_SECONDS, WHISPER_MAX_FILE_SIZE_MB, WHISPER_TIMEOUT
import whisper
from bot.utils.database import db
from bot.utils.ai_queue import get_queue, TaskType, ensure_queue_started
from bot.utils.helpers import format_styled_message
import subprocess
from deep_translator import GoogleTranslator
import edge_tts

logger = logging.getLogger(__name__)

API_ICON = "🎙️"
API_NAME = "Расшифровка"

TRANS_ICON = "🌐"
TRANS_NAME = "Перевод и Озвучка"

_model_instance = None
_model_lock = asyncio.Lock()


def split_text_to_chunks(text: str, max_size: int = 4000) -> List[str]:
    chunks = []
    while len(text) > max_size:
        split_pos = text.rfind("\n", 0, max_size)
        if split_pos == -1:
            split_pos = text.rfind(" ", 0, max_size)
        if split_pos == -1:
            split_pos = max_size

        chunks.append(text[:split_pos].strip())
        text = text[split_pos:].strip()

    if text:
        chunks.append(text)
    return chunks


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


async def transcribe_audio(file_path: str, language: str = "auto", task: str = "transcribe") -> Optional[str]:
    try:
        model = await get_whisper_model()

        options = {
            "language": language if language != "auto" else None,
            "task": task,
            "fp16": False,
            "verbose": False,
        }

        loop = asyncio.get_event_loop()

        result = await asyncio.wait_for(
            loop.run_in_executor(None, lambda: model.transcribe(file_path, **options)),
            timeout=WHISPER_TIMEOUT
        )

        transcribed_text = result.get("text", "").strip()

        if transcribed_text:
            logger.info(f"✅ Распознано {len(transcribed_text)} символов")
            return transcribed_text
        else:
            logger.warning("⚠️ Распознавание не дало результатов")
            return None

    except asyncio.TimeoutError:
        logger.error("❌ Whisper завис и был остановлен по таймауту")
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
        return True

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
        return True

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
            return True

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
            return True

        text_chunks = split_text_to_chunks(transcribed_text, max_size=3700)

        first_chunk = format_styled_message(
            emoji=API_ICON,
            title=f"{API_NAME} ({media_type_text})",
            message=f"📝 <b>ТЕКСТ (Часть 1/{len(text_chunks)}):</b>\n<code>{text_chunks[0]}</code>"
        )
        await status_msg.edit_text(first_chunk)

        for i, chunk in enumerate(text_chunks[1:], start=2):
            await message.reply(f"<b>📝 ТЕКСТ (Часть {i}/{len(text_chunks)}):</b>\n<code>{chunk}</code>")

        from config import COMMAND_COSTS, VIP_IDS, PAYMENTS_ENABLED
        if PAYMENTS_ENABLED:
            from bot.utils.tokens_database import tokens_db
            cost = COMMAND_COSTS.get("!расшифровка", 0)
            if cost > 0 and message.from_user.id not in VIP_IDS:
                await tokens_db.spend_tokens(message.from_user.id, cost)

        await db.increment_commands()
        await db.log_command("!расшифровка", message.from_user.id)
        return True

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


async def get_duration(file_path: str) -> float:
    try:
        cmd = [
            'ffprobe', '-v', 'error', '-show_entries', 'format=duration',
            '-of', 'default=noprint_wrappers=1:nokey=1', file_path
        ]
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, _ = await process.communicate()
        return float(stdout.decode().strip())
    except Exception as e:
        logger.error(f"❌ Ошибка получения длительности файла {file_path}: {e}")
        return 0.0


async def adjust_audio_duration(audio_path: str, target_duration: float, output_path: str) -> bool:
    current_duration = await get_duration(audio_path)
    if current_duration == 0 or target_duration == 0:
        return False

    speed_factor = current_duration / target_duration

    if abs(speed_factor - 1.0) < 0.03:
        return False

    filters = []
    remaining_factor = speed_factor

    while remaining_factor > 2.0:
        filters.append("atempo=2.0")
        remaining_factor /= 2.0
    while remaining_factor < 0.5:
        filters.append("atempo=0.5")
        remaining_factor /= 0.5

    if remaining_factor != 1.0:
        filters.append(f"atempo={remaining_factor:.4f}")

    filter_str = ",".join(filters)

    try:
        cmd = [
            'ffmpeg', '-y',
            '-i', audio_path,
            '-filter:a', filter_str,
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
        logger.error(f"❌ Ошибка при изменении скорости аудио: {e}")
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
            format_styled_message(
                emoji=TRANS_ICON,
                title=TRANS_NAME,
                message="❌ <b>Ошибка использования!</b>\n📝 Ответьте командой <code>!перевести</code> на иностранное аудио, голосовое или видео."
            )
        )
        return True

    reply_msg = message.reply_to_message
    if not any([reply_msg.voice, reply_msg.video_note, reply_msg.video, reply_msg.audio]):
        await message.reply(
            format_styled_message(
                emoji=TRANS_ICON,
                title=TRANS_NAME,
                message="❌ <b>Команда работает только для голосовых, аудио и видео!</b>"
            )
        )
        return True

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
            return True

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
            return True

        await status_msg.edit_text(format_styled_message(emoji=TRANS_ICON, title=TRANS_NAME, message="⏳ <b>Финальный перевод на русский...</b>"))
        translated_text = await translate_text(original_text, target_lang="ru")

        await status_msg.edit_text(format_styled_message(emoji=TRANS_ICON, title=TRANS_NAME, message="⏳ <b>Генерирую новую озвучку...</b>"))
        tts_path = file_path + "_tts.mp3"

        if not await text_to_speech(translated_text, tts_path):
            await status_msg.edit_text(format_styled_message(emoji=TRANS_ICON, title=TRANS_NAME, message="❌ <b>Ошибка: Не удалось сгенерировать озвучку.</b>"))
            return True

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
                return True

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
        return True

    except Exception as e:
        logger.error(f"❌ Критическая ошибка в cmd_translate: {e}", exc_info=True)
        await status_msg.edit_text(format_styled_message(emoji=TRANS_ICON, title=TRANS_NAME, message="❌ <b>Произошла внутренняя ошибка сервера.</b>"))
        return True

    finally:
        for path in [file_path, tts_path, output_path]:
            if path and os.path.exists(path):
                try: os.unlink(path)
                except: pass

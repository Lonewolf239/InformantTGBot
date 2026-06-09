import asyncio
import logging
import os
import tempfile
from typing import Optional, Tuple
from aiogram import types
from config import WHISPER_MAX_DURATION_SECONDS, WHISPER_MAX_FILE_SIZE_MB

logger = logging.getLogger(__name__)


async def download_media_file(message: types.Message, bot) -> Tuple[Optional[str], Optional[str]]:
    media_obj = message.voice or message.video_note or message.video or message.audio
    if not media_obj:
        return None, None

    media_type = "voice" if message.voice else "video_note" if message.video_note else "video" if message.video else "audio"
    file_id = media_obj.file_id

    extension = ".ogg" if media_type == "voice" else ".mp4" if media_type in ["video_note", "video"] else ".mp3"
    if media_type == "audio" and message.audio.file_name:
        _, ext = os.path.splitext(message.audio.file_name)
        extension = ext or ".mp3"

    duration = getattr(media_obj, 'duration', 0)
    if duration and duration > WHISPER_MAX_DURATION_SECONDS:
        logger.warning(f"⚠️ Слишком длинное сообщение: {duration} сек (макс {WHISPER_MAX_DURATION_SECONDS})")
        return None, None

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


async def get_duration(file_path: str) -> float:
    try:
        cmd = ['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'default=noprint_wrappers=1:nokey=1', file_path]
        process = await asyncio.create_subprocess_exec(*cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
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
    clamped_speed_factor = max(0.85, min(1.35, speed_factor))

    filters = []
    remaining_factor = clamped_speed_factor

    while remaining_factor > 2.0:
        filters.append("atempo=2.0")
        remaining_factor /= 2.0
    while remaining_factor < 0.5:
        filters.append("atempo=0.5")
        remaining_factor /= 0.5

    if remaining_factor != 1.0:
        filters.append(f"atempo={remaining_factor:.4f}")
    filters.append("apad")

    try:
        cmd = ['ffmpeg', '-y', '-i', audio_path, '-filter:a', ",".join(filters), '-t', str(target_duration), output_path]
        process = await asyncio.create_subprocess_exec(*cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        await process.communicate()
        return process.returncode == 0
    except Exception as e:
        logger.error(f"❌ Ошибка при изменении скорости аудио: {e}")
        return False


async def replace_audio_in_video(video_path: str, audio_path: str, output_path: str) -> bool:
    try:
        cmd = ['ffmpeg', '-y', '-i', video_path, '-i', audio_path, '-c:v', 'copy', '-c:a', 'aac', '-map', '0:v:0', '-map', '1:a:0', '-shortest', output_path]
        process = await asyncio.create_subprocess_exec(*cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        await process.communicate()
        return process.returncode == 0
    except Exception as e:
        logger.error(f"❌ Ошибка FFmpeg (replace audio): {e}")
        return False

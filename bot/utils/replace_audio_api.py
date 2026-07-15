import asyncio
import os
import logging
from aiogram import types
from aiogram.types import FSInputFile
from config import COMMAND_METADATA
from bot.utils.database import db
from bot.utils.helpers import format_styled_message, spend_tokens, get_raw_text
from bot.utils.youtube_api import _sync_download
from bot.utils.queue_wrapper import process_with_queue

logger = logging.getLogger(__name__)

API_ICON = COMMAND_METADATA["!звук"]["icon"]
API_NAME = COMMAND_METADATA["!звук"]["name"]


async def _process_replace_audio(
    video_msg, audio_msg, audio_url, bot, vid_path, base_aud_path, out_path
):
    actual_aud_path = base_aud_path

    try:
        video_obj = video_msg.video
        await bot.download(video_obj, destination=vid_path)

        if audio_url:
            loop = asyncio.get_running_loop()
            media_data = await loop.run_in_executor(
                None, _sync_download, audio_url, "bestaudio/best", "audio"
            )

            if not media_data or not os.path.exists(media_data["file_path"]):
                logger.error("Не удалось скачать аудио по предоставленной ссылке.")
                return False, actual_aud_path

            actual_aud_path = media_data["file_path"]
        else:
            audio_obj = audio_msg.audio or audio_msg.voice
            await bot.download(audio_obj, destination=actual_aud_path)

        proc_probe = await asyncio.create_subprocess_exec(
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            vid_path,
            stdout=asyncio.subprocess.PIPE,
        )
        stdout, _ = await proc_probe.communicate()
        duration = stdout.decode().strip()

        ffmpeg_cmd = [
            "ffmpeg",
            "-y",
            "-loglevel",
            "error",
            "-i",
            vid_path,
            "-i",
            actual_aud_path,
            "-map",
            "0:v:0",
            "-map",
            "1:a:0",
            "-c:v",
            "copy",
            "-c:a",
            "aac",
        ]

        if duration:
            ffmpeg_cmd.extend(["-t", duration])

        ffmpeg_cmd.append(out_path)

        proc_concat = await asyncio.create_subprocess_exec(*ffmpeg_cmd)
        await proc_concat.communicate()

        return os.path.exists(out_path), actual_aud_path

    except Exception as e:
        logger.error(f"Ошибка в _process_replace_audio: {e}")
        return False, actual_aud_path


async def cmd_replace_audio(message: types.Message):
    if not message.reply_to_message:
        await message.reply(
            format_styled_message(
                emoji="❌",
                title=API_NAME,
                message="<b>Ответь этой командой на сообщение с видео или аудио!</b>\n\nПрикрепи к команде недостающий файл (аудио/видео) ИЛИ передай ссылку на звук (например: <code>!звук https://...</code>).",
            )
        )
        return

    raw_text = get_raw_text(message, normalize=False) or ""
    parts = raw_text.split(maxsplit=1)
    audio_url = parts[1].strip() if len(parts) > 1 else None

    if audio_url and not audio_url.startswith("http"):
        audio_url = None

    video_msg = (
        message
        if message.video
        else (message.reply_to_message if message.reply_to_message.video else None)
    )

    audio_msg = None
    if not audio_url:
        audio_msg = (
            message
            if (message.audio or message.voice)
            else (
                message.reply_to_message
                if (message.reply_to_message.audio or message.reply_to_message.voice)
                else None
            )
        )

    if not video_msg or (not audio_msg and not audio_url):
        await message.reply(
            format_styled_message(
                emoji="❌",
                title=API_NAME,
                message="<b>Не найдены видео или аудио/ссылка!</b>\n\nУбедись, что в связке есть одно видео, а звук передан аудиофайлом, голосовым сообщением или ссылкой на видео/трек.",
            )
        )
        return

    user_id = message.from_user.id
    msg_id = message.message_id
    vid_path = f"temp_snd_vid_{user_id}_{msg_id}.mp4"
    base_aud_path = f"temp_snd_aud_{user_id}_{msg_id}.media"
    out_path = f"temp_snd_out_{user_id}_{msg_id}.mp4"
    actual_aud_path = None

    try:
        queue_result, status_msg = await process_with_queue(
            message=message,
            queue_name="heavyweights",
            icon=API_ICON,
            title=API_NAME,
            action_text="Свожу аудио с видео",
            func=_process_replace_audio,
            video_msg=video_msg,
            audio_msg=audio_msg,
            audio_url=audio_url,
            bot=message.bot,
            vid_path=vid_path,
            base_aud_path=base_aud_path,
            out_path=out_path,
        )

        if not queue_result:
            if status_msg:
                await status_msg.edit_text(
                    format_styled_message(
                        emoji="❌",
                        title=API_NAME,
                        message="Ошибка: не удалось создать видео. Возможно, очередь перегружена.",
                    )
                )
            return

        success, actual_aud_path = queue_result

        if not success:
            await status_msg.edit_text(
                format_styled_message(
                    emoji="❌",
                    title=API_NAME,
                    message="Ошибка: не удалось создать видео. Возможно, повреждены исходники или недоступна ссылка.",
                )
            )
            return

        result_file = FSInputFile(out_path)

        await status_msg.edit_text(
            format_styled_message(
                emoji="✅",
                title=API_NAME,
                message="Готово! Лови переозвученное видео 👇",
            )
        )

        await message.reply_video(
            video=result_file,
            caption=format_styled_message(
                emoji=API_ICON, title=API_NAME, message="Идеальная переозвучка."
            ),
            supports_streaming=True,
        )

        await db.increment_commands()
        await db.log_command("!звук", message.from_user.id)
        await spend_tokens(message, "!звук")

    except Exception as e:
        logger.error(f"Ошибка команды !звук: {e}")
        await message.reply(
            format_styled_message(
                emoji="❌",
                title=API_NAME,
                message="Произошла непредвиденная ошибка при обработке.",
            )
        )
    finally:
        paths_to_clean = [vid_path, out_path, base_aud_path]
        if actual_aud_path:
            paths_to_clean.append(actual_aud_path)

        for file_path in paths_to_clean:
            if file_path and os.path.exists(file_path):
                try:
                    os.remove(file_path)
                except Exception as cleanup_error:
                    logger.warning(
                        f"Не удалось удалить файл {file_path}: {cleanup_error}"
                    )

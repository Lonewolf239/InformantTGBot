import asyncio
import os
import logging
from aiogram import types
from aiogram.types import FSInputFile

from config import COMMAND_METADATA
from bot.utils.database import db
from bot.utils.helpers import format_styled_message, spend_tokens

logger = logging.getLogger(__name__)

API_ICON = COMMAND_METADATA["!звук"]["icon"]
API_NAME = COMMAND_METADATA["!звук"]["name"]


async def cmd_replace_audio(message: types.Message):
    if not message.reply_to_message:
        await message.reply(
            format_styled_message(
                emoji="❌",
                title=API_NAME,
                message="<b>Ответь этой командой на сообщение с видео или аудио!</b>\n\nПрикрепи к команде недостающий файл (если отвечаешь на видео — прикрепи аудио/войс, и наоборот)."
            )
        )
        return

    video_msg = message if message.video else (message.reply_to_message if message.reply_to_message.video else None)
    audio_msg = message if (message.audio or message.voice) else (message.reply_to_message if (message.reply_to_message.audio or message.reply_to_message.voice) else None)

    if not video_msg or not audio_msg:
        await message.reply(
            format_styled_message(
                emoji="❌",
                title=API_NAME,
                message="<b>Не найдены видео или аудио!</b>\n\nУбедись, что в связке (твоё сообщение + сообщение, на которое ты отвечаешь) есть одно видео и один аудиофайл (или голосовое)."
            )
        )
        return

    status_msg = await message.reply(
        format_styled_message(
            emoji="⏳",
            title=API_NAME,
            message="Свожу аудио с видео... Это займет немного времени."
        )
    )

    user_id = message.from_user.id
    msg_id = message.message_id
    vid_path = f"temp_snd_vid_{user_id}_{msg_id}.mp4"
    aud_path = f"temp_snd_aud_{user_id}_{msg_id}.media"
    out_path = f"temp_snd_out_{user_id}_{msg_id}.mp4"

    video_obj = video_msg.video
    audio_obj = audio_msg.audio or audio_msg.voice

    try:
        await message.bot.download(video_obj, destination=vid_path)
        await message.bot.download(audio_obj, destination=aud_path)

        proc_probe = await asyncio.create_subprocess_exec(
            "ffprobe", "-v", "error", "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1", vid_path,
            stdout=asyncio.subprocess.PIPE
        )
        stdout, _ = await proc_probe.communicate()
        duration = stdout.decode().strip()

        ffmpeg_cmd = [
            "ffmpeg", "-y", "-loglevel", "error",
            "-i", vid_path, "-i", aud_path,
            "-map", "0:v:0", "-map", "1:a:0",
            "-c:v", "copy", "-c:a", "aac"
        ]

        if duration:
            ffmpeg_cmd.extend(["-t", duration])

        ffmpeg_cmd.append(out_path)

        proc_concat = await asyncio.create_subprocess_exec(*ffmpeg_cmd)
        await proc_concat.communicate()

        if os.path.exists(out_path):
            result_file = FSInputFile(out_path)

            await status_msg.edit_text(
                format_styled_message(
                    emoji="✅",
                    title=API_NAME,
                    message="Готово! Лови переозвученное видео 👇"
                )
            )

            await message.reply_video(
                video=result_file,
                caption=format_styled_message(
                    emoji=API_ICON,
                    title=API_NAME,
                    message="Идеальная переозвучка."
                ),
                supports_streaming=True
            )

            await db.increment_commands()
            await db.log_command("!звук", message.from_user.id)
            await spend_tokens(message, "!звук")
        else:
            await status_msg.edit_text(
                format_styled_message(
                    emoji="❌", 
                    title=API_NAME, 
                    message="Ошибка: не удалось создать видео. Возможно, повреждены исходники."
                )
            )

    except Exception as e:
        logger.error(f"Ошибка команды !звук: {e}")
        await status_msg.edit_text(
            format_styled_message(
                emoji="❌", 
                title=API_NAME, 
                message="Произошла непредвиденная ошибка при обработке."
            )
        )
    finally:
        for file_path in [vid_path, aud_path, out_path]:
            if os.path.exists(file_path):
                try:
                    os.remove(file_path)
                except Exception as cleanup_error:
                    logger.warning(f"Не удалось удалить файл {file_path}: {cleanup_error}")

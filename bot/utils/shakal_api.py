import asyncio
import os
import logging
from aiogram import types
from aiogram.types import FSInputFile

from config import COMMAND_METADATA
from bot.utils.database import db
from bot.utils.helpers import format_styled_message, spend_tokens
from bot.utils.mosh import async_mosh
from bot.utils.queue_wrapper import process_with_queue

logger = logging.getLogger(__name__)

API_ICON = COMMAND_METADATA["!шакал"]["icon"]
API_NAME = COMMAND_METADATA["!шакал"]["name"]


async def _process_shakal_video(vid1_path, vid2_path, concat_path, out_path, bot, vid1_msg, vid2_msg):
    try:
        await bot.download(vid1_msg.video, destination=vid1_path)
        await bot.download(vid2_msg.video, destination=vid2_path)

        concat_cmd = [
            "ffmpeg", "-y", "-loglevel", "error",
            "-i", vid1_path, "-i", vid2_path,
            "-filter_complex", 
            "[0:v:0]scale=720:1280,fps=30,setsar=1[v0]; [1:v:0]scale=720:1280,fps=30,setsar=1[v1]; [v0][0:a:0][v1][1:a:0]concat=n=2:v=1:a=1[outv][outa]",
            "-map", "[outv]", "-map", "[outa]",
            "-c:v", "libx264", "-preset", "fast", concat_path
        ]
        proc_concat = await asyncio.create_subprocess_exec(*concat_cmd)
        await proc_concat.communicate()

        await async_mosh(
            vid1_path=vid1_path,
            vid2_path=vid2_path,
            concat_mp4=concat_path,
            output_video=out_path,
            fps=30
        )

        return os.path.exists(out_path)
    except Exception as e:
        logger.error(f"Ошибка в _process_shakal_video: {e}")
        return False


async def cmd_shakal(message: types.Message):
    if not message.reply_to_message or not message.reply_to_message.video:
        await message.reply(
            format_styled_message(
                emoji="❌",
                title=API_NAME,
                message="<b>Ответь этой командой на первое видео, прикрепив второе!</b>"
            )
        )
        return

    if not message.video:
        await message.reply(
            format_styled_message(
                emoji="❌",
                title=API_NAME,
                message="<b>Прикрепи второе видео к сообщению с командой!</b>"
            )
        )
        return

    text = (message.text or message.caption or "").lower()
    is_reverse = "-начало" in text

    if is_reverse:
        vid1_msg = message
        vid2_msg = message.reply_to_message
    else:
        vid1_msg = message.reply_to_message
        vid2_msg = message

    user_id = message.from_user.id
    msg_id = message.message_id
    vid1_path = f"temp_shakal_1_{user_id}_{msg_id}.mp4"
    vid2_path = f"temp_shakal_2_{user_id}_{msg_id}.mp4"
    concat_path = f"temp_shakal_concat_{user_id}_{msg_id}.mp4"
    out_path = f"temp_shakal_out_{user_id}_{msg_id}.mp4"

    try:
        result, status_msg = await process_with_queue(
            message=message,
            queue_name="heavyweights",
            icon=API_ICON,
            title=API_NAME,
            action_text="Расплавляю пиксели",
            func=_process_shakal_video,
            vid1_path=vid1_path,
            vid2_path=vid2_path,
            concat_path=concat_path,
            out_path=out_path,
            bot=message.bot,
            vid1_msg=vid1_msg,
            vid2_msg=vid2_msg
        )

        if not result:
            if status_msg:
                await status_msg.edit_text(
                    format_styled_message(
                        emoji="❌",
                        title=API_NAME,
                        message="Ошибка: не удалось создать глитч-видео."
                    )
                )
            return

        result_file = FSInputFile(out_path)

        await status_msg.edit_text(
            format_styled_message(
                emoji="✅",
                title=API_NAME,
                message="Готово! Лови результат 👇"
            )
        )

        await message.reply_video(
            video=result_file,
            caption=format_styled_message(
                emoji=API_ICON,
                title=API_NAME,
                message="Идеальный датамош."
            ),
            supports_streaming=True
        )

        await db.increment_commands()
        await db.log_command("!шакал", message.from_user.id)
        await spend_tokens(message, "!шакал")

    except Exception as e:
        logger.error(f"Ошибка команды !шакал: {e}")
        await message.reply(
            format_styled_message(
                emoji="❌",
                title=API_NAME,
                message="Произошла непредвиденная ошибка при обработке."
            )
        )
    finally:
        for file_path in [vid1_path, vid2_path, concat_path, out_path]:
            if os.path.exists(file_path):
                try:
                    os.remove(file_path)
                except Exception as cleanup_error:
                    logger.warning(f"Не удалось удалить файл {file_path}: {cleanup_error}")

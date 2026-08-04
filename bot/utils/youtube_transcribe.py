import os
import logging
import asyncio
import uuid
import re
import yt_dlp
from aiogram import types
from aiogram.types import InlineKeyboardButton, BufferedInputFile
from config import (
    YT_DOWNLOAD_DIR,
    COOKIES_FILE,
    COMMAND_METADATA,
    WHISPER_DIARIZATION_EXTRA_COST,
)
from bot.utils.helpers import (
    format_styled_message,
    create_user_keyboard,
    get_raw_text,
    freeze_tokens,
    refund_tokens,
)
from bot.utils.database import db
from bot.utils.queue_wrapper import process_with_queue
from bot.utils.whisper_core import transcribe_audio

API_ICON = COMMAND_METADATA["!ютуб_текст"]["icon"]
API_NAME = COMMAND_METADATA["!ютуб_текст"]["name"]

logger = logging.getLogger(__name__)

os.makedirs(YT_DOWNLOAD_DIR, exist_ok=True)
yt_transcribe_cache = {}


def format_duration(seconds: int) -> str:
    if not seconds:
        return "?:??"
    return f"{int(seconds // 60)}:{int(seconds % 60):02d}"


def _sync_download_audio_for_transcribe(url: str, request_id: str) -> dict | None:
    temp_path = os.path.join(YT_DOWNLOAD_DIR, f"yt_transcribe_{request_id}")
    opts = {
        "quiet": True,
        "no_warnings": True,
        "format": "m4a/bestaudio/best",
        "outtmpl": temp_path + ".%(ext)s",
        "source_address": "0.0.0.0",
        "extractor_args": {
            "youtube": {"player_client": ["android", "web", "mweb", "ios"]}
        },
        "postprocessors": [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192",
            }
        ],
    }
    if os.path.exists(COOKIES_FILE):
        opts["cookiefile"] = COOKIES_FILE

    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=True)
            if not info:
                return None
            filename = ydl.prepare_filename(info)
            base_path = os.path.splitext(filename)[0]
            final_path = base_path + ".mp3"
            title = info.get("title", "Видео YouTube")
            duration = info.get("duration", 0)
            return {
                "file_path": final_path,
                "title": title,
                "duration": duration,
            }
    except Exception as e:
        logger.error(f"Ошибка скачивания для транскрипции: {e}")
        return None


def get_yt_transcribe_keyboard(req_id: str, user_id: int):
    req_data = yt_transcribe_cache.get(req_id)
    if not req_data:
        return None

    if req_data.get("diarization"):
        diar_status = f"🟢 Вкл (+{WHISPER_DIARIZATION_EXTRA_COST} токенов)"
    else:
        diar_status = "🔴 Выкл"
    ts_status = "🟢 Вкл" if req_data.get("timestamps") else "🔴 Выкл"

    keyboard = [
        [
            InlineKeyboardButton(
                text=f"🔹 Разделять спикеров: {diar_status}",
                callback_data=f"yt_transcribe|diarization|{req_id}",
            )
        ]
    ]

    if req_data.get("diarization"):
        spk_mode = req_data.get("speakers_mode", "auto")
        spk_display = {"auto": "Авто", "1": "1", "2-4": "2-4", "4-8": "4-8"}.get(
            spk_mode, "Авто"
        )
        keyboard.append(
            [
                InlineKeyboardButton(
                    text=f"👥 Кол-во спикеров: {spk_display}",
                    callback_data=f"yt_transcribe|speakers|{req_id}",
                )
            ]
        )

    keyboard.extend(
        [
            [
                InlineKeyboardButton(
                    text=f"🔹 Таймкоды: {ts_status}",
                    callback_data=f"yt_transcribe|timestamps|{req_id}",
                )
            ],
            [
                InlineKeyboardButton(
                    text="🚀 Начать транскрипцию",
                    callback_data=f"yt_transcribe|start|{req_id}",
                )
            ],
        ]
    )
    return create_user_keyboard(keyboard, user_id)


async def _async_download_task(url: str, request_id: str):
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(
        None, _sync_download_audio_for_transcribe, url, request_id
    )


async def cmd_youtube_transcribe(message: types.Message):
    raw_text = get_raw_text(message, normalize=False) or ""
    args = raw_text.split(maxsplit=1)

    if len(args) < 2:
        error_msg = format_styled_message(
            emoji=API_ICON,
            title=API_NAME,
            message=(
                "❌ <b>Не указана ссылка на видео YouTube.</b>\n\n"
                "📝 <b>Пример использования:</b>\n"
                "<code>!ютуб_текст https://www.youtube.com/watch?v=dQw4w9WgXcQ</code>"
            ),
        )
        await message.reply(error_msg)
        return

    url = args[1].strip()
    request_id = uuid.uuid4().hex[:8]

    res, status_msg = await process_with_queue(
        message,
        "heavyweights",
        API_ICON,
        API_NAME,
        "Скачивание аудио с YouTube",
        _async_download_task,
        url,
        request_id,
    )

    if not res or not res.get("file_path"):
        await status_msg.edit_text(
            format_styled_message(
                emoji="❌",
                title=API_NAME,
                message="Не удалось скачать аудио по данной ссылке. Проверьте адрес и повторите попытку.",
            )
        )
        return

    yt_transcribe_cache[request_id] = {
        "file_path": res["file_path"],
        "title": res["title"],
        "duration": res["duration"],
        "diarization": False,
        "speakers_mode": "auto",
        "timestamps": True,
        "user_id": message.from_user.id,
    }

    duration_str = format_duration(res["duration"])
    info_text = (
        f"📹 <b>Название:</b> {res['title']}\n"
        f"⏱ <b>Длительность:</b> {duration_str}\n\n"
        "Выберите настройки и нажмите <b>«Начать транскрипцию»</b>:"
    )

    kb = get_yt_transcribe_keyboard(request_id, message.from_user.id)
    await status_msg.edit_text(
        format_styled_message(emoji=API_ICON, title=API_NAME, message=info_text),
        reply_markup=kb,
    )


async def process_yt_transcribe_callback(callback_query: types.CallbackQuery):
    data = callback_query.data
    parts = data.split("|")
    if len(parts) < 3:
        await callback_query.answer("❌ Неверный формат данных", show_alert=True)
        return

    _, action, req_id = parts[:3]
    req_data = yt_transcribe_cache.get(req_id)

    if not req_data:
        await callback_query.answer(
            "⚠️ Сессия транскрипции истекла или не найдена.", show_alert=True
        )
        return

    user_id = callback_query.from_user.id

    if action == "diarization":
        req_data["diarization"] = not req_data["diarization"]
        kb = get_yt_transcribe_keyboard(req_id, user_id)
        await callback_query.message.edit_reply_markup(reply_markup=kb)
        await callback_query.answer(
            f"Разделение спикеров: {'Включено' if req_data['diarization'] else 'Выключено'}"
        )

    elif action == "speakers":
        modes = ["auto", "1", "2-4", "4-8"]
        current_idx = modes.index(req_data.get("speakers_mode", "auto"))
        req_data["speakers_mode"] = modes[(current_idx + 1) % len(modes)]
        kb = get_yt_transcribe_keyboard(req_id, user_id)
        await callback_query.message.edit_reply_markup(reply_markup=kb)
        await callback_query.answer(f"Количество спикеров: {req_data['speakers_mode']}")

    elif action == "timestamps":
        req_data["timestamps"] = not req_data["timestamps"]
        kb = get_yt_transcribe_keyboard(req_id, user_id)
        await callback_query.message.edit_reply_markup(reply_markup=kb)
        await callback_query.answer(
            f"Таймкоды: {'Включены' if req_data['timestamps'] else 'Выключены'}"
        )

    elif action == "start":
        file_path = req_data["file_path"]
        title = req_data["title"]
        duration = req_data["duration"]
        speakers_mode = req_data.get("speakers_mode", "auto")
        diarization = req_data["diarization"]
        timestamps = req_data["timestamps"]

        extra_cost = WHISPER_DIARIZATION_EXTRA_COST if diarization else 0
        if not await freeze_tokens(
            callback_query.message, user_id, "!ютуб_текст", extra_cost
        ):
            return

        await callback_query.answer("🎙 Начинаем расшифровку...")

        duration_str = format_duration(duration)
        status_text = (
            f"🎙 <b>Транскрипция в процессе...</b>\n"
            f"📹 <b>Видео:</b> {title}\n"
            f"⏱ <b>Длительность:</b> {duration_str}"
        )

        await callback_query.message.edit_text(
            format_styled_message(emoji=API_ICON, title=API_NAME, message=status_text),
            reply_markup=None,
        )

        progress_task = None
        if duration > 600:

            async def update_progress():
                dots = [".", "..", "...", "...."]
                idx = 0
                while True:
                    await asyncio.sleep(50)
                    idx = (idx + 1) % len(dots)
                    try:
                        prog_text = (
                            f"⏳ <b>Идёт транскрипция видео ({duration_str}){dots[idx]}</b>\n"
                            "Whisper распознаёт текст. Это может занять некоторое время."
                        )
                        await callback_query.message.edit_text(
                            format_styled_message(
                                emoji=API_ICON, title=API_NAME, message=prog_text
                            )
                        )
                    except Exception:
                        pass

            progress_task = asyncio.create_task(update_progress())

        try:
            if asyncio.iscoroutinefunction(transcribe_audio):
                text_result = await transcribe_audio(
                    file_path=file_path,
                    timestamps=timestamps,
                    diarization=diarization,
                    speakers_mode=speakers_mode,
                )
            else:
                loop = asyncio.get_running_loop()
                text_result = await loop.run_in_executor(
                    None,
                    lambda: transcribe_audio(
                        file_path=file_path,
                        timestamps=timestamps,
                        diarization=diarization,
                        speakers_mode=speakers_mode,
                    ),
                )

            if not text_result or not text_result.strip():
                await refund_tokens(user_id, "!ютуб_текст", extra_cost)
                await callback_query.message.edit_text(
                    format_styled_message(
                        emoji="❌",
                        title=API_NAME,
                        message="Не удалось распознать текст из данного видео (возможно, в видео отсутствует речь).",
                    )
                )
                return

            header = f"{title}\n\n"

            file_content = (header + text_result).encode("utf-8")
            clean_title = re.sub(r"[^\w\s-]", "", title).strip().replace(" ", "_")[:30]
            doc_filename = f"YouTube_{clean_title}_{req_id}.txt"

            input_file = BufferedInputFile(file_content, filename=doc_filename)

            caption_msg = format_styled_message(
                emoji=API_ICON,
                title=API_NAME,
                message=(
                    f"✅ <b>Транскрипция завершена!</b>\n"
                    f"📹 <b>Видео:</b> {title}\n"
                    f"📄 <b>Файл:</b> <code>{doc_filename}</code>"
                ),
            )

            await callback_query.message.answer_document(
                document=input_file, caption=caption_msg
            )

            await db.increment_commands()
            await db.log_command("!ютуб_текст", user_id)

            try:
                await callback_query.message.edit_text(
                    format_styled_message(
                        emoji="✅",
                        title=API_NAME,
                        message=f"Транскрипция видео <b>{title}</b> успешно завершена и отправлена!",
                    )
                )
            except Exception as e:
                logger.error(f"Ошибка при изменении финального сообщения: {e}")

        except Exception as e:
            logger.error(f"Ошибка при транскрипции YouTube: {e}")
            await refund_tokens(user_id, "!ютуб_текст", extra_cost)
            err_text = format_styled_message(
                emoji="❌",
                title=API_NAME,
                message="Произошла ошибка при транскрипции видео. Попробуйте ещё раз позже.",
            )
            await callback_query.message.edit_text(err_text)

        finally:
            if progress_task:
                progress_task.cancel()
            if os.path.exists(file_path):
                try:
                    os.remove(file_path)
                except Exception as e:
                    logger.error(f"Ошибка удаления файла {file_path}: {e}")
            yt_transcribe_cache.pop(req_id, None)

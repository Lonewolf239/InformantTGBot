import logging
import asyncio
import os
import uuid
import shutil
from typing import Optional, Dict, Any
import yt_dlp
from aiogram import types, F
from aiogram.types import FSInputFile, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.exceptions import TelegramAPIError

logger = logging.getLogger(__name__)

DOWNLOAD_DIR = "downloads"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

pending_requests = {}
download_queue = asyncio.Queue()


def _sync_get_info(url: str) -> Optional[dict]:
    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'skip_download': True,
    }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            return ydl.extract_info(url, download=False)
    except Exception as e:
        logger.error(f"Ошибка получения информации о видео {url}: {e}")
        return None


def _sync_download(url: str, format_str: str, media_type: str) -> Optional[Dict[str, Any]]:
    ydl_opts = {
        'outtmpl': f'{DOWNLOAD_DIR}/%(id)s.%(ext)s',
        'noplaylist': True,
        'quiet': True,
        'no_warnings': True,
        'format': format_str,
    }

    if media_type == "audio":
        ydl_opts.update({
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }],
        })

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)

            if 'requested_downloads' in info and info['requested_downloads']:
                filename = info['requested_downloads'][0].get('filepath')
            else:
                filename = ydl.prepare_filename(info)

            if media_type == "audio":
                filename = os.path.splitext(filename)[0] + '.mp3'
            else:
                if not os.path.exists(filename):
                    base = os.path.splitext(filename)[0]
                    for ext in ['.mp4', '.mkv', '.webm', '.3gp']:
                        if os.path.exists(base + ext):
                            filename = base + ext
                            break

            return {
                "title": info.get("title", "Unknown Video"),
                "duration": info.get("duration", 0),
                "file_path": filename,
                "type": media_type,
            }

    except Exception as e:
        logger.error(f"Ошибка yt-dlp при скачивании {url}: {e}")
        return None


async def process_download_task(task_data: dict):
    message: types.Message = task_data['status_message']
    original_message: types.Message = task_data['original_message']
    url: str = task_data['url']
    format_choice: str = task_data['format_choice']
    media_type: str = task_data['type']

    try:
        try:
            if os.path.exists(DOWNLOAD_DIR):
                shutil.rmtree(DOWNLOAD_DIR)
            os.makedirs(DOWNLOAD_DIR, exist_ok=True)
        except Exception as cleanup_e:
            logger.warning(f"Не удалось очистить папку загрузок: {cleanup_e}")

        await message.edit_text(f"<b>┌─ ⏳ Статус:</b>\n└─ Скачивание файла...")

        loop = asyncio.get_running_loop()
        media_data = await loop.run_in_executor(None, _sync_download, url, format_choice, media_type)

        if not media_data or not os.path.exists(media_data["file_path"]):
            await message.edit_text("<b>┌─ ❌ Ошибка скачивания.</b>\n└─ Не удалось получить доступ к медиа (возможно, заблокировано).")
            return

        file_size_bytes = os.path.getsize(media_data["file_path"])
        limit_bytes = 50 * 1024 * 1024

        if file_size_bytes > limit_bytes:
            size_mb = file_size_bytes / (1024 * 1024)
            await message.edit_text(
                f"<b>┌─ ❌ Ошибка лимита.</b>\n└─ Итоговый файл весит <b>{size_mb:.1f} MB</b>.\n"
                f"Telegram запрещает ботам отправлять файлы тяжелее 50 MB."
            )
            if os.path.exists(media_data["file_path"]):
                os.remove(media_data["file_path"])
            return

        await message.edit_text(f"<b>┌─ ⏳ Статус:</b>\n└─ Отправка в Telegram...")

        file = FSInputFile(media_data["file_path"])
        caption = f"<b>┌─ 🎬 {media_data['title']}</b>\n└─ Скачано ботом"

        try:
            if media_data["type"] == "audio":
                await original_message.reply_audio(audio=file, caption=caption)
            else:
                await original_message.reply_video(video=file, caption=caption)
        except TelegramAPIError as e:
            if "reply" in str(e) or "not found" in str(e):
                if media_data["type"] == "audio":
                    await message.chat.send_audio(audio=file, caption=caption)
                else:
                    await message.chat.send_video(video=file, caption=caption)
            else:
                logger.warning(f"Не удалось отправить как медиа, пробуем документом: {e}")
                try:
                    await original_message.reply_document(
                        document=file, 
                        caption=caption + "\n<i>(Отправлено файлом из-за лимитов/ошибки формата)</i>"
                    )
                except Exception as doc_e:
                    try:
                        await message.chat.send_document(document=file, caption=caption)
                    except Exception as final_e:
                        logger.error(f"Не удалось отправить даже напрямую в чат: {final_e}")
                        await message.edit_text("<b>┌─ ❌ Ошибка отправки.</b>\n└─ Не удалось передать файл через API Telegram.")
                        if os.path.exists(media_data["file_path"]):
                            os.remove(media_data["file_path"])
                        return

        await message.edit_text(f"<b>┌─ ✅ Успешно!</b>\n└─ Файл отправлен ниже.")

        if os.path.exists(media_data["file_path"]):
            os.remove(media_data["file_path"])

    except Exception as e:
        logger.error(f"Внутренняя ошибка обработки: {e}")
        await message.edit_text("<b>┌─ ❌ Ошибка.</b>\n└─ Произошла внутренняя ошибка сервера.")


async def download_worker():
    while True:
        task_data = await download_queue.get()
        await process_download_task(task_data)
        download_queue.task_done()


async def cmd_download_yt(message: types.Message):
    args = message.text.split()
    if len(args) < 2:
        await message.reply("<b>┌─ 📝 Использование:</b>\n└─ <code>!скачать</code> [ссылка]")
        return

    url = args[-1]
    status_msg = await message.reply("<b>┌─ ⚙️ Анализ видео:</b>\n└─ Пожалуйста, подождите, собираем доступные форматы...")

    loop = asyncio.get_running_loop()
    info = await loop.run_in_executor(None, _sync_get_info, url)

    if not info:
        await status_msg.edit_text("<b>┌─ ❌ Ошибка.</b>\n└─ Не удалось извлечь данные о видео. Проверьте корректность ссылки.")
        return

    request_id = str(uuid.uuid4())[:8]
    formats = info.get('formats', [])

    audio_formats = [f for f in formats if f.get('vcodec') == 'none' and f.get('acodec') != 'none']
    best_aud = max(audio_formats, key=lambda x: x.get('filesize') or x.get('filesize_approx') or 0, default={})
    audio_size = best_aud.get('filesize') or best_aud.get('filesize_approx') or 0
    audio_format_id = best_aud.get('format_id')

    video_formats = [f for f in formats if f.get('vcodec') != 'none']
    heights_dict = {}
    for f in video_formats:
        h = f.get('height')
        if not h:
            continue
        current_size = f.get('filesize') or f.get('filesize_approx') or 0
        if h not in heights_dict or current_size > heights_dict[h].get('size', 0):
            heights_dict[h] = {
                'format_id': f.get('format_id'),
                'size': current_size,
                'acodec': f.get('acodec')
            }

    def format_size(bytes_size):
        if not bytes_size:
            return "размер неизвестен"
        mb = bytes_size / (1024 * 1024)
        return f"{mb:.1f} MB"

    choices = {}
    inline_keyboard = []

    sorted_heights = sorted(heights_dict.keys(), reverse=True)

    for h in sorted_heights:
        v_info = heights_dict[h]
        v_size = v_info['size']

        is_video_only = v_info['acodec'] == 'none'
        total_size = (v_size + audio_size) if (is_video_only and v_size and audio_size) else (v_size or audio_size)

        if is_video_only and audio_format_id:
            format_str = f"{v_info['format_id']}+{audio_format_id}"
        else:
            format_str = v_info['format_id']

        choice_key = f"vid_{h}"
        choices[choice_key] = {
            "size": total_size,
            "format_str": format_str,
            "type": "video"
        }

        size_str = format_size(total_size)
        warn = " ⚠️ >50MB" if total_size > 50 * 1024 * 1024 else ""
        btn_text = f"🎬 {h}p ({size_str}){warn}"
        inline_keyboard.append([InlineKeyboardButton(text=btn_text, callback_data=f"yt_dl|{choice_key}|{request_id}")])

    if best_aud:
        choice_key = "audio"
        choices[choice_key] = {
            "size": audio_size,
            "format_str": audio_format_id if audio_format_id else "bestaudio/best",
            "type": "audio"
        }
        size_str = format_size(audio_size)
        warn = " ⚠️ >50MB" if audio_size > 50 * 1024 * 1024 else ""
        btn_text = f"🎵 Только Звук ({size_str}){warn}"
        inline_keyboard.append([InlineKeyboardButton(text=btn_text, callback_data=f"yt_dl|{choice_key}|{request_id}")])

    pending_requests[request_id] = {
        "url": url,
        "formats": choices
    }

    keyboard = InlineKeyboardMarkup(inline_keyboard=inline_keyboard)
    video_title = info.get('title', 'Unknown Video')

    await status_msg.edit_text(
        f"<b>┌─ 🎬 {video_title}</b>\n└─ Выберите формат (Лимит TG: 50MB):", 
        reply_markup=keyboard
    )


async def process_yt_callback(callback: types.CallbackQuery):
    _, choice_key, req_id = callback.data.split("|")

    req_data = pending_requests.get(req_id)
    if not req_data:
        await callback.message.edit_text("<b>┌─ ❌ Ошибка.</b>\n└─ Ссылка устарела или не найдена. Повторите запрос.")
        await callback.answer()
        return

    choice_data = req_data["formats"].get(choice_key)
    if not choice_data:
        await callback.message.edit_text("<b>┌─ ❌ Ошибка.</b>\n└─ Выбранный формат больше недоступен.")
        await callback.answer()
        return

    limit_bytes = 50 * 1024 * 1024
    if choice_data["size"] > limit_bytes:
        size_mb = choice_data["size"] / (1024 * 1024)
        await callback.answer(
            text=f"❌ Скачивание невозможно!\n\nРазмер файла ({size_mb:.1f} MB) превышает лимит Telegram в 50 MB для обычных ботов.",
            show_alert=True
        )
        return

    url = req_data["url"]
    del pending_requests[req_id]

    queue_position = download_queue.qsize() + 1
    await callback.message.edit_text(f"<b>┌─ ⏳ Статус:</b>\n└─ Добавлено в очередь (позиция: {queue_position})...")

    await download_queue.put({
        'original_message': callback.message.reply_to_message or callback.message,
        'status_message': callback.message,
        'url': url,
        'format_choice': choice_data["format_str"],
        'type': choice_data["type"]
    })

    await callback.answer()

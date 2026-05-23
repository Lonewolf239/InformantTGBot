import logging
import asyncio
import os
import uuid
import shutil
import re
import random
import zipfile
from typing import Optional, Dict, Any
import yt_dlp
from aiogram import types
from aiogram.types import FSInputFile, InlineKeyboardButton
from aiogram.exceptions import TelegramAPIError
from config import YT_DOWNLOAD_DIR, YT_MAX_FILE_SIZE_MB
from bot.utils.helpers import create_user_keyboard, format_styled_message

logger = logging.getLogger(__name__)

API_ICON = "🎬"
API_NAME = "Медиа"

os.makedirs(YT_DOWNLOAD_DIR, exist_ok=True)
pending_requests = {}
download_queue = asyncio.Queue()


def detect_platform(url: str) -> str:
    url_lower = url.lower()
    if "tiktok.com" in url_lower:
        return "TikTok"
    return "YouTube"


def _sync_get_info(url: str) -> Optional[dict]:
    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'skip_download': True,
        'extract_flat': 'in_playlist',
        'nocheckcertificate': True,
        'geo_bypass': True,
        'headers': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36'
        },
        'extractor_args': {'youtube': {'player_client': ['android', 'web', 'mweb', 'ios']}},
    }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            return ydl.extract_info(url, download=False)
    except Exception as e:
        logger.error(f"Ошибка получения информации о медиа {url}: {e}")
        return None


def _sync_download(url: str, format_str: str, media_type: str) -> Optional[Dict[str, Any]]:
    ydl_opts = {
        'outtmpl': f'{YT_DOWNLOAD_DIR}/%(title)s.%(ext)s',
        'noplaylist': True,
        'quiet': True,
        'no_warnings': True,
        'format': format_str,
        'nocheckcertificate': True,
        'geo_bypass': True,
        'headers': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36'
        },
        'extractor_args': {'youtube': {'player_client': ['android', 'web', 'mweb', 'ios']}},
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
                "title": info.get("title", "Unknown Media"),
                "duration": info.get("duration", 0),
                "file_path": filename,
                "type": media_type,
            }

    except Exception as e:
        logger.error(f"Ошибка yt-dlp при скачивании {url}: {e}")
        return None


def _sync_download_playlist_item(url: str, output_dir: str) -> Optional[Dict[str, Any]]:
    ydl_opts = {
        'outtmpl': f'{output_dir}/%(uploader|Неизвестен)s - %(title)s.%(ext)s',
        'noplaylist': True,
        'quiet': True,
        'no_warnings': True,
        'format': 'bestaudio/best',
        'nocheckcertificate': True,
        'geo_bypass': True,
        'ignoreerrors': True,
        'headers': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36'
        },
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }],
        'extractor_args': {'youtube': {'player_client': ['android', 'web', 'mweb', 'ios']}},
    }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            if not info:
                return None
            if 'requested_downloads' in info and info['requested_downloads']:
                filename = info['requested_downloads'][0].get('filepath')
            else:
                filename = ydl.prepare_filename(info)
            filename = os.path.splitext(filename)[0] + '.mp3'
            return {"file_path": filename}
    except Exception as e:
        logger.error(f"Ошибка при скачивании трека из плейлиста {url}: {e}")
        return None


async def process_download_task(task_data: dict):
    message: types.Message = task_data['status_message']
    original_message: types.Message = task_data['original_message']
    url: str = task_data['url']
    format_choice: str = task_data['format_choice']
    media_type: str = task_data['type']
    platform: str = task_data.get('platform', 'YouTube')

    try:
        try:
            if os.path.exists(YT_DOWNLOAD_DIR):
                shutil.rmtree(YT_DOWNLOAD_DIR)
            os.makedirs(YT_DOWNLOAD_DIR, exist_ok=True)
        except Exception: pass

        await message.edit_text(format_styled_message(emoji="⏳", title="Статус", message="Скачивание файла..."))
        loop = asyncio.get_running_loop()
        media_data = await loop.run_in_executor(None, _sync_download, url, format_choice, media_type)

        if not media_data or not os.path.exists(media_data["file_path"]):
            await message.edit_text(format_styled_message(emoji="❌", title=f"ОШИБКА {platform.upper()}", message="Не удалось получить доступ к медиа."))
            return

        file_size_bytes = os.path.getsize(media_data["file_path"])
        limit_bytes = YT_MAX_FILE_SIZE_MB * 1024 * 1024

        if file_size_bytes > limit_bytes:
            await message.edit_text(
                format_styled_message(
                    emoji="❌",
                    title="ОШИБКА ЛИМИТА",
                    message=(
                        f"Итоговый файл весит <b>{file_size_bytes / (1024 * 1024):.1f} MB</b>.\n"
                        f"Telegram запрещает ботам отправлять файлы тяжелее {YT_MAX_FILE_SIZE_MB} MB."
                    )
                )
            )
            if os.path.exists(media_data["file_path"]): os.remove(media_data["file_path"])
            return

        await message.edit_text(format_styled_message(emoji="⏳", title="Статус", message="Отправка в Telegram..."))

        original_title = "".join([c for c in media_data['title'] if c not in ['/', '\\', '?', '%', '*', ':', '|', '"', '<', '>']])
        file_ext = os.path.splitext(media_data["file_path"])[1]
        telegram_filename = f"{original_title}{file_ext}"

        file = FSInputFile(media_data["file_path"], filename=telegram_filename)
        
        caption = format_styled_message(emoji="🎬", title=media_data['title'], message="Скачано ботом")

        try:
            if media_data["type"] == "audio": await original_message.reply_audio(audio=file, caption=caption)
            else: await original_message.reply_video(video=file, caption=caption)

        except TelegramAPIError as e:
            if "reply" in str(e) or "not found" in str(e):
                if media_data["type"] == "audio": await message.chat.send_audio(audio=file, caption=caption)
                else: await message.chat.send_video(video=file, caption=caption)
            else:
                try: await original_message.reply_document(document=file, caption=caption + "\n<i>(Отправлено файлом из-за лимитов)</i>")
                except Exception:
                    try: await message.chat.send_document(document=file, caption=caption)
                    except Exception:
                        await message.edit_text(format_styled_message(emoji="❌", title=f"ОШИБКА {platform.upper()}", message="Не удалось передать файл."))
                        if os.path.exists(media_data["file_path"]): os.remove(media_data["file_path"])
                        return

        await message.edit_text(format_styled_message(emoji=API_ICON, title=original_title, message="✅ <b>Успешно!</b>"))

        if os.path.exists(media_data["file_path"]):
            os.remove(media_data["file_path"])

    except Exception as e:
        logger.error(f"Внутренняя ошибка обработки: {e}")
        await message.edit_text(format_styled_message(emoji="❌", title=f"ОШИБКА {platform.upper()}", message="Произошла внутренняя ошибка сервера."))


async def download_worker():
    while True:
        task_data = await download_queue.get()
        await process_download_task(task_data)
        download_queue.task_done()


async def cmd_download_yt(message: types.Message):
    args = message.text.split()
    if len(args) < 2:
        usage_text = (
            "<code>!скачать</code> [ссылка] [параметры]\n\n"
            "<b>Параметры для плейлистов:</b>\n"
            "• <code>-random</code> — 1 случайный трек (или перемешать список)\n"
            "• <code>-X</code> — скачать X треков (например: -5)\n"
            "• <code>-от_X</code> — начать с трека №X (например: -от_2)\n"
            "• <code>-до_X</code> — закончить на №X (например: -до_7)\n\n"
            "<i>💡 Можно комбинировать: <code>-random -5</code> скачает 5 случайных треков.</i>"
        )
        await message.reply(format_styled_message(emoji=API_ICON, title="Использование", message=usage_text))
        return

    url = None
    params_args = []
    for arg in args[1:]:
        if arg.startswith("http://") or arg.startswith("https://"):
            url = arg
        else:
            params_args.append(arg)

    if not url:
        url = args[1]
        params_args = args[2:]

    is_random = False
    count = None
    from_idx = None
    to_idx = None

    for arg in params_args:
        if arg.lower() == "-random":
            is_random = True
        elif re.match(r"^-\d+$", arg):
            count = int(arg[1:])
        elif arg.lower().startswith("-от_"):
            try: from_idx = int(arg.split("_")[1])
            except ValueError: pass
        elif arg.lower().startswith("-до_"):
            try: to_idx = int(arg.split("_")[1])
            except ValueError: pass

    platform = detect_platform(url)
    status_msg = await message.reply(format_styled_message(emoji="⚙️", title=f"Анализ {platform}", message="Пожалуйста, подождите..."))

    loop = asyncio.get_running_loop()
    info = await loop.run_in_executor(None, _sync_get_info, url)

    if not info:
        await status_msg.edit_text(format_styled_message(emoji="❌", title=f"Ошибка {platform}", message="Не удалось извлечь данные."))
        return

    if 'entries' in info or info.get('_type') == 'playlist':
        playlist_title = info.get('title', 'Плейлист')
        safe_playlist_title = "".join([c for c in playlist_title if c not in ['/', '\\', '?', '%', '*', ':', '|', '"', '<', '>']])

        entries = list(info.get('entries', []))
        if not entries:
            await status_msg.edit_text(format_styled_message(emoji="❌", title="Ошибка плейлиста", message="В данном плейлисте нет доступных треков."))
            return

        start = (from_idx - 1) if from_idx is not None else 0
        end = to_idx if to_idx is not None else len(entries)
        entries = entries[max(0, start):min(len(entries), end)]

        if is_random:
            random.shuffle(entries)

        if count is not None:
            entries = entries[:count]
        elif is_random and from_idx is None and to_idx is None:
            entries = entries[:1]

        if not entries:
            await status_msg.edit_text(format_styled_message(emoji="❌", title="Ошибка параметров", message="По заданным критериям треков не найдено."))
            return

        await status_msg.edit_text(format_styled_message(emoji="📦", title=f"Обнаружен плейлист ({len(entries)} треков)", message="Загрузка треков..."))

        playlist_id = str(uuid.uuid4())[:8]
        temp_playlist_dir = os.path.join(YT_DOWNLOAD_DIR, f"playlist_{playlist_id}")
        os.makedirs(temp_playlist_dir, exist_ok=True)

        downloaded_files = []
        for idx, entry in enumerate(entries, 1):
            entry_url = entry.get('url') or entry.get('webpage_url') or entry.get('id')
            if not entry_url:
                continue
            if not str(entry_url).startswith("http"):
                entry_url = f"https://www.youtube.com/watch?v={entry_url}"

            await status_msg.edit_text(format_styled_message(emoji="⏳", title="Скачивание", message=f"Загрузка трека {idx}/{len(entries)}..."))
            media_data = await loop.run_in_executor(None, _sync_download_playlist_item, entry_url, temp_playlist_dir)
            if media_data and os.path.exists(media_data["file_path"]):
                downloaded_files.append(media_data["file_path"])

        if not downloaded_files:
            await status_msg.edit_text(format_styled_message(emoji="❌", title="Ошибка", message="Не удалось загрузить ни одного трека."))
            shutil.rmtree(temp_playlist_dir, ignore_errors=True)
            return

        if len(downloaded_files) == 1:
            single_file = downloaded_files[0]
            await status_msg.edit_text(format_styled_message(emoji="⏳", title="Отправка", message="Отправка трека..."))

            tg_file = FSInputFile(single_file, filename=os.path.basename(single_file))
            caption = format_styled_message(emoji="🎵", title="Трек", message="Скачано ботом")

            try: 
                await message.reply_audio(audio=tg_file, caption=caption)
            except Exception:
                try: 
                    await message.chat.send_audio(audio=tg_file, caption=caption)
                except Exception as e: 
                    logger.error(f"Ошибка отправки одиночного аудио из плейлиста: {e}")

            await status_msg.edit_text(format_styled_message(emoji="🎬", title="Результат", message="✅ <b>Трек успешно отправлен!</b>"))
            shutil.rmtree(temp_playlist_dir, ignore_errors=True)
            return

        await status_msg.edit_text(format_styled_message(emoji="📦", title="Упаковка", message="Формируем ZIP-архивы..."))

        zip_groups = []
        current_group = []
        current_size = 0
        MAX_ZIP_SIZE = 49 * 1024 * 1024

        for f_path in downloaded_files:
            f_size = os.path.getsize(f_path)
            if current_size + f_size > MAX_ZIP_SIZE and current_group:
                zip_groups.append(current_group)
                current_group = [f_path]
                current_size = f_size
            else:
                current_group.append(f_path)
                current_size += f_size
        if current_group:
            zip_groups.append(current_group)

        for z_idx, group in enumerate(zip_groups, 1):
            await status_msg.edit_text(format_styled_message(emoji="⏳", title="Отправка", message=f"Отправка архива {z_idx}/{len(zip_groups)}..."))

            if len(zip_groups) > 1:
                caption = format_styled_message(emoji="📦", title=f"{safe_playlist_title} (Часть {z_idx}/{len(zip_groups)})", message="Скачано ботом")
            else:
                caption = format_styled_message(emoji="📦", title=safe_playlist_title, message="Скачано ботом")

            zip_filename = os.path.join(YT_DOWNLOAD_DIR, zip_name)

            with zipfile.ZipFile(zip_filename, 'w', zipfile.ZIP_DEFLATED) as zipf:
                for f_path in group:
                    zipf.write(f_path, os.path.basename(f_path))

            tg_file = FSInputFile(zip_filename, filename=zip_name)

            try:
                await message.reply_document(document=tg_file, caption=caption)
            except Exception:
                try:
                    await message.chat.send_document(document=tg_file, caption=caption)
                except Exception as e: 
                    logger.error(f"Ошибка отправки ZIP: {e}")

            if os.path.exists(zip_filename):
                os.remove(zip_filename)

        await status_msg.edit_text(format_styled_message(emoji="🎬", title="Результат", message="✅ <b>Архивы успешно отправлены!</b>"))
        shutil.rmtree(temp_playlist_dir, ignore_errors=True)
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
            if platform == "TikTok": h = "Видео"
            else: continue

        current_size = f.get('filesize') or f.get('filesize_approx') or 0
        if h not in heights_dict or current_size > heights_dict[h].get('size', 0):
            heights_dict[h] = {
                'format_id': f.get('format_id'),
                'size': current_size,
                'acodec': f.get('acodec')
            }

    def format_size(bytes_size):
        if not bytes_size: return "размер неизвестен"
        mb = bytes_size / (1024 * 1024)
        return f"{mb:.1f} MB"

    choices = {}
    inline_keyboard = []

    sorted_heights = sorted([k for k in heights_dict.keys() if isinstance(k, int)], reverse=True)
    str_heights = [k for k in heights_dict.keys() if isinstance(k, str)]
    sorted_heights.extend(str_heights)

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
        warn = f" ⚠️ >{YT_MAX_FILE_SIZE_MB}MB" if total_size > YT_MAX_FILE_SIZE_MB * 1024 * 1024 else ""

        label = f"{h}p" if isinstance(h, int) else str(h)
        btn_text = f"🎬 {label} ({size_str}){warn}"
        inline_keyboard.append([InlineKeyboardButton(text=btn_text, callback_data=f"yt_dl|{choice_key}|{request_id}")])

    if best_aud:
        choice_key = "audio"
        choices[choice_key] = {
            "size": audio_size,
            "format_str": audio_format_id if audio_format_id else "bestaudio/best",
            "type": "audio"
        }
        size_str = format_size(audio_size)
        warn = f" ⚠️ >{YT_MAX_FILE_SIZE_MB}MB" if audio_size > YT_MAX_FILE_SIZE_MB * 1024 * 1024 else ""
        btn_text = f"🎵 Только Звук ({size_str}){warn}"
        inline_keyboard.append([InlineKeyboardButton(text=btn_text, callback_data=f"yt_dl|{choice_key}|{request_id}")])

    pending_requests[request_id] = {
        "url": url,
        "formats": choices,
        "platform": platform
    }

    keyboard = create_user_keyboard(inline_keyboard, message.from_user.id)
    video_title = info.get('title', 'Unknown Media')

    await status_msg.edit_text(
        format_styled_message(emoji=API_ICON, title=video_title, message="Выберите формат:"),
        reply_markup=keyboard
    )
    return


async def process_yt_callback(callback: types.CallbackQuery):
    _, choice_key, req_id = callback.data.split("|")

    req_data = pending_requests.get(req_id)
    if not req_data:
        await callback.message.edit_text(format_styled_message(emoji="❌", title="Ошибка", message="Ссылка устарела. Повторите запрос."))
        return

    choice_data = req_data["formats"].get(choice_key)
    if not choice_data:
        await callback.message.edit_text(format_styled_message(emoji="❌", title="Ошибка", message="Формат недоступен."))
        return

    limit_bytes = YT_MAX_FILE_SIZE_MB * 1024 * 1024
    if choice_data["size"] > limit_bytes:
        size_mb = choice_data["size"] / (1024 * 1024)
        await callback.answer(
            text=f"❌ Файл ({size_mb:.1f} MB) превышает лимит {YT_MAX_FILE_SIZE_MB} MB.",
            show_alert=True
        )
        return

    url = req_data["url"]
    platform = req_data.get("platform", "YouTube")
    del pending_requests[req_id]

    queue_position = download_queue.qsize() + 1
    await callback.message.edit_text(format_styled_message(emoji="⏳", title="Статус", message=f"Добавлено в очередь ({queue_position})..."))

    await download_queue.put({
        'original_message': callback.message.reply_to_message or callback.message,
        'status_message': callback.message,
        'url': url,
        'format_choice': choice_data["format_str"],
        'type': choice_data["type"],
        'platform': platform
    })

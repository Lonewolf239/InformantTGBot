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
from config import YT_DOWNLOAD_DIR, YT_MAX_FILE_SIZE_MB, COOKIES_FILE, COMMAND_METADATA
from bot.utils.helpers import create_user_keyboard, format_styled_message, spend_tokens

logger = logging.getLogger(__name__)

API_ICON = COMMAND_METADATA["!скачать"]["icon"]
API_NAME = COMMAND_METADATA["!скачать"]["name"]

os.makedirs(YT_DOWNLOAD_DIR, exist_ok=True)
pending_requests = {}
download_queue = asyncio.Queue(maxsize=50)


def get_base_ydl_opts() -> dict:
    opts = {
        'quiet': True,
        'no_warnings': True,
        'nocheckcertificate': True,
        'geo_bypass': True,
        'headers': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36'
        },
        'extractor_args': {'youtube': {'player_client': ['android', 'web', 'mweb', 'ios']}},
    }

    if os.path.exists(COOKIES_FILE):
        opts['cookiefile'] = COOKIES_FILE

    return opts


def sanitize_filename(name: str) -> str:
    return re.sub(r'[\\/*?:"<>|%]', '', name)


def extract_audio_tags(media_data: dict) -> tuple:
    artist = media_data.get('artist')
    track = media_data.get('track')
    raw_title = media_data.get('title', 'Unknown Media')

    if not artist or not track:
        if " - " in raw_title:
            parts = raw_title.split(" - ", 1)
            artist = parts[0].strip()
            track = parts[1].strip()
        else:
            artist = media_data.get('uploader', 'Unknown Artist')
            track = raw_title

    track = re.sub(r'\s*[\(\[].*?[\)\]]', '', track).strip().strip('"\'').strip()
    return track, artist


def detect_platform(url: str) -> str:
    url_lower = url.lower()
    if "tiktok.com" in url_lower: return "TikTok"
    if "youtube.com" in url_lower or "youtu.be" in url_lower: return "YouTube"
    if "twitter.com" in url_lower or "x.com" in url_lower: return "Twitter/X"
    if "instagram.com" in url_lower: return "Instagram"
    if "vk.com" in url_lower or "vk.video" in url_lower: return "VK"
    if "reddit.com" in url_lower: return "Reddit"
    return "Сайта"


def _sync_get_info(url: str) -> Optional[dict]:
    ydl_opts = get_base_ydl_opts()
    ydl_opts.update({
        'skip_download': True,
        'extract_flat': 'in_playlist',
    })
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            return ydl.extract_info(url, download=False)
    except Exception as e:
        logger.error(f"Ошибка получения информации о медиа {url}: {e}")
        return None


def _sync_download(url: str, format_str: str, media_type: str) -> Optional[Dict[str, Any]]:
    ydl_opts = get_base_ydl_opts()
    ydl_opts.update({
        'outtmpl': f'{YT_DOWNLOAD_DIR}/%(title)s.%(ext)s',
        'noplaylist': True,
        'format': format_str,
        'writethumbnail': True,
    })

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
            if not info:
                return None

            filename = info['requested_downloads'][0].get('filepath') if 'requested_downloads' in info and info['requested_downloads'] else ydl.prepare_filename(info)

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
                "uploader": info.get("uploader", "Unknown Artist"),
                "artist": info.get("artist"),
                "track": info.get("track"),
                "duration": info.get("duration", 0),
                "file_path": filename,
                "type": media_type,
            }
    except Exception as e:
        logger.error(f"Ошибка yt-dlp при скачивании {url}: {e}")
        return None


def _sync_download_playlist_item(url: str, output_dir: str) -> Optional[Dict[str, Any]]:
    ydl_opts = get_base_ydl_opts()
    ydl_opts.update({
        'outtmpl': f'{output_dir}/%(uploader|Неизвестен)s - %(title)s.%(ext)s',
        'noplaylist': True,
        'format': 'bestaudio/best',
        'ignoreerrors': True,
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }],
    })
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            if not info:
                return None

            filename = info['requested_downloads'][0].get('filepath') if 'requested_downloads' in info and info['requested_downloads'] else ydl.prepare_filename(info)
            filename = os.path.splitext(filename)[0] + '.mp3'

            return {
                "file_path": filename,
                "title": info.get("title", "Unknown Track"),
                "uploader": info.get("uploader", "Unknown Artist"),
            }
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

    media_path = None
    thumbnail_path = None

    try:
        os.makedirs(YT_DOWNLOAD_DIR, exist_ok=True)
        await message.edit_text(format_styled_message(emoji="⏳", title=API_NAME, message=f"Скачивание файла... ({platform})"))

        loop = asyncio.get_running_loop()
        media_data = await loop.run_in_executor(None, _sync_download, url, format_choice, media_type)

        if not media_data or not os.path.exists(media_data["file_path"]):
            await message.edit_text(format_styled_message(emoji="❌", title=API_NAME, message=f"Не удалось получить доступ к медиа ({platform})."))
            return

        media_path = media_data["file_path"]
        file_size_bytes = os.path.getsize(media_path)
        limit_bytes = YT_MAX_FILE_SIZE_MB * 1024 * 1024

        if file_size_bytes > limit_bytes:
            await message.edit_text(
                format_styled_message(
                    emoji="❌", title=API_NAME,
                    message=(f"Ошибка лимита: Итоговый файл весит <b>{file_size_bytes / (1024 * 1024):.1f} MB</b>.\n"
                             f"Telegram запрещает ботам отправлять файлы тяжелее {YT_MAX_FILE_SIZE_MB} MB.")
                )
            )
            return

        await message.edit_text(format_styled_message(emoji="⏳", title=API_NAME, message="Отправка в Telegram..."))

        original_title = sanitize_filename(media_data['title'])
        file_ext = os.path.splitext(media_path)[1]
        telegram_filename = f"{original_title}{file_ext}"

        file = FSInputFile(media_path, filename=telegram_filename)
        caption = format_styled_message(emoji=API_ICON, title=f"{API_NAME} ({platform})", message=f"<b>{media_data['title']}</b>")

        base_path = os.path.splitext(media_path)[0]
        for ext in ['.jpg', '.webp', '.png']:
            if os.path.exists(base_path + ext):
                thumbnail_path = base_path + ext
                break

        track_title, artist_name = extract_audio_tags(media_data)

        try:
            if media_type == "audio":
                await original_message.reply_audio(
                    audio=file, caption=caption, title=track_title, performer=artist_name,
                    thumbnail=FSInputFile(thumbnail_path) if thumbnail_path else None
                )
            else: 
                await original_message.reply_video(video=file, caption=caption)

        except TelegramAPIError as e:
            err_msg = str(e).lower()
            if "reply" in err_msg or "not found" in err_msg:
                if media_type == "audio":
                    await message.chat.send_audio(
                        audio=file, caption=caption, title=track_title, performer=artist_name,
                        thumbnail=FSInputFile(thumbnail_path) if thumbnail_path else None
                    )
                else:
                    await message.chat.send_video(video=file, caption=caption)
            else:
                try:
                    await original_message.reply_document(document=file, caption=caption + "\n<i>(Отправлено файлом из-за лимитов Telegram)</i>")
                except Exception:
                    await message.chat.send_document(document=file, caption=caption)

        from bot.utils.database import db
        await db.increment_commands()
        await db.log_command("!скачать", message.from_user.id)
        await spend_tokens(message, "!скачать")

        await message.edit_text(format_styled_message(emoji=API_ICON, title=API_NAME, message=f"✅ <b>{original_title} успешно загружено!</b>"))

    except Exception as e:
        logger.error(f"Внутренняя ошибка обработки: {e}")
        await message.edit_text(format_styled_message(emoji="❌", title=API_NAME, message="Произошла внутренняя ошибка сервера."))

    finally:
        if media_path and os.path.exists(media_path): os.remove(media_path)
        if thumbnail_path and os.path.exists(thumbnail_path): os.remove(thumbnail_path)


async def download_worker():
    while True:
        try:
            task_data = await download_queue.get()
            try:
                await process_download_task(task_data)
            except Exception as e:
                logger.error(f"Критическая ошибка при скачивании файла: {e}")
            finally:
                download_queue.task_done()
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error(f"Глобальная ошибка воркера YouTube: {e}")
            await asyncio.sleep(1)


async def cmd_download_yt(message: types.Message):
    args = message.text.split()
    if len(args) < 2:
        usage_text = (
            "<code>!скачать</code> [ссылка] [параметры]\n\n"
            "<b>Параметры для плейлистов:</b>\n"
            "• <code>-random</code> — 1 случайный трек\n"
            "• <code>-X</code> — скачать X треков (например: -5)\n"
            "• <code>-от_X</code> — начать с трека №X\n"
            "• <code>-до_X</code> — закончить на №X\n\n"
            "<i>💡 Можно комбинировать: <code>-random -5</code></i>"
        )
        await message.reply(format_styled_message(emoji=API_ICON, title=API_NAME, message=usage_text))
        return

    url = next((arg for arg in args[1:] if arg.startswith("http://") or arg.startswith("https://")), args[1])
    params_args = [arg for arg in args[1:] if not arg.startswith("http")]

    is_random = "-random" in [a.lower() for a in params_args]
    count, from_idx, to_idx = None, None, None

    for arg in params_args:
        if re.match(r"^-\d+$", arg): count = int(arg[1:])
        elif arg.lower().startswith("-от_"):
            try: from_idx = int(arg.split("_")[1])
            except ValueError: pass
        elif arg.lower().startswith("-до_"):
            try: to_idx = int(arg.split("_")[1])
            except ValueError: pass

    if "x.com/" in url.lower():
        url = re.sub(r"https?://(?:www\.)?x\.com/", "https://twitter.com/", url)

    platform = detect_platform(url)
    status_msg = await message.reply(format_styled_message(emoji="⏳", title=API_NAME, message=f"Анализ ссылки ({platform}), подождите..."))

    loop = asyncio.get_running_loop()
    info = await loop.run_in_executor(None, _sync_get_info, url)

    if not info:
        await status_msg.edit_text(format_styled_message(emoji="❌", title=API_NAME, message=f"Не удалось извлечь данные с {platform}."))
        return

    if 'entries' in info or info.get('_type') == 'playlist':
        playlist_title = info.get('title', 'Плейлист')
        safe_playlist_title = sanitize_filename(playlist_title)

        entries = list(info.get('entries', []))
        if not entries:
            await status_msg.edit_text(format_styled_message(emoji="❌", title=API_NAME, message="В данном плейлисте нет доступных треков."))
            return

        start = (from_idx - 1) if from_idx is not None else 0
        end = to_idx if to_idx is not None else len(entries)
        entries = entries[max(0, start):min(len(entries), end)]

        if is_random: random.shuffle(entries)
        if count is not None: entries = entries[:count]
        elif is_random and from_idx is None and to_idx is None: entries = entries[:1]

        if not entries:
            await status_msg.edit_text(format_styled_message(emoji="❌", title=API_NAME, message="По заданным критериям треков не найдено."))
            return

        await status_msg.edit_text(format_styled_message(emoji="⏳", title=API_NAME, message=f"Обнаружен плейлист ({len(entries)} треков).\nЗагрузка..."))

        temp_playlist_dir = os.path.join(YT_DOWNLOAD_DIR, f"playlist_{uuid.uuid4().hex[:8]}")
        os.makedirs(temp_playlist_dir, exist_ok=True)

        from config import COMMAND_COSTS, VIP_IDS, PAYMENTS_ENABLED
        user_id = message.from_user.id
        is_vip = user_id in VIP_IDS
        cost = COMMAND_COSTS.get("!скачать", 0)
        insufficient_funds = False

        if PAYMENTS_ENABLED:
            from bot.utils.tokens_database import tokens_db

        downloaded_files = []
        for idx, entry in enumerate(entries, 1):
            if PAYMENTS_ENABLED and not is_vip and cost > 0:
                has_tokens = await tokens_db.has_enough_tokens(user_id, cost)
                if not has_tokens:
                    insufficient_funds = True
                    break

            entry_url = entry.get('url') or entry.get('webpage_url') or entry.get('id')
            if not entry_url: continue
            if not str(entry_url).startswith("http"): entry_url = f"https://www.youtube.com/watch?v={entry_url}"

            await status_msg.edit_text(format_styled_message(emoji="⏳", title=API_NAME, message=f"Скачивание: загрузка трека {idx}/{len(entries)}..."))
            media_data = await loop.run_in_executor(None, _sync_download_playlist_item, entry_url, temp_playlist_dir)

            if media_data and os.path.exists(media_data["file_path"]):
                downloaded_files.append(media_data)

                if PAYMENTS_ENABLED and not is_vip and cost > 0:
                    await tokens_db.spend_tokens(user_id, cost)

        if not downloaded_files:
            if insufficient_funds:
                err_msg = "У тебя недостаточно токенов даже для загрузки первого трека!"
            else:
                err_msg = "Не удалось загрузить ни одного трека."
            await status_msg.edit_text(format_styled_message(emoji="❌", title=API_NAME, message=err_msg))
            shutil.rmtree(temp_playlist_dir, ignore_errors=True)
            return

        if len(downloaded_files) == 1:
            media_info = downloaded_files[0]
            single_file = media_info["file_path"]

            await status_msg.edit_text(format_styled_message(emoji="⏳", title=API_NAME, message="Отправка трека в Telegram..."))
            tg_file = FSInputFile(single_file, filename=os.path.basename(single_file))
            caption = format_styled_message(emoji="🎵", title=f"{API_NAME} ({platform})", message=f"<b>{os.path.basename(single_file)}</b>")

            track_title, artist_name = extract_audio_tags(media_info)

            try: 
                await message.reply_audio(audio=tg_file, caption=caption, title=track_title, performer=artist_name)
            except Exception:
                try: await message.chat.send_audio(audio=tg_file, caption=caption, title=track_title, performer=artist_name)
                except Exception as e: logger.error(f"Ошибка отправки одиночного аудио из плейлиста: {e}")

            from bot.utils.database import db
            await db.increment_commands()
            await db.log_command("!скачать", message.from_user.id)

            warning_msg = "\n\n⚠️ <i>Скачивание плейлиста прервано: закончились токены!</i>" if insufficient_funds else ""
            await status_msg.edit_text(format_styled_message(emoji=API_ICON, title=API_NAME, message=f"✅ <b>Трек успешно отправлен!</b>{warning_msg}"))
            shutil.rmtree(temp_playlist_dir, ignore_errors=True)
            return

        await status_msg.edit_text(format_styled_message(emoji="⏳", title=API_NAME, message="Упаковка: формируем ZIP-архивы..."))

        zip_groups, current_group, current_size = [], [], 0
        MAX_ZIP_SIZE = 49 * 1024 * 1024

        for item in downloaded_files:
            f_path = item["file_path"]
            f_size = os.path.getsize(f_path)
            if current_size + f_size > MAX_ZIP_SIZE and current_group:
                zip_groups.append(current_group)
                current_group, current_size = [f_path], f_size
            else:
                current_group.append(f_path)
                current_size += f_size
        if current_group: zip_groups.append(current_group)

        for z_idx, group in enumerate(zip_groups, 1):
            await status_msg.edit_text(format_styled_message(emoji="⏳", title=API_NAME, message=f"Отправка архива {z_idx}/{len(zip_groups)}..."))

            is_multi = len(zip_groups) > 1
            caption_msg = f"<b>{safe_playlist_title}</b> (Часть {z_idx}/{len(zip_groups)})" if is_multi else f"<b>{safe_playlist_title}</b>"
            caption = format_styled_message(emoji="📦", title=f"{API_NAME} ({platform})", message=caption_msg)
            zip_name = f"{safe_playlist_title}_part{z_idx}.zip" if is_multi else f"{safe_playlist_title}.zip"

            zip_filename = os.path.join(YT_DOWNLOAD_DIR, zip_name)
            with zipfile.ZipFile(zip_filename, 'w', zipfile.ZIP_DEFLATED) as zipf:
                for f_path in group: zipf.write(f_path, os.path.basename(f_path))

            tg_file = FSInputFile(zip_filename, filename=zip_name)
            try: await message.reply_document(document=tg_file, caption=caption)
            except Exception:
                try: await message.chat.send_document(document=tg_file, caption=caption)
                except Exception as e: logger.error(f"Ошибка отправки ZIP: {e}")

            if os.path.exists(zip_filename): os.remove(zip_filename)

        from bot.utils.database import db
        await db.increment_commands()
        await db.log_command("!скачать", message.from_user.id)

        warning_msg = "\n\n⚠️ <i>Скачивание плейлиста прервано: закончились токены! Выдана часть архивов.</i>" if insufficient_funds else ""
        await status_msg.edit_text(format_styled_message(emoji=API_ICON, title=API_NAME, message=f"✅ <b>Архивы успешно отправлены!</b>{warning_msg}"))
        shutil.rmtree(temp_playlist_dir, ignore_errors=True)
        return

    request_id = uuid.uuid4().hex[:8]
    formats = info.get('formats', [])

    audio_formats = [f for f in formats if f.get('vcodec') == 'none' and f.get('acodec') != 'none']
    best_aud = audio_formats[-1] if audio_formats else {}
    audio_size = best_aud.get('filesize') or best_aud.get('filesize_approx') or 0
    audio_format_id = best_aud.get('format_id') or "bestaudio/best"

    video_formats = [f for f in formats if f.get('vcodec') != 'none' and f.get('vcodec') is not None]
    heights_dict = {}

    for f in video_formats:
        h = f.get('height')
        if not h:
            res = f.get('resolution')
            if isinstance(res, str) and 'x' in res:
                try: h = int(res.split('x')[1])
                except ValueError: pass
        if not h:
            note = f.get('format_note')
            if isinstance(note, str) and 'p' in note:
                try: h = int(re.sub(r'\D', '', note))
                except ValueError: pass
        if not h: h = "Видео"

        current_size = f.get('filesize') or f.get('filesize_approx') or 0
        new_entry = {'format_id': f.get('format_id'), 'size': current_size, 'acodec': f.get('acodec')}

        if h not in heights_dict or (current_size > 0 or heights_dict[h]['size'] == 0):
            heights_dict[h] = new_entry

    def format_size(bytes_size):
        return f"{bytes_size / (1024 * 1024):.1f} MB" if bytes_size else "неизвестно"

    choices = {}
    inline_keyboard = []

    sorted_heights = sorted([k for k in heights_dict.keys() if isinstance(k, int)], reverse=True) + \
                     [k for k in heights_dict.keys() if isinstance(k, str)]

    for h in sorted_heights:
        v_info = heights_dict[h]
        v_size, acodec = v_info['size'], v_info.get('acodec')
        is_video_only = (acodec == 'none' or acodec is None)

        total_size = (v_size + audio_size) if is_video_only and v_size else v_size
        format_str = f"{v_info['format_id']}+{audio_format_id}" if is_video_only else v_info['format_id']

        choice_key = f"vid_{h}"
        choices[choice_key] = {"size": total_size, "format_str": format_str, "type": "video"}

        warn = f" ⚠️ >{YT_MAX_FILE_SIZE_MB}MB" if total_size > YT_MAX_FILE_SIZE_MB * 1024 * 1024 else ""
        label = f"{h}p" if isinstance(h, int) else str(h)
        btn_text = f"🎬 {label} ({format_size(total_size)}){warn}"

        inline_keyboard.append([InlineKeyboardButton(text=btn_text, callback_data=f"yt_dl|{choice_key}|{request_id}")])

    choices["audio"] = {"size": audio_size, "format_str": audio_format_id, "type": "audio"}
    warn = f" ⚠️ >{YT_MAX_FILE_SIZE_MB}MB" if audio_size > YT_MAX_FILE_SIZE_MB * 1024 * 1024 else ""
    inline_keyboard.append([InlineKeyboardButton(text=f"🎵 Только Звук ({format_size(audio_size)}){warn}", callback_data=f"yt_dl|audio|{request_id}")])

    if len(choices) == 1:
        choices["best_auto"] = {"size": 0, "format_str": "bestvideo+bestaudio/best", "type": "video"}
        inline_keyboard.insert(0, [InlineKeyboardButton(text="🎬 Скачать (Лучшее качество)", callback_data=f"yt_dl|best_auto|{request_id}")])

    pending_requests[request_id] = {"url": url, "formats": choices, "platform": platform}

    await status_msg.edit_text(
        format_styled_message(emoji=API_ICON, title=f"{API_NAME} ({platform})", message=f"<b>{info.get('title', 'Unknown Media')}</b>\n\nВыберите формат:"),
        reply_markup=create_user_keyboard(inline_keyboard, message.from_user.id)
    )


async def process_yt_callback(callback: types.CallbackQuery):
    _, choice_key, req_id = callback.data.split("|")

    req_data = pending_requests.get(req_id)
    if not req_data:
        await callback.message.edit_text(format_styled_message(emoji="❌", title=API_NAME, message="Ссылка устарела. Повторите запрос."))
        return

    choice_data = req_data["formats"].get(choice_key)
    if not choice_data:
        await callback.message.edit_text(format_styled_message(emoji="❌", title=API_NAME, message="Формат недоступен."))
        return

    if choice_data["size"] > YT_MAX_FILE_SIZE_MB * 1024 * 1024:
        await callback.answer(text=f"❌ Файл ({choice_data['size'] / (1024 * 1024):.1f} MB) превышает лимит {YT_MAX_FILE_SIZE_MB} MB.", show_alert=True)
        return

    url, platform = req_data["url"], req_data.get("platform", "YouTube")
    del pending_requests[req_id]

    await callback.message.edit_text(format_styled_message(
        emoji="⏳", title=API_NAME, 
        message=f"Добавлено в очередь (позиция {download_queue.qsize() + 1}).\nПожалуйста, ожидайте..."
    ))

    try:
        download_queue.put_nowait({
            'original_message': callback.message.reply_to_message or callback.message,
            'status_message': callback.message,
            'url': url,
            'format_choice': choice_data["format_str"],
            'type': choice_data["type"],
            'platform': platform
        })
    except asyncio.QueueFull:
        await callback.answer("❌ Очередь загрузок переполнена (макс. 50). Попробуйте позже.", show_alert=True)
        return

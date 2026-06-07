import logging
import asyncio
import os
import uuid
import re
import yt_dlp
from aiogram import types
from aiogram.types import FSInputFile, InlineKeyboardButton
from config import YT_DOWNLOAD_DIR, YT_MAX_FILE_SIZE_MB, COOKIES_FILE
from bot.utils.helpers import format_styled_message, create_user_keyboard
from bot.utils.database import db

API_ICON = "🎵"
API_NAME = "Музыка"

logger = logging.getLogger(__name__)

os.makedirs(YT_DOWNLOAD_DIR, exist_ok=True)
music_search_cache = {}


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
            artist = media_data.get('uploader', media_data.get('channel', 'Unknown Artist'))
            track = raw_title

    track = re.sub(r'\s*[\(\[].*?[\)\]]', '', track).strip().strip('"\'').strip()

    if artist and artist.endswith(" - Topic"):
        artist = artist.replace(" - Topic", "")

    return track, artist


def get_yt_search_opts() -> dict:
    opts = {
        'quiet': True,
        'extract_flat': 'in_playlist',
        'skip_download': True,
        'no_warnings': True,
        'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    }
    if os.path.exists(COOKIES_FILE):
        opts['cookiefile'] = COOKIES_FILE
    return opts


def get_yt_audio_opts(output_path: str) -> dict:
    opts = {
        'quiet': True,
        'no_warnings': True,
        'format': 'm4a/bestaudio/best',
        'outtmpl': output_path,
        'writethumbnail': True,
        'extractor_args': {'youtube': {'player_client': ['android', 'web', 'mweb', 'ios']}},
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }],
    }
    if os.path.exists(COOKIES_FILE):
        opts['cookiefile'] = COOKIES_FILE
    return opts


def _sync_search_music(query: str, limit: int = 5) -> list:
    opts = get_yt_search_opts()
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(f"ytsearch{limit}:{query} official audio", download=False)

            entries = info.get('entries', [])
            return [e for e in entries if e]

    except Exception as e:
        logger.error(f"Ошибка поиска: {e}")
        return []


def _sync_download_audio(url: str, request_id: str) -> dict:
    temp_path = os.path.join(YT_DOWNLOAD_DIR, f"music_{request_id}")
    opts = get_yt_audio_opts(temp_path + ".%(ext)s")

    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=True)
            if not info:
                return None

            filename = ydl.prepare_filename(info)
            base_path = os.path.splitext(filename)[0]
            final_path = base_path + ".mp3"

            thumbnail_path = None
            for ext in ['.jpg', '.webp', '.png']:
                if os.path.exists(base_path + ext):
                    thumbnail_path = base_path + ext
                    break

            track, artist = extract_audio_tags(info)

            return {
                "file_path": final_path,
                "thumbnail_path": thumbnail_path,
                "track": track,
                "artist": artist,
                "raw_title": info.get("title", "Unknown Track")
            }
    except Exception as e:
        logger.error(f"Ошибка скачивания трека: {e}")
        return None


def format_duration(seconds: int) -> str:
    if not seconds: return "?:??"
    return f"{int(seconds // 60)}:{int(seconds % 60):02d}"


async def cmd_music(message: types.Message):
    args = message.text.split(maxsplit=1)

    if len(args) < 2:
        error_msg = format_styled_message(
            emoji=API_ICON,
            title=API_NAME,
            message="❌ <b>Не указано название.</b>\n📝 Пример: <code>!трек Bring Me The Horizon</code>"
        )
        await message.reply(error_msg)
        return True

    query = args[1].strip()
    status_msg = await message.reply(
        format_styled_message(emoji="🔍", title=API_NAME, message=f"Ищу трек: <b>{query}</b>...")
    )

    loop = asyncio.get_running_loop()
    results = await loop.run_in_executor(None, _sync_search_music, query)

    if not results:
        await status_msg.edit_text(
            format_styled_message(emoji="❌", title=API_NAME, message="По вашему запросу ничего не найдено.")
        )
        return True

    request_id = uuid.uuid4().hex[:8]
    music_search_cache[request_id] = {}

    inline_keyboard = []

    for idx, entry in enumerate(results, 1):
        url = entry.get('url')

        track_name, artist_name = extract_audio_tags(entry)
        duration = format_duration(entry.get('duration', 0))

        display_name = f"{artist_name} — {track_name}"

        music_search_cache[request_id][str(idx)] = {
            "url": url,
            "title": display_name
        }

        btn_text = f"⬇️ {display_name} [{duration}]"
        if len(btn_text) > 60:
            btn_text = btn_text[:57] + "..."

        inline_keyboard.append([
            InlineKeyboardButton(text=btn_text, callback_data=f"mus_dl|{request_id}|{idx}")
        ])

    result_text = f"🔎 <b>Результаты по запросу:</b> <i>{query}</i>\n\nВыберите нужный трек ниже:"

    await status_msg.edit_text(
        format_styled_message(emoji=API_ICON, title=API_NAME, message=result_text),
        reply_markup=create_user_keyboard(inline_keyboard, message.from_user.id)
    )

    from config import COMMAND_COSTS, VIP_IDS, PAYMENTS_ENABLED
    if PAYMENTS_ENABLED:
        from bot.utils.tokens_database import tokens_db
        cost = COMMAND_COSTS.get("!музыка", 0)
        if cost > 0 and message.from_user.id not in VIP_IDS:
            await tokens_db.spend_tokens(message.from_user.id, cost)

    await db.increment_commands()
    await db.log_command("!музыка", message.from_user.id)
    return True


async def process_music_callback(callback: types.CallbackQuery):
    _, req_id, track_idx = callback.data.split("|")

    cache_data = music_search_cache.get(req_id)
    if not cache_data or track_idx not in cache_data:
        await callback.message.edit_text(
            format_styled_message(emoji="❌", title=API_NAME, message="Время поиска истекло. Пожалуйста, введите команду заново.")
        )
        return

    track_data = cache_data[track_idx]
    url = track_data["url"]

    del music_search_cache[req_id]

    await callback.message.edit_text(
        format_styled_message(emoji="⏳", title=API_NAME, message=f"Загружаю трек: <b>{track_data['title']}</b>...")
    )

    loop = asyncio.get_running_loop()
    media_info = await loop.run_in_executor(None, _sync_download_audio, url, req_id)

    if not media_info or not os.path.exists(media_info["file_path"]):
        await callback.message.edit_text(
            format_styled_message(emoji="❌", title=API_NAME, message="Не удалось загрузить аудио (возможно, видео имеет возрастные ограничения или заблокировано).")
        )
        return

    file_path = media_info["file_path"]
    thumbnail_path = media_info.get("thumbnail_path")
    file_size = os.path.getsize(file_path)

    if file_size > YT_MAX_FILE_SIZE_MB * 1024 * 1024:
        await callback.message.edit_text(
            format_styled_message(emoji="❌", title=API_NAME, message=f"Файл слишком большой (> {YT_MAX_FILE_SIZE_MB}MB).")
        )
        os.remove(file_path)
        if thumbnail_path and os.path.exists(thumbnail_path):
            os.remove(thumbnail_path)
        return

    await callback.message.edit_text(
        format_styled_message(emoji="⏳", title=API_NAME, message="Отправка в Telegram...")
    )

    caption = format_styled_message(
        emoji=API_ICON, 
        title=API_NAME, 
        message=f"<b>{media_info['artist']} — {media_info['track']}</b>"
    )

    tg_file = FSInputFile(file_path)
    tg_thumb = FSInputFile(thumbnail_path) if thumbnail_path else None

    try:
        if callback.message.reply_to_message:
            await callback.message.reply_to_message.reply_audio(
                audio=tg_file, 
                caption=caption,
                title=media_info['track'],
                performer=media_info['artist'],
                thumbnail=tg_thumb
            )
        else:
            await callback.message.answer_audio(
                audio=tg_file, 
                caption=caption,
                title=media_info['track'],
                performer=media_info['artist'],
                thumbnail=tg_thumb
            )

        await callback.message.edit_text(
            format_styled_message(emoji="✅", title=API_NAME, message=f"Трек <b>{track_data['title']}</b> успешно отправлен!")
        )
    except Exception as e:
        logger.error(f"Ошибка отправки аудио: {e}")
        await callback.message.edit_text(
            format_styled_message(emoji="❌", title=API_NAME, message="Ошибка при отправке аудио в чат.")
        )
    finally:
        if os.path.exists(file_path):
            os.remove(file_path)
        if thumbnail_path and os.path.exists(thumbnail_path):
            os.remove(thumbnail_path)

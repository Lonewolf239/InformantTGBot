import logging
import asyncio
import os
import uuid
import re
import math
import yt_dlp
from aiogram import types
from aiogram.types import FSInputFile, InlineKeyboardButton
from config import YT_DOWNLOAD_DIR, YT_MAX_FILE_SIZE_MB, COOKIES_FILE, COMMAND_METADATA
from bot.utils.helpers import format_styled_message, create_user_keyboard, spend_tokens
from bot.utils.database import db

API_ICON = COMMAND_METADATA["!трек"]["icon"]
API_NAME = COMMAND_METADATA["!трек"]["name"]

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
        'source_address': '0.0.0.0',
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
        'source_address': '0.0.0.0',
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


def _sync_search_music(query: str, limit: int = 25) -> list:
    opts = get_yt_search_opts()
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(f"ytsearch{limit}:{query}", download=False)
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


def generate_music_keyboard(request_id: str, page: int, user_id: int):
    cache_data = music_search_cache.get(request_id)
    if not cache_data:
        return None

    results = cache_data["results"]
    total_pages = cache_data["total_pages"]
    per_page = 5

    start_idx = page * per_page
    end_idx = start_idx + per_page
    page_results = results[start_idx:end_idx]

    inline_keyboard = []

    for i, entry in enumerate(page_results):
        global_idx = start_idx + i
        track_name, artist_name = extract_audio_tags(entry)
        duration = format_duration(entry.get('duration', 0))

        display_name = f"{artist_name} — {track_name}"
        btn_text = f"⬇️ {display_name} [{duration}]"
        if len(btn_text) > 60:
            btn_text = btn_text[:57] + "..."

        inline_keyboard.append([
            InlineKeyboardButton(text=btn_text, callback_data=f"mus_dl|{request_id}|{global_idx}")
        ])

    nav_row = []
    if page > 0:
        nav_row.append(InlineKeyboardButton(text="⬅️ Назад", callback_data=f"mus_page|{request_id}|{page-1}"))

    if total_pages > 1:
        nav_row.append(InlineKeyboardButton(text=f"📄 {page+1}/{total_pages}", callback_data="ignore"))

    if page < total_pages - 1:
        nav_row.append(InlineKeyboardButton(text="Вперед ➡️", callback_data=f"mus_page|{request_id}|{page+1}"))

    if nav_row:
        inline_keyboard.append(nav_row)

    return create_user_keyboard(inline_keyboard, user_id)


async def cmd_music(message: types.Message):
    args = message.text.split(maxsplit=1)

    if len(args) < 2:
        error_msg = format_styled_message(
            emoji=API_ICON,
            title=API_NAME,
            message="❌ <b>Не указано название.</b>\n📝 Пример: <code>!трек Bring Me The Horizon</code>"
        )
        await message.reply(error_msg)
        return

    query = args[1].strip()
    status_msg = await message.reply(
        format_styled_message(emoji="🔍", title=API_NAME, message=f"Ищу трек: <b>{query}</b>...")
    )

    loop = asyncio.get_running_loop()
    results = await loop.run_in_executor(None, _sync_search_music, query, 25)

    if not results:
        await status_msg.edit_text(
            format_styled_message(emoji="❌", title=API_NAME, message="По вашему запросу ничего не найдено.")
        )
        return

    request_id = uuid.uuid4().hex[:8]

    music_search_cache[request_id] = {
        "query": query,
        "results": results,
        "total_pages": math.ceil(len(results) / 5)
    }

    keyboard = generate_music_keyboard(request_id, 0, message.from_user.id)
    result_text = f"🔎 <b>Результаты по запросу:</b> <i>{query}</i>\n\nВыберите нужный трек ниже:"

    await status_msg.edit_text(
        format_styled_message(emoji=API_ICON, title=API_NAME, message=result_text),
        reply_markup=keyboard
    )

    await db.increment_commands()
    await db.log_command("!музыка", message.from_user.id)
    await spend_tokens(message, "!музыка")


async def cmd_music_by_text(message: types.Message):
    args = message.text.split(maxsplit=1)

    cmd_icon = COMMAND_METADATA["!по_тексту"]["icon"]
    cmd_name = COMMAND_METADATA["!по_тексту"]["name"]

    if len(args) < 2:
        error_msg = format_styled_message(
            emoji=cmd_icon,
            title=cmd_name,
            message="❌ <b>Не указан текст песни.</b>\n📝 Пример: <code>!по_тексту я помню белые обои</code>"
        )
        await message.reply(error_msg)
        return

    raw_query = args[1].strip()

    status_msg = await message.reply(
        format_styled_message(emoji="🔍", title=cmd_name, message=f"Провожу разведку по тексту: <b>{raw_query}</b>...")
    )

    loop = asyncio.get_running_loop()

    probe_query = f'"{raw_query}" текст песни' if bool(re.search('[а-яА-Я]', raw_query)) else f'"{raw_query}" lyrics'
    probe_results = await loop.run_in_executor(None, _sync_search_music, probe_query, 5)

    if not probe_results:
        probe_query_fallback = probe_query.replace('"', '')
        probe_results = await loop.run_in_executor(None, _sync_search_music, probe_query_fallback, 5)

    best_artist = None
    best_track = None

    if probe_results:
        trash_pattern = re.compile(r'(?i)(remix|slowed|reverb|sped up|speed up|bass|phonk|8d|cover|mashup|хайтек|ремикс|кавер)')

        for res in probe_results:
            artist, track = extract_audio_tags(res)
            raw_title = res.get('title', '')

            if artist and track and artist != 'Unknown Artist':
                if not trash_pattern.search(raw_title) and not trash_pattern.search(track):
                    clean_pattern = re.compile(r'(?i)\b(lyrics|lyric video|lyric|official audio|official video|official|audio|video|music video)\b')

                    best_artist = clean_pattern.sub('', artist).strip(' -|/.,')
                    best_track = clean_pattern.sub('', track).strip(' -|/.,')
                    break

    if best_artist and best_track:
        final_query = f'{best_artist} - {best_track} official audio'
        await status_msg.edit_text(
            format_styled_message(emoji="🎯", title=cmd_name, message=f"Распознал трек: <b>{best_artist} — {best_track}</b>\nИщу оригинальное аудио...")
        )
    else:
        final_query = f'"{raw_query}" official audio -remix -slowed -phonk'
        await status_msg.edit_text(
            format_styled_message(emoji="🔍", title=cmd_name, message="Точное название вытянуть не вышло, ищу по тексту с жестким фильтром...")
        )

    final_results = await loop.run_in_executor(None, _sync_search_music, final_query, 25)

    if not final_results:
        await status_msg.edit_text(
            format_styled_message(emoji="❌", title=cmd_name, message="По вашему запросу ничего не найдено.")
        )
        return

    request_id = uuid.uuid4().hex[:8]

    music_search_cache[request_id] = {
        "query": f"Текст: {raw_query}",
        "results": final_results,
        "total_pages": math.ceil(len(final_results) / 5)
    }

    keyboard = generate_music_keyboard(request_id, 0, message.from_user.id)

    if best_artist and best_track:
        result_text = f"🎯 <b>Найдено по тексту:</b> <i>{raw_query}</i>\n🎧 <b>Оригинальный трек:</b> {best_artist} — {best_track}\n\nВыберите нужный трек ниже:"
    else:
        result_text = f"🔎 <b>Результаты по тексту:</b> <i>{raw_query}</i>\n\nВыберите нужный трек ниже:"

    await status_msg.edit_text(
        format_styled_message(emoji=cmd_icon, title=cmd_name, message=result_text),
        reply_markup=keyboard
    )

    await db.increment_commands()
    await db.log_command("!по_тексту", message.from_user.id)
    await spend_tokens(message, "!по_тексту")


async def process_music_page_callback(callback: types.CallbackQuery):
    try:
        _, req_id, page_str = callback.data.split("|")
        page = int(page_str)
    except ValueError:
        return

    keyboard = generate_music_keyboard(req_id, page, callback.from_user.id)
    if not keyboard:
        await callback.answer("⏳ Время поиска истекло. Введите команду заново.", show_alert=True)
        return

    query = music_search_cache[req_id]["query"]
    result_text = f"🔎 <b>Результаты по запросу:</b> <i>{query}</i>\n\nВыберите нужный трек ниже:"

    try:
        await callback.message.edit_text(
            format_styled_message(emoji=API_ICON, title=API_NAME, message=result_text),
            reply_markup=keyboard
        )
    except Exception:
        pass

    await callback.answer()


async def process_music_callback(callback: types.CallbackQuery):
    _, req_id, track_idx_str = callback.data.split("|")
    track_idx = int(track_idx_str)

    cache_data = music_search_cache.get(req_id)
    if not cache_data or track_idx >= len(cache_data["results"]):
        await callback.message.edit_text(
            format_styled_message(emoji="❌", title=API_NAME, message="Время поиска истекло. Пожалуйста, введите команду заново.")
        )
        return

    track_data = cache_data["results"][track_idx]
    url = track_data["url"]

    del music_search_cache[req_id]

    track_name, artist_name = extract_audio_tags(track_data)
    display_title = f"{artist_name} — {track_name}"

    await callback.message.edit_text(
        format_styled_message(emoji="⏳", title=API_NAME, message=f"Загружаю трек: <b>{display_title}</b>...")
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
            format_styled_message(emoji="✅", title=API_NAME, message=f"Трек <b>{display_title}</b> успешно отправлен!")
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

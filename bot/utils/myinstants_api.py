import aiohttp
import logging
import math
import uuid
import re
import os
import tempfile
from urllib.parse import quote
from aiogram import types
from aiogram.types import FSInputFile, InlineKeyboardButton

from config import COMMAND_METADATA
from bot.utils.helpers import (
    format_styled_message,
    create_user_keyboard,
    spend_tokens,
    get_raw_text,
)
from bot.utils.database import db

logger = logging.getLogger(__name__)

API_ICON = COMMAND_METADATA["!инстант"]["icon"]
API_NAME = COMMAND_METADATA["!инстант"]["name"]

instants_cache = {}
user_active_requests = {}


async def _scrape_myinstants(query: str = None, page: int = 1) -> list:
    if query:
        url = f"https://www.myinstants.com/ru/search/?name={quote(query)}&page={page}"
    else:
        url = f"https://www.myinstants.com/ru/categories/memes/lt/?page={page}"

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
        "Referer": "https://www.myinstants.com/",
        "Sec-Ch-Ua": '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
        "Sec-Ch-Ua-Mobile": "?0",
        "Sec-Ch-Ua-Platform": '"Windows"',
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "same-origin",
        "Upgrade-Insecure-Requests": "1",
    }

    async with aiohttp.ClientSession(headers=headers) as session:
        try:
            async with session.get(url, timeout=15) as response:
                html = await response.text()

                if response.status != 200:
                    logger.error(
                        f"[MyInstants] Ошибка: сайт вернул статус {response.status}. Возможно, сработала защита Cloudflare."
                    )
                    return []

                pattern = re.compile(
                    r"play\('([^']+)'[^)]*\).*?<a[^>]+class=[\"'][^\"']*instant-link[^\"']*[\"'][^>]*>(.*?)</a>",
                    re.DOTALL | re.IGNORECASE,
                )
                matches = pattern.findall(html)

                if not matches:
                    return []

                results = []
                seen_urls = set()

                for audio_path, name in matches:
                    if not audio_path.startswith("http"):
                        audio_path = "https://www.myinstants.com" + audio_path

                    if audio_path not in seen_urls:
                        seen_urls.add(audio_path)
                        results.append({"name": name.strip(), "url": audio_path})

                return results

        except Exception as e:
            logger.error(f"[MyInstants] Ошибка парсинга: {e}")
            return []


def generate_instants_keyboard(req_id: str, page: int, user_id: int):
    cache_data = instants_cache.get(req_id)
    if not cache_data:
        return None

    results = cache_data["results"]
    total_pages = cache_data["total_pages"]
    per_page = 6

    start_idx = page * per_page
    end_idx = start_idx + per_page
    page_results = results[start_idx:end_idx]

    inline_keyboard = []

    for i, entry in enumerate(page_results):
        global_idx = start_idx + i
        btn_text = f"🔊 {entry['name']}"
        if len(btn_text) > 40:
            btn_text = btn_text[:37] + "..."

        inline_keyboard.append(
            [
                InlineKeyboardButton(
                    text=btn_text, callback_data=f"inst_dl|{req_id}|{global_idx}"
                )
            ]
        )

    nav_row = []
    if page > 0:
        nav_row.append(
            InlineKeyboardButton(
                text="⬅️ Назад", callback_data=f"inst_pg|{req_id}|{page - 1}"
            )
        )

    if total_pages > 1:
        nav_row.append(
            InlineKeyboardButton(
                text=f"📄 {page + 1}/{total_pages}", callback_data="ignore"
            )
        )

    if page < total_pages - 1:
        nav_row.append(
            InlineKeyboardButton(
                text="Вперед ➡️", callback_data=f"inst_pg|{req_id}|{page + 1}"
            )
        )
    else:
        nav_row.append(
            InlineKeyboardButton(text="Ещё 🔄", callback_data=f"inst_more|{req_id}")
        )

    if nav_row:
        inline_keyboard.append(nav_row)

    return create_user_keyboard(inline_keyboard, user_id)


async def _handle_expired_request(callback: types.CallbackQuery):
    try:
        expired_text = format_styled_message(
            emoji="⏳",
            title=API_NAME,
            message="<b>Время этого запроса истекло.</b>\nПожалуйста, вызовите команду заново.",
        )
        await callback.message.edit_text(text=expired_text, reply_markup=None)
    except Exception:
        pass


async def cmd_myinstants(message: types.Message):
    raw_text = get_raw_text(message)
    args = raw_text.split(maxsplit=1) if raw_text else []
    query = args[1].strip() if len(args) > 1 else None

    status_msg = await message.reply(
        format_styled_message(
            emoji="🔍",
            title=API_NAME,
            message=f"Ищу звуки{' по запросу: ' + query if query else ' в трендах мемов'}...",
        )
    )

    results = await _scrape_myinstants(query)

    if not results:
        await status_msg.edit_text(
            format_styled_message(
                emoji="❌",
                title=API_NAME,
                message="Ничего не найдено или сайт недоступен.",
            )
        )
        return

    user_id = message.from_user.id

    if user_id in user_active_requests:
        old_req_id = user_active_requests[user_id]
        if old_req_id in instants_cache:
            del instants_cache[old_req_id]

    req_id = uuid.uuid4().hex[:8]
    user_active_requests[user_id] = req_id

    instants_cache[req_id] = {
        "query": query or "Тренды",
        "results": results,
        "total_pages": math.ceil(len(results) / 6),
        "site_page": 1,
    }

    keyboard = generate_instants_keyboard(req_id, 0, user_id)
    result_text = (
        f"🔎 <b>Результаты ({len(results)} шт.):</b>\n\nВыберите звук для скачивания:"
    )

    await status_msg.edit_text(
        format_styled_message(emoji=API_ICON, title=API_NAME, message=result_text),
        reply_markup=keyboard,
    )

    await db.increment_commands()
    await db.log_command("!инстант", user_id)
    await spend_tokens(message, "!инстант")


async def process_instants_page_callback(callback: types.CallbackQuery):
    try:
        _, req_id, page_str = callback.data.split("|")
        page = int(page_str)
    except ValueError:
        return

    keyboard = generate_instants_keyboard(req_id, page, callback.from_user.id)
    if not keyboard:
        await _handle_expired_request(callback)
        return

    query = instants_cache[req_id]["query"]
    result_text = f"🔎 <b>Результаты ({query}):</b>\n\nВыберите звук для скачивания:"

    try:
        await callback.message.edit_text(
            format_styled_message(emoji=API_ICON, title=API_NAME, message=result_text),
            reply_markup=keyboard,
        )
    except Exception:
        pass

    await callback.answer()


async def process_instants_more_callback(callback: types.CallbackQuery):
    try:
        _, req_id = callback.data.split("|")
    except ValueError:
        return

    cache_data = instants_cache.get(req_id)
    if not cache_data:
        await _handle_expired_request(callback)
        return

    await callback.answer("⏳ Подгружаю ещё звуки...")

    next_site_page = cache_data.get("site_page", 1) + 1
    query = cache_data["query"]

    search_query = query if query != "Тренды" else None

    new_results = await _scrape_myinstants(search_query, next_site_page)

    if not new_results:
        await callback.answer("❌ Больше результатов нет!", show_alert=True)
        return

    current_bot_page = cache_data["total_pages"] - 1

    cache_data["results"].extend(new_results)
    cache_data["total_pages"] = math.ceil(len(cache_data["results"]) / 6)
    cache_data["site_page"] = next_site_page

    keyboard = generate_instants_keyboard(
        req_id, current_bot_page + 1, callback.from_user.id
    )

    result_text = f"🔎 <b>Результаты ({len(cache_data['results'])} шт.):</b>\n\nВыберите звук для скачивания:"

    try:
        await callback.message.edit_text(
            format_styled_message(emoji=API_ICON, title=API_NAME, message=result_text),
            reply_markup=keyboard,
        )
    except Exception:
        pass


async def process_instants_download_callback(callback: types.CallbackQuery):
    _, req_id, track_idx_str = callback.data.split("|")
    track_idx = int(track_idx_str)

    cache_data = instants_cache.get(req_id)
    if not cache_data or track_idx >= len(cache_data["results"]):
        await _handle_expired_request(callback)
        return

    track_data = cache_data["results"][track_idx]
    audio_url = track_data["url"]
    name = track_data["name"]

    await callback.answer(f"⬇️ Загружаю: {name}...")

    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(audio_url) as resp:
                if resp.status == 200:
                    audio_data = await resp.read()

                    fd, path = tempfile.mkstemp(suffix=".mp3")
                    with os.fdopen(fd, "wb") as f:
                        f.write(audio_data)

                    tg_file = FSInputFile(path)
                    caption = format_styled_message(
                        emoji=API_ICON, title=API_NAME, message=f"<b>{name}</b>"
                    )

                    try:
                        if callback.message.reply_to_message:
                            await callback.message.reply_to_message.reply_voice(
                                voice=tg_file, caption=caption
                            )
                        else:
                            await callback.message.answer_voice(
                                voice=tg_file, caption=caption
                            )
                    finally:
                        os.remove(path)
                else:
                    await callback.answer(
                        "❌ Ошибка при скачивании файла.", show_alert=True
                    )
        except Exception as e:
            logger.error(f"Ошибка загрузки звука myinstants: {e}")
            await callback.answer("❌ Ошибка сети.", show_alert=True)

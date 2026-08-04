import aiohttp
import logging
from urllib.parse import quote
from aiogram import types
from config import KINOPOISK_API_KEY, COMMAND_METADATA
from bot.utils.database import db
from bot.utils.helpers import (
    format_styled_message,
    freeze_tokens,
    refund_tokens,
    get_raw_text,
)

API_ICON = COMMAND_METADATA["!кино"]["icon"]
API_NAME = COMMAND_METADATA["!кино"]["name"]

logger = logging.getLogger(__name__)


async def search_movie(query: str) -> dict | None:
    url = f"https://kinopoiskapiunofficial.tech/api/v2.1/films/search-by-keyword?keyword={quote(query)}&page=1"
    headers = {"X-API-KEY": KINOPOISK_API_KEY, "Content-Type": "application/json"}
    async with aiohttp.ClientSession(headers=headers) as session:
        try:
            async with session.get(url, timeout=15) as response:
                if response.status == 200:
                    data = await response.json()
                    films = data.get("films", [])
                    return films[0] if films else None
                return None
        except Exception as e:
            logger.error(f"Ошибка Кинопоиск API: {e}")
            return None


async def cmd_movie(message: types.Message):
    user_id = message.from_user.id
    if not await freeze_tokens(message, user_id, "!кино"):
        return

    raw_text = get_raw_text(message)
    parts = raw_text.split(maxsplit=1) if raw_text else []
    if len(parts) < 2:
        await refund_tokens(user_id, "!кино")
        await message.reply(
            format_styled_message(
                emoji=API_ICON,
                title=API_NAME,
                message="❌ Напиши название фильма.\n📝 Пример: <code>!кино Бойцовский клуб</code>",
            )
        )
        return

    query = parts[1].strip()
    wait_msg = await message.reply(
        format_styled_message(
            emoji="⏳", title=API_NAME, message="Ищу фильм в базе Кинопоиска..."
        )
    )

    movie = await search_movie(query)
    if not movie:
        await refund_tokens(user_id, "!кино")
        await wait_msg.edit_text(
            format_styled_message(
                emoji="❌", title=API_NAME, message=f"Фильм «{query}» не найден."
            )
        )
        return

    title = movie.get("nameRu") or movie.get("nameEn") or "Без названия"
    year = movie.get("year", "—")
    genres = ", ".join([g.get("genre", "") for g in movie.get("genres", [])])
    countries = ", ".join([c.get("country", "") for c in movie.get("countries", [])])
    rating = movie.get("rating", "—")
    duration = movie.get("filmLength", "—")
    kp_id = movie.get("filmId") or movie.get("kinopoiskId")
    poster = movie.get("posterUrlPreview")

    movie_text = (
        f"🎬 <b>{title}</b> ({year})\n\n"
        f"⭐️ <b>Рейтинг:</b> {rating}\n"
        f"🌍 <b>Страна:</b> {countries}\n"
        f"🎭 <b>Жанр:</b> {genres}\n"
        f"⏱ <b>Время:</b> {duration}\n\n"
        f"🔗 <a href='https://www.kinopoisk.ru/film/{kp_id}/'>Страница на Кинопоиске</a>"
    )

    caption = format_styled_message(emoji=API_ICON, title=API_NAME, message=movie_text)

    try:
        if poster:
            try:
                await message.reply_photo(photo=poster, caption=caption)
                await wait_msg.edit_text(
                    format_styled_message(
                        emoji="✅",
                        title=API_NAME,
                        message="Информация найдена и отправлена ниже! 👇",
                    )
                )
            except Exception:
                await wait_msg.edit_text(caption, disable_web_page_preview=False)
        else:
            await wait_msg.edit_text(caption, disable_web_page_preview=False)

        await db.increment_commands()
        await db.log_command("!кино", user_id)

    except Exception as e:
        await refund_tokens(user_id, "!кино")
        logger.error(f"Ошибка отправки сообщения кино: {e}")

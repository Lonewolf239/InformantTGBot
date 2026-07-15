import logging
import asyncio
import html
from aiogram import types
from config import COMMAND_METADATA
from bot.utils.database import db
from bot.utils.helpers import (
    format_styled_message,
    spend_tokens,
    get_raw_text,
    get_reply_raw_text,
)

try:
    from duckduckgo_search import DDGS
except ImportError:
    DDGS = None

API_ICON = COMMAND_METADATA["!поиск"]["icon"]
API_NAME = COMMAND_METADATA["!поиск"]["name"]

logger = logging.getLogger(__name__)


def _sync_search(query: str, limit: int = 6):
    with DDGS() as ddgs:
        return list(
            ddgs.text(query, region="ru-ru", safesearch="moderate", max_results=limit)
        )


async def search_internet(query: str, limit: int = 6) -> str | None:
    if not DDGS:
        logger.error("Библиотека duckduckgo_search не установлена.")
        return None

    try:
        results = await asyncio.to_thread(_sync_search, query, limit)

        if not results:
            return None

        results_text = ["Результаты по запросу:", f"«<code>{query}</code>»\n"]

        for idx, res in enumerate(results, 1):
            title = html.escape(res.get("title", "Без названия"))
            body = html.escape(res.get("body", "Нет описания"))
            link = res.get("href", "")

            if len(body) > 120:
                body = body[:117] + "..."

            item_text = (
                f"<b>{idx}.</b> <a href='{link}'><b>{title}</b></a>\n<i>{body}</i>\n"
            )
            results_text.append(item_text)

        return "\n".join(results_text).rstrip("\n")

    except Exception as e:
        logger.error(f"Ошибка API DuckDuckGo: {e}")
        return None


async def cmd_search(message: types.Message):
    raw_text = get_raw_text(message)
    parts = raw_text.split(maxsplit=1) if raw_text else []
    query = ""

    if len(parts) > 1:
        query = parts[1].strip()
    else:
        raw_reply_text = get_reply_raw_text(message)
        if raw_reply_text:
            query = raw_reply_text

    if not query:
        error_msg = format_styled_message(
            emoji=API_ICON,
            title=API_NAME,
            message="❌ <b>Не указан запрос.</b>\n📝 Использование: <code>!поиск</code> [запрос] или ответом на сообщение.",
        )
        await message.reply(error_msg)
        return

    wait_msg = await message.reply(
        format_styled_message(
            emoji="⏳",
            title=API_NAME,
            message=f"Ищу информацию по запросу: <b>{query}</b>...",
        )
    )

    search_text = await search_internet(query)

    if not search_text:
        if not DDGS:
            await wait_msg.edit_text(
                format_styled_message(
                    emoji="❌",
                    title="Ошибка",
                    message="Не установлена библиотека <code>duckduckgo-search</code>.",
                )
            )
        else:
            await wait_msg.edit_text(
                format_styled_message(
                    emoji="❌",
                    title=API_NAME,
                    message=f"По запросу «<b>{query}</b>» ничего не найдено.",
                )
            )
        return

    result_msg = format_styled_message(
        emoji=API_ICON, title=API_NAME, message=search_text
    )

    await wait_msg.edit_text(result_msg, disable_web_page_preview=True)

    await db.increment_commands()
    await db.log_command("!поиск", message.from_user.id)
    await spend_tokens(message, "!поиск")

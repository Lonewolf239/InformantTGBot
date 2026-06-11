import aiohttp
import logging
from urllib.parse import quote
from aiogram import types
from config import NEWS_API_KEY, COMMAND_METADATA
from bot.utils.database import db
from bot.utils.helpers import format_styled_message, spend_tokens

API_ICON = COMMAND_METADATA["!новости"]["icon"]
API_NAME = COMMAND_METADATA["!новости"]["name"]

logger = logging.getLogger(__name__)


async def get_news(query: str = "") -> str | None:
    if query:
        url = f"https://newsapi.org/v2/everything?q={quote(query)}&pageSize=5&sortBy=relevancy&language=ru&apiKey={NEWS_API_KEY}"
    else:
        url = f"https://newsapi.org/v2/everything?q=новости&pageSize=5&sortBy=publishedAt&language=ru&apiKey={NEWS_API_KEY}"

    headers = {
        "User-Agent": "InformantBot/1.0 (https://t.me/Lonewolf239_informantBOT) aiohttp/3.8"
    }

    async with aiohttp.ClientSession(headers=headers) as session:
        try:
            async with session.get(url, timeout=15) as response:
                if response.status == 200:
                    data = await response.json()
                    articles = data.get("articles", [])
                    if not articles:
                        return None

                    news_text = ""
                    for art in articles:
                        title = art.get("title", "Без заголовка")
                        link = art.get("url", "")
                        news_text += f"📰 <b>{title}</b>\n🔗 <a href='{link}'>Читать полностью</a>\n\n"

                    return news_text.strip()
                else:
                    logger.error(f"Ошибка NewsAPI: HTTP {response.status}")
                    return None
        except Exception as e:
            logger.error(f"Ошибка получения новостей: {e}")
            return None


async def cmd_news(message: types.Message):
    parts = message.text.split(maxsplit=1) if message.text else []
    query = parts[1].strip() if len(parts) > 1 else ""

    wait_msg = await message.reply(
        format_styled_message(emoji="⏳", title=API_NAME, message="Собираю свежие новости...")
    )

    news_text = await get_news(query)

    if not news_text:
        await wait_msg.edit_text(
            format_styled_message(
                emoji="❌", 
                title=API_NAME, 
                message=f"По запросу «<b>{query}</b>» новости не найдены." if query else "Не удалось получить свежие новости (возможно, API недоступен)."
            )
        )
        return

    result_msg = format_styled_message(
        emoji=API_ICON,
        title=API_NAME,
        message=news_text
    )

    await wait_msg.edit_text(result_msg, disable_web_page_preview=True)

    await db.increment_commands()
    await db.log_command("!новости", message.from_user.id)
    await spend_tokens(message, "!новости")

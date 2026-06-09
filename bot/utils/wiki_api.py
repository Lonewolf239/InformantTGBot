import aiohttp
import logging
from urllib.parse import quote
from aiogram import types
from config import COMMAND_METADATA
from bot.utils.database import db
from bot.utils.helpers import format_styled_message, spend_tokens

API_ICON = COMMAND_METADATA["!вики"]["icon"]
API_NAME = COMMAND_METADATA["!вики"]["name"]

logger = logging.getLogger(__name__)


async def search_wikipedia(query: str) -> str | None:
    search_url = f"https://ru.wikipedia.org/w/api.php?action=opensearch&search={quote(query)}&limit=1&namespace=0&format=json"
    headers = {
        "User-Agent": "InformantBot/1.0 (https://t.me/Lonewolf239_informantBOT) aiohttp/3.8"
    }

    async with aiohttp.ClientSession(headers=headers) as session:
        try:
            async with session.get(search_url) as response:
                if response.status != 200:
                    return None
                data = await response.json()
                if not data[1]:
                    return None
                title = data[1][0]

            summary_url = f"https://ru.wikipedia.org/api/rest_v1/page/summary/{quote(title)}"
            async with session.get(summary_url) as summary_resp:
                if summary_resp.status != 200:
                    return None
                summary_data = await summary_resp.json()

                extract = summary_data.get("extract", "")
                page_url = summary_data.get("content_urls", {}).get("desktop", {}).get("page", "")

                if not extract:
                    return None

                return f"<b>{title}</b>\n\n{extract}\n\n🔗 <a href='{page_url}'>Читать полностью</a>"

        except Exception as e:
            logger.error(f"Ошибка API Википедии (поиск): {e}")
            return None


async def cmd_wiki(message: types.Message):
    parts = message.text.split(maxsplit=1) if message.text else []
    query = ""

    if len(parts) > 1:
        query = parts[1].strip()
    elif message.reply_to_message and message.reply_to_message.text:
        query = message.reply_to_message.text.strip()

    if not query:
        error_msg = format_styled_message(
            emoji=API_ICON,
            title=API_NAME,
            message="❌ <b>Не указан запрос.</b>\n📝 Использование: <code>!вики [запрос]</code> или ответом на сообщение."
        )
        await message.reply(error_msg)
        return

    wait_msg = await message.reply(
        format_styled_message(emoji="⏳", title=API_NAME, message="Ищу информацию...")
    )

    wiki_text = await search_wikipedia(query)

    if not wiki_text:
        await wait_msg.edit_text(
            format_styled_message(emoji="❌", title=API_NAME, message=f"По запросу «<b>{query}</b>» ничего не найдено.")
        )
        return

    result_msg = format_styled_message(
        emoji=API_ICON,
        title=API_NAME,
        message=wiki_text
    )

    await wait_msg.edit_text(result_msg, disable_web_page_preview=True)

    await db.increment_commands()
    await db.log_command("!вики", message.from_user.id)
    await spend_tokens(message, "!вики")

import aiohttp
import logging
from urllib.parse import quote
from aiogram import types
from config import COMMAND_METADATA, TICKETMASTER_API_KEY
from bot.utils.database import db
from bot.utils.helpers import format_styled_message, spend_tokens, get_raw_text

API_ICON = COMMAND_METADATA["!афиша"]["icon"]
API_NAME = COMMAND_METADATA["!афиша"]["name"]

logger = logging.getLogger(__name__)


async def search_global_events(query: str) -> str | None:
    url = f"https://app.ticketmaster.com/discovery/v2/events.json?apikey={TICKETMASTER_API_KEY}&keyword={quote(query)}&size=5&sort=date,asc"

    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(url, timeout=15) as response:
                if response.status == 200:
                    data = await response.json()

                    if "_embedded" not in data or "events" not in data["_embedded"]:
                        return None

                    events = data["_embedded"]["events"]
                    events_text = ""

                    for ev in events:
                        title = ev.get("name", "Без названия")
                        url_link = ev.get("url", "")
                        dates = (
                            ev.get("dates", {})
                            .get("start", {})
                            .get("localDate", "Дата неизвестна")
                        )

                        venues = ev.get("_embedded", {}).get("venues", [])
                        location_str = ""
                        if venues:
                            venue = venues[0]
                            city = venue.get("city", {}).get("name", "")
                            country = venue.get("country", {}).get("name", "")
                            if city and country:
                                location_str = f"📍 {city}, {country}"

                        info_line = f"📅 {dates}"
                        if location_str:
                            info_line += f"  |  {location_str}"

                        events_text += f"🎫 <b>{title}</b>\n{info_line}\n🔗 <a href='{url_link}'>Билеты и инфо</a>\n\n"

                    return events_text.strip()
                else:
                    logger.error(f"Ошибка Ticketmaster API: HTTP {response.status}")
                    return None
        except Exception as e:
            logger.error(f"Ошибка получения афиши: {e}")
            return None


async def cmd_events(message: types.Message):
    raw_text = get_raw_text(message)
    parts = raw_text.split(maxsplit=1) if raw_text else []
    query = parts[1].strip() if len(parts) > 1 else ""

    if not query:
        error_msg = format_styled_message(
            emoji=API_ICON,
            title=API_NAME,
            message="❌ <b>Укажи город или артиста.</b>\n📝 Пример: <code>!афиша London</code> или <code>!афиша Rammstein</code>",
        )
        await message.reply(error_msg)
        return

    wait_msg = await message.reply(
        format_styled_message(
            emoji="⏳", title=API_NAME, message="Ищу события по всему миру..."
        )
    )

    events_text = await search_global_events(query)

    if not events_text:
        await wait_msg.edit_text(
            format_styled_message(
                emoji="❌",
                title=API_NAME,
                message=f"По запросу «<b>{query}</b>» ничего не найдено.\n💡 <i>Попробуй написать название города или группы на английском.</i>",
            )
        )
        return

    result_msg = format_styled_message(
        emoji=API_ICON, title=API_NAME, message=events_text
    )

    await wait_msg.edit_text(result_msg, disable_web_page_preview=True)

    await db.increment_commands()
    await db.log_command("!афиша", message.from_user.id)
    await spend_tokens(message, "!афиша")

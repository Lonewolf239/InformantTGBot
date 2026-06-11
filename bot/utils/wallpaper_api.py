import aiohttp
import logging
from urllib.parse import quote
from aiogram import types
from config import UNSPLASH_API_KEY, COMMAND_METADATA
from bot.utils.database import db
from bot.utils.helpers import format_styled_message, spend_tokens

API_ICON = COMMAND_METADATA["!обои"]["icon"]
API_NAME = COMMAND_METADATA["!обои"]["name"]

logger = logging.getLogger(__name__)


async def get_wallpaper(query: str) -> dict | None:
    if not query:
        url = f"https://api.unsplash.com/photos/random?orientation=landscape&client_id={UNSPLASH_API_KEY}"
    else:
        url = f"https://api.unsplash.com/photos/random?query={quote(query)}&orientation=landscape&client_id={UNSPLASH_API_KEY}"

    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(url, timeout=15) as response:
                if response.status == 200:
                    photo = await response.json()

                    if isinstance(photo, list) and len(photo) > 0:
                        photo = photo[0]

                    if not photo or "urls" not in photo:
                        return None

                    return {
                        "url": photo["urls"]["regular"],
                        "full_url": photo["urls"]["full"],
                        "author": photo["user"].get("name", "Неизвестен"),
                        "link": photo["links"]["html"]
                    }
                else:
                    logger.error(f"Ошибка Unsplash API: HTTP {response.status}")
                    return None
        except Exception as e:
            logger.error(f"Ошибка получения обоев: {e}")
            return None


async def cmd_wallpaper(message: types.Message):
    parts = message.text.split(maxsplit=1) if message.text else []
    query = parts[1].strip() if len(parts) > 1 else ""

    wait_text = "Ищу крутые обои по твоему запросу..." if query else "Подбираю случайные крутые обои..."
    wait_msg = await message.reply(
        format_styled_message(emoji="⏳", title=API_NAME, message=wait_text)
    )

    wallpaper_data = await get_wallpaper(query)

    if not wallpaper_data:
        await wait_msg.edit_text(
            format_styled_message(emoji="❌", title=API_NAME, message=f"Обои по запросу «<b>{query}</b>» не найдены." if query else "Не удалось получить случайные обои.")
        )
        return

    caption = format_styled_message(
        emoji=API_ICON,
        title=API_NAME,
        message=f"🎨 <b>Автор:</b> {wallpaper_data['author']}\n🔗 <a href='{wallpaper_data['full_url']}'>Скачать оригинал</a>"
    )

    try:
        await message.reply_photo(photo=wallpaper_data["url"], caption=caption)

        await wait_msg.edit_text(
            format_styled_message(emoji="✅", title=API_NAME, message="Обои успешно подобраны и отправлены ниже!")
        )

        await db.increment_commands()
        await db.log_command("!обои", message.from_user.id)
        await spend_tokens(message, "!обои")

    except Exception as e:
        logger.error(f"Ошибка отправки фото (!обои): {e}")
        await wait_msg.edit_text(
            format_styled_message(emoji="❌", title=API_NAME, message="Не удалось загрузить картинку в Telegram. Возможно, файл слишком большой.")
        )

import re
import socket
import aiohttp
import logging
from aiogram import types
from aiogram.types import BufferedInputFile, InputMediaPhoto
from config import COMMAND_COSTS, VIP_IDS, PAYMENTS_ENABLED, COMMAND_METADATA
from bot.utils.database import db
from bot.utils.helpers import format_styled_message, spend_tokens

API_ICON = COMMAND_METADATA["!картинка"]["icon"]
API_NAME = COMMAND_METADATA["!картинка"]["name"]

logger = logging.getLogger(__name__)

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/125.0.0.0 Safari/537.36"
)


async def fetch_from_bing(query: str) -> list[str]:
    url = "https://www.bing.com/images/search"
    params = {"q": query, "form": "HDRSC2", "first": "1"}
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
    }
    try:
        connector = aiohttp.TCPConnector(family=socket.AF_INET)
        async with aiohttp.ClientSession(connector=connector, headers=headers) as session:
            async with session.get(url, params=params, timeout=3.5) as response:
                if response.status != 200:
                    logger.warning(f"Bing вернул статус {response.status}")
                    return []
                html = await response.text()

                urls = re.findall(r'murl&quot;:&quot;(https?://[^&"\s]+)', html)
                if not urls:
                    urls = re.findall(r'"murl"\s*:\s*"(https?://[^"]+)"', html)

                if urls:
                    logger.info(f"Успешно получено {len(urls)} картинок через Bing")
                    return urls
    except Exception as e:
        logger.error(f"Ошибка парсинга через Bing ({type(e).__name__}): {e}")
    return []


async def fetch_from_yahoo(query: str) -> list[str]:
    url = "https://images.search.yahoo.com/search/images"
    params = {"p": query}
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    }
    try:
        connector = aiohttp.TCPConnector(family=socket.AF_INET)
        async with aiohttp.ClientSession(connector=connector, headers=headers) as session:
            async with session.get(url, params=params, timeout=3.5) as response:
                if response.status != 200:
                    logger.warning(f"Yahoo вернул статус {response.status}")
                    return []
                html = await response.text()

                urls = re.findall(r'&quot;iurl&quot;:&quot;(https?://[^&"\s]+)', html)
                if not urls:
                    urls = re.findall(r'"iurl"\s*:\s*"(https?://[^"]+)"', html)

                if urls:
                    logger.info(f"Успешно получено {len(urls)} картинок через Yahoo")
                    return urls
    except Exception as e:
        logger.error(f"Ошибка парсинга через Yahoo ({type(e).__name__}): {e}")
    return []


async def fetch_image_urls(query: str) -> list[str]:
    urls = await fetch_from_bing(query)
    if urls:
        return urls

    logger.warning("Bing не дал результатов, переключаюсь на Yahoo Images...")
    return await fetch_from_yahoo(query)


async def cmd_search_image(message: types.Message):
    parts = message.text.split(maxsplit=1) if message.text else []
    query = ""

    if len(parts) > 1:
        query = parts[1].strip()
    elif message.reply_to_message:
        query = (message.reply_to_message.text or message.reply_to_message.caption or "").strip()

    if not query:
        await message.reply(format_styled_message(
            emoji=API_ICON,
            title=API_NAME,
            message="❌ <b>Не указан запрос для поиска.</b>\n📝 Пример: <code>!картинка чешское пиво</code>"
        ))
        return

    wait_msg = await message.reply(format_styled_message(
        emoji="⏳", title=API_NAME, message=f"Ищу изображения по запросу: «<code>{query}</code>»..."
    ))

    urls = await fetch_image_urls(query)

    if not urls:
        await wait_msg.edit_text(format_styled_message(
            emoji="❌", title=API_NAME, message="Ничего не найдено по вашему запросу. Попробуйте изменить формулировку."
        ))
        return

    downloaded_images = []
    download_headers = {
        "User-Agent": USER_AGENT,
        "Accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8"
    }

    connector = aiohttp.TCPConnector(family=socket.AF_INET)
    async with aiohttp.ClientSession(connector=connector, headers=download_headers) as session:
        for url in urls[:25]:
            if len(downloaded_images) >= 6:
                break
            try:
                async with session.get(url, timeout=3) as resp:
                    if resp.status == 200 and resp.headers.get("Content-Type", "").startswith("image"):
                        img_bytes = await resp.read()
                        if len(img_bytes) > 2048:
                            downloaded_images.append(img_bytes)
            except Exception:
                continue

    if not downloaded_images:
        await wait_msg.edit_text(format_styled_message(
            emoji="❌", title=API_NAME, message="Не удалось загрузить найденные изображения. Попробуйте другой запрос."
        ))
        return

    try:
        caption = format_styled_message(
            emoji=API_ICON,
            title=API_NAME,
            message=f"Результаты по запросу:\n«<code>{query}</code>»"
        )

        if len(downloaded_images) == 1:
            photo_file = BufferedInputFile(downloaded_images[0], filename="search_result.jpg")
            await message.reply_photo(photo=photo_file, caption=caption)
        else:
            media_group = []
            for i, img_bytes in enumerate(downloaded_images):
                photo_file = BufferedInputFile(img_bytes, filename=f"search_result_{i}.jpg")
                if i == 0:
                    media_group.append(InputMediaPhoto(media=photo_file, caption=caption))
                else:
                    media_group.append(InputMediaPhoto(media=photo_file))

            await message.reply_media_group(media=media_group)

        await wait_msg.edit_text(format_styled_message(
            emoji="✨", title=API_NAME, message=f"Успешно загружено и отправлено {len(downloaded_images)} шт. ниже! 👇"
        ))

        await db.increment_commands()
        await db.log_command("!картинка", message.from_user.id)
        await spend_tokens(message, "!картинка")

    except Exception as e:
        logger.error(f"Ошибка отправки медиа-альбома или редактирования статуса ({type(e).__name__}): {e}")
        await wait_msg.edit_text(format_styled_message(
            emoji="❌", title=API_NAME, message="Ошибка отрисовки изображений. Попробуйте еще раз."
        ))

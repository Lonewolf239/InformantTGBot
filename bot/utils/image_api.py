import aiohttp
import logging
import random
from urllib.parse import quote
from aiogram import types
from aiogram.types import BufferedInputFile
from config import COMMAND_COSTS, VIP_IDS, PAYMENTS_ENABLED, POLLINATIONS_API_KEY, COMMAND_METADATA
from bot.utils.database import db
from bot.utils.helpers import format_styled_message, spend_tokens
from bot.utils.tokens_database import tokens_db

API_ICON = COMMAND_METADATA["!рис"]["icon"]
API_NAME = COMMAND_METADATA["!рис"]["name"]

logger = logging.getLogger(__name__)


async def generate_flux_image(prompt: str) -> bytes | None:
    seed = random.randint(1, 999999)
    url = f"https://image.pollinations.ai/p/{quote(prompt)}?model=flux&width=1024&height=1024&seed={seed}&enhance=true"

    headers = {}
    if POLLINATIONS_API_KEY:
        headers["Authorization"] = f"Bearer {POLLINATIONS_API_KEY}"

    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(url, headers=headers, timeout=50) as response:
                if response.status == 200:
                    return await response.read()
                logger.error(f"Ошибка Pollinations API: Статус {response.status}")
                return None
        except Exception as e:
            logger.error(f"Исключение при генерации картинки: {e}")
            return None


async def cmd_render(message: types.Message):
    parts = message.text.split(maxsplit=1) if message.text else []
    prompt = ""

    if len(parts) > 1:
        prompt = parts[1].strip()
    elif message.reply_to_message:
        prompt = (message.reply_to_message.text or message.reply_to_message.caption or "").strip()

    if not prompt:
        await message.reply(format_styled_message(
            emoji=API_ICON,
            title=API_NAME,
            message="❌ <b>Не указан промпт для генерации.</b>\n📝 Пример: <code>!рис неоновый самурай, киберпанк, 8k</code> или ответом на текст."
        ))
        return

    wait_msg = await message.reply(format_styled_message(
        emoji="⏳", title=API_NAME, message="Рисую шедевр (модель <b>FLUX</b>)... Это займет около 10-20 секунд."
    ))

    image_bytes = await generate_flux_image(prompt)

    if not image_bytes:
        await wait_msg.edit_text(format_styled_message(
            emoji="❌", title=API_NAME, message="Не удалось сгенерировать картинку. Сервер временно перегружен."
        ))
        return

    try:
        photo_file = BufferedInputFile(image_bytes, filename="flux_art.jpg")
        caption = format_styled_message(
            emoji=API_ICON,
            title=API_NAME,
            message=f"Результат по запросу:\n«<code>{prompt}</code>»"
        )

        await message.reply_photo(photo=photo_file, caption=caption)

        await wait_msg.edit_text(format_styled_message(
            emoji="✨", title=API_NAME, message="Шедевр успешно готов и отправлен ниже! 👇"
        ))

        await db.increment_commands()
        await db.log_command("!рис", message.from_user.id)
        await spend_tokens(message, "!рис")

    except Exception as e:
        logger.error(f"Ошибка при отправке готового фото: {e}")
        await wait_msg.edit_text(format_styled_message(
            emoji="❌", title=API_NAME, message="Ошибка отправки готового файла. Попробуйте еще раз."
        ))

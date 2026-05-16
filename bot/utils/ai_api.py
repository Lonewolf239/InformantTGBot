import logging
from typing import Optional
import aiohttp
from aiogram import types
from config import OLLAMA_BASE_URL, OLLAMA_MODEL, AI_SYSTEM_PROMPT
from bot.utils.database import db
from bot.utils.ai_queue import get_queue, TaskType, ensure_queue_started

logger = logging.getLogger(__name__)

MAX_REPLY_LEN = 3800
REQUEST_TIMEOUT = aiohttp.ClientTimeout(total=90)

DISCLAIMER = "\n\n*⚠️ ИИ может ошибаться. Проверяй важную информацию.*"


def split_text(text: str, limit: int = MAX_REPLY_LEN) -> list[str]:
    text = (text or "").strip()
    if not text:
        return [""]

    if len(text) <= limit:
        return [text]

    chunks = []
    while text:
        if len(text) <= limit:
            chunks.append(text)
            break

        cut = text.rfind("\n", 0, limit)
        if cut < int(limit * 0.6):
            cut = text.rfind(" ", 0, limit)

        if cut <= 0:
            cut = limit

        chunks.append(text[:cut].strip())
        text = text[cut:].strip()

    return [chunk for chunk in chunks if chunk.strip()]


async def ask_local_ai(user_prompt: str, system_prompt: Optional[str] = None) -> Optional[str]:
    system_prompt = system_prompt or AI_SYSTEM_PROMPT
    url = f"{OLLAMA_BASE_URL.rstrip('/')}/api/chat"

    payload = {
        "model": OLLAMA_MODEL,
        "stream": False,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        # Optimized for qwen2.5:3b (CPU-friendly, short Telegram replies)
        "options": {
            "temperature": 0.4,
            "top_p": 0.75,
            "repeat_penalty": 1.1,
            "num_ctx": 1024,
            "num_predict": 256
        }
    }

    async with aiohttp.ClientSession(timeout=REQUEST_TIMEOUT) as session:
        try:
            async with session.post(url, json=payload) as response:
                if response.status != 200:
                    body = await response.text()
                    logger.error(f"Ошибка Ollama API: {response.status} - {body}")
                    return None

                data = await response.json()

                if data.get("message", {}).get("content"):
                    return data["message"]["content"].strip()

                if data.get("response"):
                    return str(data["response"]).strip()

                logger.error(f"Пустой ответ Ollama: {data}")
                return None

        except aiohttp.ClientTimeout:
            logger.error("Таймаут запроса к Ollama")
            return None
        except Exception as e:
            logger.error(f"Ошибка при запросе к Ollama: {e}")
            return None


async def cmd_ai(message: types.Message):
    ensure_queue_started()

    parts = message.text.split(maxsplit=1) if message.text else []

    if len(parts) < 2:
        await message.reply(
            "<b>┌─ 🧠 ИИ</b>\n"
            "├─ ❌ Не указан запрос.\n"
            "└─ 📝 Использование: <code>!ии</code> [текст]"
        )
        return True

    user_prompt = parts[1].strip()

    if message.reply_to_message and message.reply_to_message.text:
        user_prompt = (
            "Ответь на сообщение ниже и учти запрос пользователя.\n\n"
            f"Сообщение:\n{message.reply_to_message.text}\n\n"
            f"Запрос:\n{user_prompt}"
        )

    queue = get_queue()
    queue_position = queue.queue.qsize() + 1

    wait_msg = await message.reply(
        "<b>┌─ 🧠 ИИ</b>\n"
        f"├─ ⏳ Запрос поставлен в очередь.\n"
        f"└─ 📍 Позиция: {queue_position}"
    )

    if queue_position > 2:
        await message.reply(
            "<b>┌─ ⏳ ОЖИДАНИЕ</b>\n"
            "└─ Высокая нагрузка, ответ может занять больше времени."
        )

    try:
        answer, _ = await queue.add_task(
            task_type=TaskType.AI,
            data={"prompt": user_prompt, "system_prompt": AI_SYSTEM_PROMPT},
            user_id=message.from_user.id
        )
    except Exception as e:
        logger.exception("Ошибка при выполнении AI задачи")
        answer = None

    if not answer:
        try:
            await wait_msg.edit_text(
                "<b>┌─ 🧠 ИИ</b>\n"
                "├─ ❌ Локальная нейросеть не ответила.\n"
                f"└─ Проверь, что Ollama запущена и модель <code>{OLLAMA_MODEL}</code> скачана."
            )
        except Exception:
            await message.reply(
                "<b>┌─ 🧠 ИИ</b>\n"
                "├─ ❌ Локальная нейросеть не ответила.\n"
                f"└─ Проверь, что Ollama запущена и модель <code>{OLLAMA_MODEL}</code> скачана."
            )
        return True

    chunks = split_text(answer)
    first_chunk = f"**┌─ 🧠 ИИ**\n└─ {chunks[0]}{DISCLAIMER}"

    try:
        await wait_msg.edit_text(first_chunk, parse_mode="Markdown")
    except Exception:
        await message.reply(first_chunk, parse_mode="Markdown")

    for chunk in chunks[1:]:
        await message.answer(chunk, parse_mode="Markdown")

    db.increment_commands()
    db.log_command("!ии", message.from_user.id)

    return True

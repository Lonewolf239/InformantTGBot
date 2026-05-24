import logging
from typing import Optional
import aiohttp
from aiogram import types
from config import (
    OLLAMA_BASE_URL, OLLAMA_MODEL, AI_SYSTEM_PROMPT, 
    AI_MAX_REPLY_LEN, AI_REQUEST_TIMEOUT, AI_DISCLAIMER,
    AI_TEMPERATURE, AI_TOP_P, AI_REPEAT_PENALTY, AI_NUM_CTX, AI_NUM_PREDICT
)
from bot.utils.database import db
from bot.utils.ai_queue import get_queue, TaskType, ensure_queue_started
from bot.utils.helpers import format_styled_message

API_ICON = "🧠"
API_NAME = "ИИ"

logger = logging.getLogger(__name__)


def split_text(text: str, limit: int = AI_MAX_REPLY_LEN) -> list[str]:
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
        "options": {
            "temperature": AI_TEMPERATURE,
            "top_p": AI_TOP_P,
            "repeat_penalty": AI_REPEAT_PENALTY,
            "num_ctx": AI_NUM_CTX,
            "num_predict": AI_NUM_PREDICT
        }
    }

    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=AI_REQUEST_TIMEOUT)) as session:
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
                return None
        except Exception as e:
            logger.error(f"Ошибка при запросе к Ollama: {e}")
            return None


async def cmd_ai(message: types.Message):
    ensure_queue_started()
    parts = message.text.split(maxsplit=1) if message.text else []

    if len(parts) < 2:
        error_no_prompt = format_styled_message(
            emoji=API_ICON,
            title=API_NAME,
            message="❌ Не указан запрос.\n📝 Использование: <code>!ии [текст]</code>"
        )
        await message.reply(error_no_prompt)
        return True

    user_prompt = parts[1].strip()
    if message.reply_to_message and message.reply_to_message.text:
        user_prompt = (
            "Ответь на сообщение ниже и учти запрос пользователя.\n\n"
            f"Сообщение:\n{message.reply_to_message.text}\n\n"
            f"Запрос:\n{user_prompt}"
        )

    wait_msg_text = format_styled_message(
        emoji=API_ICON,
        title=API_NAME,
        message="⏳ Анализ запроса...\n📍 Позиция: вычисляется"
    )
    wait_msg = await message.reply(wait_msg_text)

    async def update_position(pos: int):
        try:
            if pos == 0:
                msg_text = format_styled_message(
                    emoji=API_ICON,
                    title=API_NAME,
                    message="🔄 Генерирую ответ...\n⏳ Пожалуйста, подождите"
                )
            else:
                msg_text = format_styled_message(
                    emoji=API_ICON,
                    title=API_NAME,
                    message=f"⏳ Запрос в очереди.\n📍 Позиция перед вами: {pos}"
                )
            await wait_msg.edit_text(msg_text)
        except Exception:
            pass

    queue = get_queue()

    try:
        task_future, queue_position = await queue.add_task(
            task_type=TaskType.AI,
            data={"prompt": user_prompt, "system_prompt": AI_SYSTEM_PROMPT},
            user_id=message.from_user.id,
            update_cb=update_position
        )
        await update_position(queue_position)
    except Exception as e:
        logger.exception("Ошибка при добавлении AI задачи в очередь")
        error_queue = format_styled_message(
            emoji=API_ICON,
            title=API_NAME,
            message="❌ Не удалось поставить задачу в очередь."
        )
        await wait_msg.edit_text(error_queue)
        return True

    try:
        answer = await task_future
    except Exception as e:
        logger.exception("Ошибка при выполнении AI задачи воркером")
        answer = None

    if not answer:
        error_api = format_styled_message(
            emoji=API_ICON,
            title=API_NAME,
            message=f"❌ Локальная нейросеть не ответила.\nПроверь, что Ollama запущена и модель <code>{OLLAMA_MODEL}</code> скачана."
        )
        try:
            await wait_msg.edit_text(error_api)
        except Exception:
            await message.reply(error_api)
        return True

    chunks = split_text(answer)

    first_chunk = format_styled_message(
        emoji=API_ICON,
        title=API_NAME,
        message=f"{chunks[0]}{AI_DISCLAIMER}",
        html=False
    )

    try:
        await wait_msg.edit_text(first_chunk, parse_mode="Markdown")
    except Exception:
        await message.reply(first_chunk, parse_mode="Markdown")

    for chunk in chunks[1:]:
        await message.answer(chunk, parse_mode="Markdown")

    db.increment_commands()
    db.log_command("!ии", message.from_user.id)
    return True


async def cmd_ai_ham(message: types.Message):
    ensure_queue_started()
    parts = message.text.split(maxsplit=1) if message.text else []

    if len(parts) < 2:
        error_no_prompt = format_styled_message(
            emoji="💢",
            title="Нейрохам",
            message="❌ Не указан запрос.\n📝 Использование: <code>!нейрохам [текст]</code>"
        )
        await message.reply(error_no_prompt)
        return True

    user_prompt = parts[1].strip()
    if message.reply_to_message and message.reply_to_message.text:
        user_prompt = (
            "Ответь хамски на сообщение ниже и учти запрос пользователя.\n\n"
            f"Сообщение:\n{message.reply_to_message.text}\n\n"
            f"Запрос:\n{user_prompt}"
        )

    wait_msg_text = format_styled_message(
        emoji="💢",
        title="Нейрохам",
        message="⏳ Анализ запроса...\n📍 Позиция: вычисляется"
    )
    wait_msg = await message.reply(wait_msg_text)

    async def update_position(pos: int):
        try:
            if pos == 0:
                msg_text = format_styled_message(
                    emoji="💢",
                    title="Нейрохам",
                    message="🔄 Генерирую ответ...\n⏳ Пожалуйста, подождите"
                )
            else:
                msg_text = format_styled_message(
                    emoji="💢",
                    title="Нейрохам",
                    message=f"⏳ Запрос в очереди.\n📍 Позиция перед вами: {pos}"
                )
            await wait_msg.edit_text(msg_text)
        except Exception:
            pass

    queue = get_queue()
    from config import AI_HAM_SYSTEM_PROMPT

    try:
        task_future, queue_position = await queue.add_task(
            task_type=TaskType.AI,
            data={"prompt": user_prompt, "system_prompt": AI_HAM_SYSTEM_PROMPT},
            user_id=message.from_user.id,
            update_cb=update_position
        )
        await update_position(queue_position)
    except Exception as e:
        logger.exception("Ошибка при добавлении AI задачи в очередь")
        error_queue = format_styled_message(
            emoji="💢",
            title="Нейрохам",
            message="❌ Не удалось поставить задачу в очередь."
        )
        await wait_msg.edit_text(error_queue)
        return True

    try:
        answer = await task_future
    except Exception as e:
        logger.exception("Ошибка при выполнении AI задачи воркером")
        answer = None

    if not answer:
        error_api = format_styled_message(
            emoji="💢",
            title="Нейрохам",
            message=f"❌ Хамло не отвечает. Проверь, что Ollama запущена и модель <code>{OLLAMA_MODEL}</code> скачана."
        )
        try:
            await wait_msg.edit_text(error_api)
        except Exception:
            await message.reply(error_api)
        return True

    chunks = split_text(answer)

    first_chunk = format_styled_message(
        emoji="💢",
        title="Нейрохам",
        message=f"{chunks[0]}\n\n*⚠️ Режим экспериментальный, нейросеть может нести чушь.*",
        html=False
    )

    try:
        await wait_msg.edit_text(first_chunk, parse_mode="Markdown")
    except Exception:
        await message.reply(first_chunk, parse_mode="Markdown")

    for chunk in chunks[1:]:
        await message.answer(chunk, parse_mode="Markdown")

    db.increment_commands()
    db.log_command("!нейрохам", message.from_user.id)
    return True

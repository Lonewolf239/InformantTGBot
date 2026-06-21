import logging
from typing import Optional
import aiohttp
from aiogram import types
from config import (
    OLLAMA_BASE_URL, OLLAMA_MODEL, AI_MAX_REPLY_LEN, 
    AI_REQUEST_TIMEOUT, AI_PERSONAS, COMMAND_METADATA
)
from bot.utils.database import db
from bot.utils.helpers import format_styled_message, spend_tokens, get_raw_text, get_reply_raw_text
from bot.utils.queue_wrapper import process_with_queue

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


async def ask_local_ai(user_prompt: str, system_prompt: str, **kwargs) -> Optional[str]:
    url = f"{OLLAMA_BASE_URL.rstrip('/')}/api/chat"

    payload = {
        "model": OLLAMA_MODEL,
        "stream": False,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "options": {
            "temperature": kwargs.get("temperature", 0.4),
            "top_p": kwargs.get("top_p", 0.75),
            "repeat_penalty": kwargs.get("repeat_penalty", 1.1),
            "num_ctx": kwargs.get("num_ctx", 1024),
            "num_predict": kwargs.get("num_predict", 256)
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


async def process_ai_request(message: types.Message, cmd_key: str):
    persona = AI_PERSONAS.get(cmd_key)
    meta = COMMAND_METADATA.get(cmd_key, {"icon": "🤖", "name": "ИИ"})

    if not persona:
        await message.reply(f"❌ Настройки для {cmd_key} не найдены.")
        return

    icon = meta["icon"]
    name = meta["name"]


    raw_text = get_raw_text(message)
    parts = raw_text.split(maxsplit=1) if raw_text else []
    reply_text = get_reply_raw_text(message)

    raw_prompt = None
    if len(parts) >= 2:
        raw_prompt = parts[1].strip()
    elif reply_text:
        raw_prompt = reply_text

    if not raw_prompt:
        error_no_prompt = format_styled_message(
            emoji=icon,
            title=name,
            message=f"❌ Не указан текст для обработки.\n📝 Напиши текст или ответь на сообщение командой <code>{cmd_key}</code>"
        )
        await message.reply(error_no_prompt)
        return

    if reply_text:
        raw_prompt = f"Контекст: {reply_text}\n\nВопрос/запрос: {raw_prompt}"

    user_prompt = persona["prompt_template"].format(prompt=raw_prompt)

    answer, wait_msg = await process_with_queue(
        message=message,
        queue_name="heavyweights",
        icon=icon,
        title=name,
        action_text="Анализ запроса",
        func=ask_local_ai,
        user_prompt=user_prompt,
        system_prompt=persona["system_prompt"],
        temperature=persona["temperature"],
        top_p=persona["top_p"],
        repeat_penalty=persona["repeat_penalty"],
        num_ctx=persona["num_ctx"],
        num_predict=persona["num_predict"]
    )

    if not answer:
        error_api = format_styled_message(
            emoji=icon,
            title=name,
            message=f"❌ Нейросеть не ответила. Проверь, что Ollama запущена и модель <code>{OLLAMA_MODEL}</code> скачана."
        )
        if wait_msg:
            try:
                await wait_msg.edit_text(error_api)
            except Exception:
                await message.reply(error_api)
        return

    if persona.get("strip_quotes"):
        answer = answer.strip().strip('"').strip("'").strip("«").strip("»")

    chunks = split_text(answer)

    first_chunk = format_styled_message(
        emoji=icon,
        title=name,
        message=f"{chunks[0]}{persona['disclaimer']}",
        html=False
    )

    try:
        await wait_msg.edit_text(first_chunk, parse_mode="Markdown")
    except Exception:
        await message.reply(first_chunk, parse_mode="Markdown")

    for chunk in chunks[1:]:
        await message.answer(chunk, parse_mode="Markdown")

    await db.increment_commands()
    await db.log_command(cmd_key, message.from_user.id)
    await spend_tokens(message, cmd_key)


def make_ai_handler(cmd_key: str):
    async def handler(message: types.Message):
        await process_ai_request(message, cmd_key)
    return handler


cmd_ai = make_ai_handler("!ии")
cmd_ai_ham = make_ai_handler("!нейрохам")
cmd_ai_psycho = make_ai_handler("!психолог")
cmd_ai_summary = make_ai_handler("!пересказ")

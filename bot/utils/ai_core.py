import html
import re
import random
import logging
from typing import Optional
import aiohttp
from groq import AsyncGroq

from config import (
    AI_MAX_REPLY_LEN,
    AI_PROVIDER,
    AI_REQUEST_TIMEOUT,
    GROQ_MODEL,
    GROQ_VISION_MODEL,
    OLLAMA_BASE_URL,
    OLLAMA_MODEL,
    OLLAMA_VISION_MODEL,
)
from bot.utils.api_key_manager import key_manager

logger = logging.getLogger(__name__)

MAX_SINGLE_MSG_CHARS = 2500
MAX_HISTORY_TOTAL_CHARS = 16000
GROQ_MAX_OUTPUT_TOKENS = 1000


def _reasoning_effort_for(model: str) -> Optional[str]:
    if model.startswith("qwen/"):
        return "none"
    if model.startswith("openai/gpt-oss"):
        return "low"
    return None


user_chat_histories: dict[int, list] = {}

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:123.0) Gecko/20100101 Firefox/123.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36 Edg/122.0.0.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36 OPR/107.0.0.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.3.1 Safari/605.1.15",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:123.0) Gecko/20100101 Firefox/123.0",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:123.0) Gecko/20100101 Firefox/123.0",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36 Vivaldi/6.5.3206.63",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_3_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.3 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (iPad; CPU OS 17_3_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.3 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (Linux; Android 14; Pixel 8 Pro) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Mobile Safari/537.36",
    "Mozilla/5.0 (Linux; Android 14; SM-S928B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Mobile Safari/537.36",
    "Mozilla/5.0 (Linux; Android 13; Redmi Note 12) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Mobile Safari/537.36",
]


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


def format_md_to_html(text: str) -> str:
    safe_text = html.escape(text)
    safe_text = re.sub(r"\*\*(.*?)\*\*", r"<b>\1</b>", safe_text)
    safe_text = re.sub(r"__(.*?)__", r"<u>\1</u>", safe_text)
    safe_text = re.sub(r"(?<!\*)\*(?!\*)(.*?)(?<!\*)\*(?!\*)", r"<i>\1</i>", safe_text)
    safe_text = re.sub(r"```(.*?)```", r"<pre>\1</pre>", safe_text, flags=re.DOTALL)
    safe_text = re.sub(r"`(.*?)`", r"<code>\1</code>", safe_text)
    return safe_text


def truncate_history_to_budget(
    history: list[dict], max_chars: int = MAX_HISTORY_TOTAL_CHARS
) -> list[dict]:
    def _entry_len(entry: dict) -> int:
        content = entry.get("content", "")
        return len(content) if isinstance(content, str) else 0

    total_chars = sum(_entry_len(entry) for entry in history)
    while history and total_chars > max_chars:
        removed = history.pop(0)
        total_chars -= _entry_len(removed)
    return history


async def ask_local_ai(
    user_prompt: str,
    system_prompt: str,
    images: list[str] = None,
    history: list[dict] = None,
    **kwargs,
) -> Optional[str]:
    url = f"{OLLAMA_BASE_URL.rstrip('/')}/api/chat"
    user_message = {"role": "user", "content": user_prompt}

    if images:
        user_message["images"] = images
        model_to_use = OLLAMA_VISION_MODEL
    else:
        model_to_use = OLLAMA_MODEL

    max_tokens = kwargs.get("max_tokens", 1024)
    repeat_penalty = 1.15 if kwargs.get("frequency_penalty", 0.0) > 0 else 1.0

    messages = [{"role": "system", "content": system_prompt}]
    if history:
        messages.extend(history)
    messages.append(user_message)

    payload = {
        "model": model_to_use,
        "stream": False,
        "messages": messages,
        "options": {
            "temperature": kwargs.get("temperature", 0.4),
            "top_p": kwargs.get("top_p", 0.75),
            "repeat_penalty": repeat_penalty,
            "num_predict": max_tokens,
        },
    }

    async with aiohttp.ClientSession(
        timeout=aiohttp.ClientTimeout(total=AI_REQUEST_TIMEOUT)
    ) as session:
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


async def ask_groq_ai(
    user_prompt: str,
    system_prompt: str,
    images: list[str] = None,
    history: list[dict] = None,
    **kwargs,
) -> Optional[str]:
    available_keys = key_manager.get_available_keys()

    if not available_keys:
        logger.error("Все ключи Groq отвалились, в бане или исчерпали лимит токенов!")
        return None

    last_error = None

    if images:
        model_to_use = GROQ_VISION_MODEL
        user_content = [{"type": "text", "text": user_prompt}]
        for img in images:
            user_content.append(
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:image/jpeg;base64,{img}"},
                }
            )
        user_message = {"role": "user", "content": user_content}
    else:
        model_to_use = GROQ_MODEL
        user_message = {"role": "user", "content": user_prompt}

    messages = [{"role": "system", "content": system_prompt}]
    if history:
        messages.extend(history)
    messages.append(user_message)

    for api_key in available_keys:
        user_agent = random.choice(USER_AGENTS)
        client = AsyncGroq(
            api_key=api_key, default_headers={"User-Agent": user_agent}, max_retries=0
        )

        try:
            reasoning_effort = _reasoning_effort_for(model_to_use)
            extra_params = (
                {"reasoning_effort": reasoning_effort} if reasoning_effort else {}
            )
            response = await client.chat.completions.create(
                model=model_to_use,
                messages=messages,
                temperature=kwargs.get("temperature", 0.4),
                top_p=kwargs.get("top_p", 0.75),
                max_tokens=min(kwargs.get("max_tokens", 1024), GROQ_MAX_OUTPUT_TOKENS),
                presence_penalty=kwargs.get("presence_penalty", 0.0),
                frequency_penalty=kwargs.get("frequency_penalty", 0.0),
                timeout=AI_REQUEST_TIMEOUT,
                **extra_params,
            )

            if response.usage:
                total_used = response.usage.total_tokens
                key_manager.add_usage(api_key, total_used)

            return response.choices[0].message.content.strip()

        except Exception as e:
            err_msg = str(e).lower()
            if "too large" in err_msg or "reduce your message" in err_msg:
                logger.error(
                    f"Запрос слишком большой для модели {model_to_use}, ключ не виноват: {e}"
                )
                last_error = e
                break
            if "429" in err_msg or "rate_limit_exceeded" in err_msg:
                logger.warning(
                    f"Ключ {api_key[:8]}... получил 429 ошибку. Бан на 24 часа."
                )
                key_manager.ban_key(api_key)
            else:
                logger.warning(
                    f"Ошибка Groq с ключом {api_key[:8]}... (UA: {user_agent.split('/')[0]}): {e}"
                )

            last_error = e
            continue

    logger.error(
        f"Не удалось получить ответ ни с одного из {len(available_keys)} доступных ключей. Последняя ошибка: {last_error}"
    )
    return None


async def ask_ai(
    user_prompt: str,
    system_prompt: str,
    images: list[str] = None,
    history: list[dict] = None,
    **kwargs,
) -> Optional[str]:
    if AI_PROVIDER == "groq":
        return await ask_groq_ai(
            user_prompt, system_prompt, images=images, history=history, **kwargs
        )
    return await ask_local_ai(
        user_prompt, system_prompt, images=images, history=history, **kwargs
    )

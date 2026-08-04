import base64
import io
import logging
import os
from typing import Optional
import aiohttp
from aiogram.exceptions import TelegramBadRequest
from aiogram import types
from config import (
    AI_AUDIO_EXTRA_COST,
    AI_MAX_REPLY_LEN,
    AI_PERSONAS,
    AI_PROVIDER,
    AI_REQUEST_TIMEOUT,
    AI_VISION_EXTRA_COST,
    COMMAND_METADATA,
    GROQ_API_KEY,
    GROQ_MODEL,
    GROQ_VISION_MODEL,
    OLLAMA_BASE_URL,
    OLLAMA_MODEL,
    OLLAMA_VISION_MODEL,
)
from bot.utils.database import db
from bot.utils.helpers import (
    format_styled_message,
    freeze_tokens,
    get_raw_text,
    get_reply_raw_text,
    refund_tokens,
)
from bot.utils.media_core import download_media_file
from bot.utils.queue_wrapper import process_with_queue
from bot.utils.whisper_core import transcribe_audio
from groq import AsyncGroq

logger = logging.getLogger(__name__)

groq_client = AsyncGroq(api_key=GROQ_API_KEY) if GROQ_API_KEY else None


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


def escape_unclosed_markdown(text: str) -> str:
    chars = list(text)
    stack = {"*": [], "_": [], "`": []}

    i = 0
    in_code_block = False

    while i < len(chars):
        if chars[i] == "\\" and i + 1 < len(chars):
            i += 2
            continue

        if i + 2 < len(chars) and chars[i : i + 3] == ["`", "`", "`"]:
            in_code_block = not in_code_block
            i += 3
            continue

        if in_code_block and chars[i] != "`":
            i += 1
            continue

        char = chars[i]
        if char in stack:
            if stack[char]:
                stack[char].pop()
            else:
                stack[char].append(i)
        i += 1

    unclosed = sorted(
        [idx for indices in stack.values() for idx in indices], reverse=True
    )

    for idx in unclosed:
        chars.insert(idx, "\\")

    res = "".join(chars)

    if in_code_block:
        if not res.endswith("\n"):
            res += "\n"
        res += "```"

    return res


async def ask_local_ai(
    user_prompt: str, system_prompt: str, images: list[str] = None, **kwargs
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

    payload = {
        "model": model_to_use,
        "stream": False,
        "messages": [
            {"role": "system", "content": system_prompt},
            user_message,
        ],
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
    user_prompt: str, system_prompt: str, images: list[str] = None, **kwargs
) -> Optional[str]:
    if not groq_client:
        logger.error("GROQ_API_KEY не установлен!")
        return None

    try:
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

        response = await groq_client.chat.completions.create(
            model=model_to_use,
            messages=[
                {"role": "system", "content": system_prompt},
                user_message,
            ],
            temperature=kwargs.get("temperature", 0.4),
            top_p=kwargs.get("top_p", 0.75),
            max_tokens=kwargs.get("max_tokens", 1024),
            presence_penalty=kwargs.get("presence_penalty", 0.0),
            frequency_penalty=kwargs.get("frequency_penalty", 0.0),
            timeout=AI_REQUEST_TIMEOUT,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        logger.error(f"Ошибка при запросе к Groq API: {e}")
        return None


async def ask_ai(
    user_prompt: str, system_prompt: str, images: list[str] = None, **kwargs
) -> Optional[str]:
    if AI_PROVIDER == "groq":
        return await ask_groq_ai(user_prompt, system_prompt, images=images, **kwargs)
    return await ask_local_ai(user_prompt, system_prompt, images=images, **kwargs)


async def unified_ai_worker(
    reply_msg: Optional[types.Message],
    bot,
    raw_prompt: Optional[str],
    reply_text: Optional[str],
    persona: dict,
) -> Optional[str]:
    base64_images = None

    if reply_msg:
        has_audio_video = any(
            [reply_msg.voice, reply_msg.audio, reply_msg.video_note, reply_msg.video]
        )
        has_photo = bool(reply_msg.photo)

        if has_audio_video:
            try:
                file_path, _ = await download_media_file(reply_msg, bot)
                if file_path:
                    transcribed = await transcribe_audio(
                        file_path=file_path, language="auto"
                    )
                    if transcribed:
                        reply_text = transcribed + (
                            f"\n\nПодпись к медиа: {reply_text}" if reply_text else ""
                        )
                    else:
                        return "ERROR:❌ Не удалось извлечь текст из медиафайла."
                    try:
                        os.unlink(file_path)
                    except Exception:
                        pass
            except Exception as e:
                logger.error(f"Ошибка Whisper внутри очереди: {e}")
                return "ERROR:❌ Ошибка при обработке аудиофайла."

        elif has_photo:
            try:
                photo = reply_msg.photo[-1]
                img_bytes = io.BytesIO()
                await bot.download(photo, destination=img_bytes)
                img_base64 = base64.b64encode(img_bytes.getvalue()).decode("utf-8")
                base64_images = [img_base64]
            except Exception as e:
                logger.error(f"Ошибка Vision внутри очереди: {e}")
                return "ERROR:❌ Ошибка при загрузке изображения."

    if not raw_prompt and not reply_text and base64_images:
        raw_prompt = "Опиши подробно, что ты видишь на этом изображении."

    if not raw_prompt and not reply_text:
        return "ERROR:EMPTY_PROMPT"

    if reply_text:
        if raw_prompt and raw_prompt != reply_text:
            final_prompt = (
                f"Контекст:\n{reply_text}\n\nЗапрос пользователя: {raw_prompt}"
            )
        else:
            final_prompt = reply_text
    else:
        final_prompt = raw_prompt

    user_prompt = persona.get("prompt_template", "{prompt}").format(prompt=final_prompt)

    return await ask_ai(
        user_prompt=user_prompt,
        system_prompt=persona["system_prompt"],
        images=base64_images,
        temperature=persona.get("temperature", 0.5),
        top_p=persona.get("top_p", 0.9),
        max_tokens=persona.get("max_tokens", 1024),
        presence_penalty=persona.get("presence_penalty", 0.0),
        frequency_penalty=persona.get("frequency_penalty", 0.0),
    )


async def process_ai_request(message: types.Message, cmd_key: str):
    persona = AI_PERSONAS.get(cmd_key)
    meta = COMMAND_METADATA.get(cmd_key, {"icon": "🤖", "name": "ИИ"})

    if not persona:
        await message.reply(f"❌ Настройки для {cmd_key} не найдены.")
        return

    icon = meta["icon"]
    name = meta["name"]
    user_id = message.from_user.id

    raw_text = get_raw_text(message)
    parts = raw_text.split(maxsplit=1) if raw_text else []
    reply_text = get_reply_raw_text(message)

    raw_prompt = None
    if len(parts) >= 2:
        raw_prompt = parts[1].strip()

    reply_msg = message.reply_to_message

    action_text = "Анализ запроса"
    extra_cost = 0

    if reply_msg:
        if any(
            [reply_msg.voice, reply_msg.audio, reply_msg.video_note, reply_msg.video]
        ):
            action_text = "Распознавание речи и анализ"
            extra_cost = AI_AUDIO_EXTRA_COST
        elif reply_msg.photo:
            action_text = "Анализ изображения (Vision)"
            extra_cost = AI_VISION_EXTRA_COST

    if not await freeze_tokens(message, user_id, cmd_key, extra_cost):
        return

    target_queue = "lightweights" if AI_PROVIDER == "groq" else "heavyweights"

    answer, wait_msg = await process_with_queue(
        message=message,
        queue_name=target_queue,
        icon=icon,
        title=name,
        action_text=action_text,
        func=unified_ai_worker,
        reply_msg=reply_msg,
        bot=message.bot,
        raw_prompt=raw_prompt,
        reply_text=reply_text,
        persona=persona,
    )

    if not answer:
        await refund_tokens(user_id, cmd_key, extra_cost)
        error_info = (
            "Groq API не ответил. Проверь API_KEY."
            if AI_PROVIDER == "groq"
            else f"Ollama не ответила. Проверь модели {OLLAMA_MODEL}."
        )
        error_api = format_styled_message(
            emoji=icon,
            title=name,
            message=f"❌ Нейросеть не ответила. {error_info}",
        )
        if wait_msg:
            try:
                await wait_msg.edit_text(error_api)
            except Exception:
                await message.reply(error_api)
        return

    if answer.startswith("ERROR:"):
        await refund_tokens(user_id, cmd_key, extra_cost)
        err_type = answer.split("ERROR:", 1)[1]
        if err_type == "EMPTY_PROMPT":
            err_msg = f"❌ Не указан текст или медиа для обработки.\n📝 Напиши текст, либо ответь на текст/голосовое/фото командой <code>{cmd_key}</code>"
        else:
            err_msg = err_type

        formatted_error = format_styled_message(emoji=icon, title=name, message=err_msg)
        if wait_msg:
            try:
                await wait_msg.edit_text(formatted_error)
            except Exception:
                await message.reply(formatted_error)
        return

    if persona.get("strip_quotes"):
        answer = answer.strip().strip('"').strip("'").strip("«").strip("»")

    chunks = split_text(answer)

    first_chunk = format_styled_message(
        emoji=icon,
        title=name,
        message=escape_unclosed_markdown(f"{chunks[0]}{persona['disclaimer']}"),
        html=False,
    )

    try:
        await wait_msg.edit_text(first_chunk, parse_mode="Markdown")
    except TelegramBadRequest:
        logger.warning(
            "Failed to parse Markdown in first_chunk. Falling back to plain text."
        )
        try:
            await wait_msg.edit_text(first_chunk)
        except Exception:
            await message.reply(first_chunk)
    except Exception:
        await message.reply(first_chunk, parse_mode="Markdown")

    for chunk in chunks[1:]:
        safe_chunk = escape_unclosed_markdown(chunk)
        try:
            await message.answer(safe_chunk, parse_mode="Markdown")
        except TelegramBadRequest:
            logger.warning(
                "Failed to parse Markdown in subsequent chunk. Falling back to plain text."
            )
            await message.answer(safe_chunk)

    await db.increment_commands()
    await db.log_command(cmd_key, user_id)


def make_ai_handler(cmd_key: str):
    async def handler(message: types.Message):
        await process_ai_request(message, cmd_key)

    return handler


cmd_ai = make_ai_handler("!ии")
cmd_ai_ham = make_ai_handler("!нейрохам")
cmd_ai_psycho = make_ai_handler("!психолог")
cmd_ai_summary = make_ai_handler("!пересказ")
cmd_ai_nerd = make_ai_handler("!душнила")
cmd_ai_senior = make_ai_handler("!синьор")
cmd_ai_gopnik = make_ai_handler("!гопник")
cmd_ai_joker = make_ai_handler("!шутник")
cmd_ai_tale = make_ai_handler("!сказка")
cmd_ai_babka = make_ai_handler("!бабка")
cmd_ai_drunk = make_ai_handler("!алкаш")

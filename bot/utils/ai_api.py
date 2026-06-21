import logging
import os
import base64
import io
from typing import Optional
import aiohttp
from aiogram import types
from config import (
    OLLAMA_BASE_URL, OLLAMA_MODEL, OLLAMA_VISION_MODEL, AI_MAX_REPLY_LEN,
    AI_REQUEST_TIMEOUT, AI_PERSONAS, COMMAND_METADATA,
    VIP_IDS, COMMAND_COSTS, AI_AUDIO_EXTRA_COST, AI_VISION_EXTRA_COST
)
from bot.utils.database import db
from bot.utils.helpers import format_styled_message, spend_tokens, get_raw_text, get_reply_raw_text
from bot.utils.queue_wrapper import process_with_queue
from bot.utils.media_core import download_media_file
from bot.utils.whisper_core import transcribe_audio
from bot.utils.tokens_database import tokens_db
from bot.owner_settings.config_getters import is_payments_enabled

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


async def ask_local_ai(user_prompt: str, system_prompt: str, images: list[str] = None, **kwargs) -> Optional[str]:
    url = f"{OLLAMA_BASE_URL.rstrip('/')}/api/chat"
    user_message = {"role": "user", "content": user_prompt}

    if images:
        user_message["images"] = images
        model_to_use = OLLAMA_VISION_MODEL
    else:
        model_to_use = OLLAMA_MODEL

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


async def unified_ai_worker(
    reply_msg: Optional[types.Message],
    bot,
    raw_prompt: Optional[str],
    reply_text: Optional[str],
    persona: dict
) -> Optional[str]:
    """
    Единый тяжелый воркер. Вызывается строго внутри очереди process_with_queue.
    Здесь происходит скачивание файлов, Whisper, кодирование Vision и запрос к ИИ.
    """
    base64_images = None

    if reply_msg:
        has_audio_video = any([reply_msg.voice, reply_msg.audio, reply_msg.video_note, reply_msg.video])
        has_photo = bool(reply_msg.photo)

        if has_audio_video:
            try:
                file_path, _ = await download_media_file(reply_msg, bot)
                if file_path:
                    transcribed = await transcribe_audio(file_path=file_path, language="auto")
                    if transcribed:
                        reply_text = transcribed + (f"\n\nПодпись к медиа: {reply_text}" if reply_text else "")
                    else:
                        return "ERROR:❌ Не удалось извлечь текст из медиафайла."
                    try:
                        os.unlink(file_path)
                    except:
                        pass
            except Exception as e:
                logger.error(f"Ошибка Whisper внутри очереди: {e}")
                return "ERROR:❌ Ошибка при обработке аудиофайла."

        elif has_photo:
            try:
                photo = reply_msg.photo[-1]
                img_bytes = io.BytesIO()
                await bot.download(photo, destination=img_bytes)
                img_base64 = base64.b64encode(img_bytes.getvalue()).decode('utf-8')
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
            final_prompt = f"Контекст:\n{reply_text}\n\nЗапрос пользователя: {raw_prompt}"
        else:
            final_prompt = reply_text
    else:
        final_prompt = raw_prompt

    user_prompt = persona["prompt_template"].format(prompt=final_prompt)

    return await ask_local_ai(
        user_prompt=user_prompt,
        system_prompt=persona["system_prompt"],
        images=base64_images,
        temperature=persona["temperature"],
        top_p=persona["top_p"],
        repeat_penalty=persona["repeat_penalty"],
        num_ctx=persona["num_ctx"],
        num_predict=persona["num_predict"]
    )


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

    reply_msg = message.reply_to_message

    action_text = "Анализ запроса"
    if reply_msg:
        if any([reply_msg.voice, reply_msg.audio, reply_msg.video_note, reply_msg.video]):
            action_text = "Распознавание речи и анализ"
        elif reply_msg.photo:
            action_text = "Анализ изображения (Vision)"

    answer, wait_msg = await process_with_queue(
        message=message,
        queue_name="heavyweights",
        icon=icon,
        title=name,
        action_text=action_text,
        func=unified_ai_worker,
        reply_msg=reply_msg,
        bot=message.bot,
        raw_prompt=raw_prompt,
        reply_text=reply_text,
        persona=persona
    )

    if not answer:
        error_api = format_styled_message(
            emoji=icon,
            title=name,
            message=f"❌ Нейросеть не ответила. Проверь, что Ollama запущена и скачаны модели <code>{OLLAMA_MODEL}</code> и <code>{OLLAMA_VISION_MODEL}</code>."
        )
        if wait_msg:
            try: await wait_msg.edit_text(error_api)
            except Exception: await message.reply(error_api)
        return

    if answer.startswith("ERROR:"):
        err_type = answer.split("ERROR:", 1)[1]
        if err_type == "EMPTY_PROMPT":
            err_msg = f"❌ Не указан текст или медиа для обработки.\n📝 Напиши текст, либо ответь на текст/голосовое/фото командой <code>{cmd_key}</code>"
        else:
            err_msg = err_type

        formatted_error = format_styled_message(emoji=icon, title=name, message=err_msg)
        if wait_msg:
            try: await wait_msg.edit_text(formatted_error)
            except Exception: await message.reply(formatted_error)
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

    base_cost = COMMAND_COSTS.get(cmd_key, 0)
    final_cost = base_cost

    if reply_msg:
        if any([reply_msg.voice, reply_msg.audio, reply_msg.video_note, reply_msg.video]):
            final_cost += AI_AUDIO_EXTRA_COST
        elif reply_msg.photo:
            final_cost += AI_VISION_EXTRA_COST

    if await is_payments_enabled() and message.from_user.id not in VIP_IDS and final_cost > 0:
        await tokens_db.spend_tokens(message.from_user.id, final_cost)
        logger.info(f"Пользователь {message.from_user.id} потратил {final_cost} токенов на {cmd_key}")

    await db.increment_commands()
    await db.log_command(cmd_key, message.from_user.id)


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

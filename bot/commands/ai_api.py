import base64
import html
import re
import random
import io
import logging
import os
from typing import Optional
import aiohttp
from aiogram import types
from aiogram.fsm.context import FSMContext
from aiogram.types import InlineKeyboardButton
from bot.state import AIChatMode
from config import (
    AI_AUDIO_EXTRA_COST,
    AI_MAX_REPLY_LEN,
    AI_PERSONAS,
    AI_PROVIDER,
    AI_REQUEST_TIMEOUT,
    AI_VISION_EXTRA_COST,
    COMMAND_METADATA,
    GROQ_MODEL,
    GROQ_VISION_MODEL,
    OLLAMA_BASE_URL,
    OLLAMA_MODEL,
    OLLAMA_VISION_MODEL,
    COMMAND_COSTS,
)
from bot.utils.database import db
from bot.utils.helpers import (
    format_styled_message,
    freeze_tokens,
    get_raw_text,
    get_reply_raw_text,
    refund_tokens,
    its_me,
    create_user_keyboard,
)
from bot.utils.media_core import download_media_file
from bot.utils.queue_wrapper import process_with_queue
from bot.utils.whisper_core import transcribe_audio
from groq import AsyncGroq
from bot.utils.api_key_manager import key_manager
from bot.utils.registry import COMMAND_HANDLERS, register_command

MAX_SINGLE_MSG_CHARS = 2500
MAX_HISTORY_TOTAL_CHARS = 16000

user_chat_histories: dict[int, list] = {}

logger = logging.getLogger(__name__)

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

    for api_key in available_keys:
        user_agent = random.choice(USER_AGENTS)

        client = AsyncGroq(
            api_key=api_key, default_headers={"User-Agent": user_agent}, max_retries=0
        )

        try:
            response = await client.chat.completions.create(
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

            if response.usage:
                total_used = response.usage.total_tokens
                key_manager.add_usage(api_key, total_used)

            return response.choices[0].message.content.strip()

        except Exception as e:
            err_msg = str(e).lower()

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
    user_prompt: str, system_prompt: str, images: list[str] = None, **kwargs
) -> Optional[str]:
    if AI_PROVIDER == "groq":
        return await ask_groq_ai(user_prompt, system_prompt, images=images, **kwargs)
    return await ask_local_ai(user_prompt, system_prompt, images=images, **kwargs)


async def unified_ai_worker(
    msg: Optional[types.Message],
    bot,
    raw_prompt: Optional[str],
    reply_text: Optional[str],
    persona: dict,
    user_id: int = 0,
    first_name: str = "",
) -> Optional[str]:
    base64_images = None

    if msg:
        has_audio_video = any([msg.voice, msg.audio, msg.video_note, msg.video])
        has_photo = bool(msg.photo)

        if has_audio_video:
            try:
                file_path, _ = await download_media_file(msg, bot)
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
                photo = msg.photo[-1]
                img_bytes = io.BytesIO()
                await bot.download(photo, destination=img_bytes)
                img_base64 = base64.b64encode(img_bytes.getvalue()).decode("utf-8")
                base64_images = [img_base64]
            except Exception as e:
                logger.error(f"Ошибка Vision внутри очереди: {e}")
                return "ERROR:❌ Ошибка при загрузке изображения."

    if base64_images:
        vision_prompt = "Опиши максимально подробно, что ты видишь на этом изображении."
        vision_sys = (
            "Ты — точная подсистема компьютерного зрения. Выдавай только факты."
        )

        vision_desc = await ask_ai(vision_prompt, vision_sys, images=base64_images)

        if vision_desc:
            vision_desc = re.sub(
                r"<think>.*?</think>", "", vision_desc, flags=re.DOTALL
            ).strip()

            img_context = f"[СИСТЕМНОЕ СООБЩЕНИЕ: Пользователь прикрепил картинку. Вот её подробное описание от подсистемы зрения:\n{vision_desc}]\n\n"

            if reply_text:
                final_prompt = f"{img_context}Контекст:\n{reply_text}\n\nЗапрос пользователя: {raw_prompt or 'Что скажешь?'}"
            elif raw_prompt:
                final_prompt = f"{img_context}Запрос пользователя: {raw_prompt}"
            else:
                final_prompt = (
                    f"{img_context}Прокомментируй это изображение в своем стиле."
                )

            base64_images = None
        else:
            return "ERROR:❌ Не удалось проанализировать изображение."

    elif reply_text:
        if raw_prompt and raw_prompt != reply_text:
            final_prompt = (
                f"Контекст:\n{reply_text}\n\nЗапрос пользователя: {raw_prompt}"
            )
        else:
            final_prompt = reply_text
    else:
        final_prompt = raw_prompt

    if not final_prompt:
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

    system_prompt = (
        persona["system_prompt"]
        + "\n❌ КАТЕГОРИЧЕСКИ ЗАПРЕЩЕНО: писать в тексте ответа любые действия, эмоции или звуковые эффекты в круглых или квадратных скобках (например, *улыбнулся*, (шепотом), [вздыхает]). Выдавай только чистую прямую речь и текст, без сценических ремарок!"
        + "\n\n[ТЕКУЩИЙ РЕЖИМ: БЛИЦ. Это разовый запрос, у тебя НЕТ памяти прошлых сообщений. Если юзер пытается вести диалог — прямо скажи ему отправить команду !ии_чат, чтобы перейти в режим диалога.]"
    )

    if user_id:
        if its_me(user_id):
            system_prompt += "\n[СИСТЕМНОЕ УВЕДОМЛЕНИЕ: Собеседник — Lonewolf239, твой создатель и автор бота! Учитывай это в своих ответах.]"
        else:
            safe_name = (first_name or "Пользователь").replace("\n", " ")
            system_prompt += f"\n[СИСТЕМНОЕ УВЕДОМЛЕНИЕ: Имя собеседника — '{safe_name}'. Он НЕ является твоим создателем (твой единственный разработчик — Lonewolf239).]"

    answer = await ask_ai(
        user_prompt=persona.get("prompt_template", "{prompt}").format(
            prompt=final_prompt
        ),
        system_prompt=system_prompt,
        images=base64_images,
        temperature=persona.get("temperature", 0.5),
        top_p=persona.get("top_p", 0.9),
        max_tokens=persona.get("max_tokens", 1024),
        presence_penalty=persona.get("presence_penalty", 0.0),
        frequency_penalty=persona.get("frequency_penalty", 0.0),
    )

    if answer:
        answer = re.sub(r"<think>.*?</think>", "", answer, flags=re.DOTALL).strip()

    return answer


async def process_ai_request(message: types.Message, cmd_key: str):
    persona = AI_PERSONAS.get(cmd_key)
    meta = COMMAND_METADATA.get(cmd_key, {"icon": "🤖", "name": "ИИ"})

    if not persona:
        await message.reply(f"❌ Настройки для {cmd_key} не найдены.")
        return

    icon = meta["icon"]
    name = meta["name"]
    user_id = message.from_user.id
    first_name = message.from_user.first_name if message.from_user else ""

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
        msg=reply_msg,
        bot=message.bot,
        raw_prompt=raw_prompt,
        reply_text=reply_text,
        persona=persona,
        user_id=user_id,
        first_name=first_name,
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
        message=f"{format_md_to_html(chunks[0])}{persona['disclaimer']}",
    )

    try:
        await wait_msg.edit_text(first_chunk)
    except Exception:
        await message.reply(first_chunk)

    for chunk in chunks[1:]:
        await message.answer(format_md_to_html(chunk))

    await db.increment_commands()
    await db.log_command(cmd_key, user_id)


def truncate_history_to_budget(
    history: list[str], max_chars: int = MAX_HISTORY_TOTAL_CHARS
) -> list[str]:
    total_chars = sum(len(entry) for entry in history)
    while history and total_chars > max_chars:
        removed = history.pop(0)
        total_chars -= len(removed)
    return history


@register_command("!ии_чат", is_enabled=(AI_PROVIDER == "groq"))
async def cmd_ai_chat(message: types.Message, state: FSMContext):
    if AI_PROVIDER != "groq":
        await message.reply(
            format_styled_message(
                "❌", "НЕДОСТУПНО", "Режим ИИ-чата доступен только при работе с Groq."
            )
        )
        return

    keyboard = []
    row = []
    for cmd_key, persona in AI_PERSONAS.items():
        name = persona.get("name", cmd_key)
        row.append(
            InlineKeyboardButton(
                text=name.lstrip("!"), callback_data=f"chat_persona|{cmd_key}"
            )
        )
        if len(row) == 2:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)

    keyboard.append(
        [InlineKeyboardButton(text="❌ Отмена", callback_data="chat_cancel")]
    )

    await message.reply(
        format_styled_message(
            "💬",
            "ИИ-ЧАТ",
            "Выбери персону для начала диалога. \nДля выхода из чата напиши <code>!выход</code>.",
        ),
        reply_markup=create_user_keyboard(keyboard, message.from_user.id),
    )
    await state.set_state(AIChatMode.choosing_persona)


async def process_chat_persona_callback(
    callback: types.CallbackQuery, state: FSMContext
):
    user_id = callback.from_user.id

    if callback.data == "chat_cancel":
        await state.clear()
        user_chat_histories.pop(user_id, None)
        await callback.message.edit_text("❌ Вход в режим чата отменен.")
        await callback.answer()
        return

    if AI_PROVIDER != "groq":
        await callback.answer(
            "❌ ИИ-чат отключен (режим провайдера изменён).", show_alert=True
        )
        await state.clear()
        return

    _, persona_key = callback.data.split("|")
    persona_data = AI_PERSONAS.get(persona_key)

    if not persona_data:
        await callback.answer("Ошибка: персона не найдена.", show_alert=True)
        return

    user_chat_histories[user_id] = []

    await state.update_data(persona_key=persona_key, msg_count=0)
    await state.set_state(AIChatMode.in_chat)

    await callback.message.edit_text(
        format_styled_message(
            "✅",
            "ЧАТ НАЧАТ",
            f"Ты в чате! Персона: <b>{persona_key}</b>.\nОтправляй текст, фото или голосовые. Для завершения: <code>!выход</code>",
        )
    )
    await callback.answer()


async def chat_ai_worker(
    msg: types.Message,
    bot,
    text: str,
    history: list,
    persona: dict,
    user_id: int,
    first_name: str = "",
) -> tuple[Optional[str], list]:
    has_audio_video = any([msg.voice, msg.audio, msg.video_note, msg.video])
    has_photo = bool(msg.photo)

    extracted_text = text
    base64_images = None

    if has_audio_video:
        try:
            file_path, _ = await download_media_file(msg, bot)
            if file_path:
                transcribed = await transcribe_audio(
                    file_path=file_path, language="auto"
                )
                if transcribed:
                    extracted_text = transcribed + (
                        f"\n\nПодпись: {text}" if text else ""
                    )
                else:
                    return "ERROR:MEDIA_FAILED", history
                try:
                    os.unlink(file_path)
                except Exception:
                    pass
            else:
                return "ERROR:MEDIA_FAILED", history
        except Exception as e:
            logger.error(f"Ошибка Whisper внутри очереди (чат): {e}")
            return "ERROR:MEDIA_FAILED", history

    elif has_photo:
        try:
            photo = msg.photo[-1]
            img_bytes = io.BytesIO()
            await bot.download(photo, destination=img_bytes)
            base64_images = [base64.b64encode(img_bytes.getvalue()).decode("utf-8")]
        except Exception as e:
            logger.error(f"Ошибка Vision внутри очереди (чат): {e}")
            return "ERROR:VISION_FAILED", history

    if base64_images:
        vision_prompt = "Опиши максимально подробно, что ты видишь на этом изображении."
        vision_sys = (
            "Ты — точная подсистема компьютерного зрения. Выдавай только факты."
        )

        vision_desc = await ask_ai(vision_prompt, vision_sys, images=base64_images)

        if vision_desc:
            vision_desc = re.sub(
                r"<think>.*?</think>", "", vision_desc, flags=re.DOTALL
            ).strip()

            img_context = f"[СИСТЕМНОЕ СООБЩЕНИЕ: Пользователь прикрепил картинку. Вот её подробное описание от подсистемы зрения:\n{vision_desc}]\n\n"

            if extracted_text:
                extracted_text = f"{img_context}Сообщение пользователя вместе с картинкой: {extracted_text}"
            else:
                extracted_text = (
                    f"{img_context}Прокомментируй это изображение в своем стиле."
                )

            base64_images = None
        else:
            return "ERROR:VISION_FAILED", history

    if not extracted_text and not base64_images:
        return "ERROR:EMPTY_PROMPT", history

    if len(extracted_text) > MAX_SINGLE_MSG_CHARS:
        extracted_text = extracted_text[:MAX_SINGLE_MSG_CHARS] + "..."

    local_history = history.copy()
    local_history.append(
        f"Пользователь ({first_name or 'Пользователь'}): {extracted_text}"
    )
    if len(local_history) > 10:
        local_history = local_history[-10:]
    local_history = truncate_history_to_budget(local_history)

    max_response_tokens = min(persona.get("max_tokens", 1024), 1024)

    system_prompt = (
        persona["system_prompt"]
        + "\n❌ КАТЕГОРИЧЕСКИ ЗАПРЕЩЕНО: писать в тексте ответа любые действия, эмоции или звуковые эффекты в круглых или квадратных скобках (например, *улыбнулся*, (шепотом), [вздыхает]). Выдавай только чистую прямую речь и текст, без сценических ремарок!"
        + "\n\n[⚠️ ТЕКУЩИЙ РЕЖИМ: ИИ-ЧАТ (!ии_чат). Ты находишься в активном диалоге и ПОМНИШЬ прошлые сообщения из истории ниже. НЕ отрицай наличие памяти!]"
    )

    if user_id:
        if its_me(user_id):
            system_prompt += "\n[СИСТЕМНОЕ УВЕДОМЛЕНИЕ: Собеседник — Lonewolf239, твой создатель и автор бота! Учитывай это в своих ответах.]"
        else:
            safe_name = (first_name or "Пользователь").replace("\n", " ")
            system_prompt += f"\n[СИСТЕМНОЕ УВЕДОМЛЕНИЕ: Имя собеседника — '{safe_name}'. Он НЕ является твоим создателем (твой единственный разработчик — Lonewolf239).]"

    answer = await ask_groq_ai(
        user_prompt="\n".join(local_history),
        system_prompt=system_prompt,
        images=base64_images,
        temperature=persona.get("temperature", 0.5),
        max_tokens=max_response_tokens,
    )

    if answer:
        answer = re.sub(r"<think>.*?</think>", "", answer, flags=re.DOTALL).strip()

    return answer, local_history


async def process_chat_message(message: types.Message, state: FSMContext):
    text = (message.text or message.caption or "").strip()
    user_id = message.from_user.id

    if text.lower() in ["!выход", "/exit", "выход", "!exit"]:
        await state.clear()
        user_chat_histories.pop(user_id, None)
        await message.reply(
            format_styled_message(
                "🛑", "ЧАТ ЗАВЕРШЕН", "Ты вышел из режима диалога с ИИ."
            )
        )
        return

    if AI_PROVIDER != "groq":
        await message.reply("❌ ИИ-чат отключен (режим провайдера изменён).")
        await state.clear()
        return

    first_name = message.from_user.first_name if message.from_user else ""
    data = await state.get_data()
    persona_key = data.get("persona_key", "!ии")
    msg_count = data.get("msg_count", 0)

    history = user_chat_histories.get(user_id, [])

    persona = AI_PERSONAS.get(persona_key, AI_PERSONAS["!ии"])

    has_audio_video = any(
        [message.voice, message.audio, message.video_note, message.video]
    )
    has_photo = bool(message.photo)

    media_extra_cost = 0
    action_text = "Анализ запроса"

    if has_audio_video:
        media_extra_cost = AI_AUDIO_EXTRA_COST
        action_text = "Распознавание речи и анализ"
    elif has_photo:
        media_extra_cost = AI_VISION_EXTRA_COST
        action_text = "Анализ изображения (Vision)"

    total_extra_cost = (msg_count * 2) + media_extra_cost

    if not await freeze_tokens(
        message,
        user_id,
        "!ии_чат",
        extra_cost=total_extra_cost,
        custom_message=(
            "Это сообщение стоит <b>{cost}</b> токенов.\n"
            "На балансе: <b>{balance}</b>.\n"
            "Чат завершен, возвращайся после пополнения!"
        ),
    ):
        await state.clear()
        user_chat_histories.pop(user_id, None)
        return

    meta = COMMAND_METADATA.get(persona_key, {"icon": "💬", "name": persona_key})
    icon = meta.get("icon", "💬")
    name = meta.get("name", persona_key)

    result, wait_msg = await process_with_queue(
        message=message,
        queue_name="lightweights",
        icon=icon,
        title=name,
        action_text=action_text,
        func=chat_ai_worker,
        msg=message,
        bot=message.bot,
        text=text,
        history=history,
        persona=persona,
        user_id=user_id,
        first_name=first_name,
    )

    if not result:
        await refund_tokens(user_id, "!ии_чат", extra_cost=total_extra_cost)
        err_msg = format_styled_message(
            emoji=icon,
            title=name,
            message="❌ Ошибка при постановке в очередь или сбое воркера.",
        )
        if wait_msg:
            try:
                await wait_msg.edit_text(err_msg)
            except Exception:
                await message.reply(err_msg)
        return

    answer, new_history = result

    if not answer:
        await refund_tokens(user_id, "!ии_чат", extra_cost=total_extra_cost)
        err_msg = format_styled_message(
            emoji=icon, title=name, message="❌ ИИ не ответил. Попробуй еще раз."
        )
        if wait_msg:
            try:
                await wait_msg.edit_text(err_msg)
            except Exception:
                await message.reply(err_msg)
        return

    if answer.startswith("ERROR:"):
        await refund_tokens(user_id, "!ии_чат", extra_cost=total_extra_cost)
        err_type = answer.split("ERROR:", 1)[1]
        if err_type == "EMPTY_PROMPT":
            error_text = "⚠️ Сообщение пустое или не содержит распознаваемого текста."
        elif err_type == "MEDIA_FAILED":
            error_text = "⚠️ Не удалось распознать содержимое медиа. Попробуй еще раз."
        elif err_type == "VISION_FAILED":
            error_text = "⚠️ Ошибка при загрузке изображения."
        else:
            error_text = f"⚠️ Ошибка: {err_type}"

        formatted_error = format_styled_message(
            emoji=icon, title=name, message=error_text
        )
        if wait_msg:
            try:
                await wait_msg.edit_text(formatted_error)
            except Exception:
                await message.reply(formatted_error)
        return

    new_history.append(f"ИИ: {answer}")
    new_history = truncate_history_to_budget(new_history)
    user_chat_histories[user_id] = new_history
    await state.update_data(msg_count=msg_count + 1)

    base_cost = COMMAND_COSTS.get("!ии_чат", 5)
    current_cost = base_cost + total_extra_cost

    token_info = f"\n\n<i>🪙 Стоимость сообщения: {current_cost} токенов</i>"
    disclaimer = persona.get("disclaimer", "")

    formatted_answer = f"{format_md_to_html(answer)}{token_info}{disclaimer}"
    chunks = split_text(formatted_answer)

    first_chunk = format_styled_message(emoji=icon, title=name, message=chunks[0])

    try:
        await wait_msg.edit_text(first_chunk)
    except Exception:
        await message.reply(first_chunk)

    for chunk in chunks[1:]:
        await message.answer(chunk)


def make_ai_handler(cmd_key: str):
    async def handler(message: types.Message):
        await process_ai_request(message, cmd_key)

    return handler


for cmd in AI_PERSONAS.keys():
    COMMAND_HANDLERS[cmd] = make_ai_handler(cmd)

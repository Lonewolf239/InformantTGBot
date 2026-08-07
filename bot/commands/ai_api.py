import base64
import io
import logging
import os
import re
from typing import Optional
from aiogram import types
from aiogram.fsm.context import FSMContext
from aiogram.types import InlineKeyboardButton
from bot.state import AIChatMode
from config import (
    AI_AUDIO_EXTRA_COST,
    AI_PERSONAS,
    AI_PROVIDER,
    AI_VISION_EXTRA_COST,
    COMMAND_METADATA,
    COMMAND_COSTS,
    OLLAMA_MODEL,
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
from bot.utils.registry import COMMAND_HANDLERS, register_command
from bot.utils.ai_core import (
    ask_ai,
    ask_groq_ai,
    split_text,
    format_md_to_html,
    truncate_history_to_budget,
    user_chat_histories,
    MAX_SINGLE_MSG_CHARS,
)

logger = logging.getLogger(__name__)


async def _process_message_media(
    msg: types.Message, bot, base_text: Optional[str]
) -> tuple[Optional[str], Optional[list[str]], Optional[str]]:
    has_audio_video = any([msg.voice, msg.audio, msg.video_note, msg.video])
    has_photo = bool(msg.photo)

    extracted_text = base_text
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
                        f"\n\nПодпись: {base_text}" if base_text else ""
                    )
                else:
                    return None, None, "ERROR:MEDIA_FAILED"
                try:
                    os.unlink(file_path)
                except Exception:
                    pass
            else:
                return None, None, "ERROR:MEDIA_FAILED"
        except Exception as e:
            logger.error(f"Ошибка Whisper при обработке медиа: {e}")
            return None, None, "ERROR:MEDIA_FAILED"

    elif has_photo:
        try:
            photo = msg.photo[-1]
            img_bytes = io.BytesIO()
            await bot.download(photo, destination=img_bytes)
            base64_images = [base64.b64encode(img_bytes.getvalue()).decode("utf-8")]
        except Exception as e:
            logger.error(f"Ошибка Vision при обработке изображения: {e}")
            return None, None, "ERROR:VISION_FAILED"

    return extracted_text, base64_images, None


async def _get_vision_context(
    base64_images: list[str],
) -> tuple[Optional[str], Optional[str]]:
    vision_prompt = "Опиши максимально подробно, что ты видишь на этом изображении."
    vision_sys = "Ты — точная подсистема компьютерного зрения. Выдавай только факты."
    vision_desc = await ask_ai(vision_prompt, vision_sys, images=base64_images)

    if vision_desc:
        vision_desc = re.sub(
            r"<think>.*?</think>", "", vision_desc, flags=re.DOTALL
        ).strip()
        img_context = f"[СИСТЕМНОЕ СООБЩЕНИЕ: Пользователь прикрепил картинку. Вот её подробное описание от подсистемы зрения:\n{vision_desc}]\n\n"
        return img_context, None
    return None, "ERROR:VISION_FAILED"


def _build_system_prompt(
    persona: dict, user_id: int, first_name: str, chat_mode: bool
) -> str:
    prompt = persona.get("system_prompt", "")

    if not persona.get("allow_actions", False):
        prompt += "\n❌ КАТЕГОРИЧЕСКИ ЗАПРЕЩЕНО: описывать свои физические действия, эмоции, мимику или звуки (ни в скобках, ни звездочками, ни просто текстом). Ты — текстовый ИИ, а не актер. Выдавай ТОЛЬКО свои слова и прямую речь."

    if chat_mode:
        prompt += "\n\n[⚠️ ТЕКУЩИЙ РЕЖИМ: ИИ-ЧАТ (!ии_чат). Ты находишься в активном диалоге и ПОМНИШЬ прошлые сообщения из истории ниже. НЕ отрицай наличие памяти!]"
    else:
        prompt += "\n\n[РЕЖИМ БЕЗ ПАМЯТИ. Предлагай команду !ии_чат ТОЛЬКО если юзер явно зовет общаться, играть или жалуется на забытый контекст. На обычные вопросы отвечай прямо и не упоминай эту команду.]"

    if user_id:
        if its_me(user_id):
            prompt += "\n[СИСТЕМНОЕ УВЕДОМЛЕНИЕ: Собеседник — Lonewolf239, твой создатель и автор бота! Учитывай это в своих ответах.]"
        else:
            safe_name = (first_name or "Пользователь").replace("\n", " ")
            prompt += f"\n[СИСТЕМНОЕ УВЕДОМЛЕНИЕ: Имя собеседника — '{safe_name}'. Он НЕ является твоим создателем (твой единственный разработчик — Lonewolf239).]"

    return prompt


async def unified_ai_worker(
    msg: Optional[types.Message],
    bot,
    raw_prompt: Optional[str],
    reply_text: Optional[str],
    persona: dict,
    user_id: int = 0,
    first_name: str = "",
    reply_author_name: str = "",
    reply_author_id: int = 0,
) -> Optional[str]:
    extracted_reply_text = reply_text
    base64_images = None

    if msg:
        extracted_reply_text, base64_images, err = await _process_message_media(
            msg, bot, reply_text
        )
        if err:
            return err.replace("ERROR:", "ERROR:❌ Ошибка: ")

    img_context = ""
    if base64_images:
        img_context, err = await _get_vision_context(base64_images)
        if err:
            return "ERROR:❌ Не удалось проанализировать изображение."
        base64_images = None

    if img_context:
        if extracted_reply_text:
            author_info = f"пользователя {reply_author_name}"
            if its_me(reply_author_id):
                author_info = "твоего создателя (Lonewolf239)"
            elif reply_author_id == bot.id:
                author_info = "тебя самого (бота)"
            final_prompt = f"{img_context}[КОНТЕКСТ: Сообщение от {author_info}]:\n{extracted_reply_text}\n\nЗапрос текущего пользователя: {raw_prompt or 'Что скажешь?'}"
        elif raw_prompt:
            final_prompt = f"{img_context}Запрос пользователя: {raw_prompt}"
        else:
            final_prompt = f"{img_context}Прокомментируй это изображение в своем стиле."

    elif extracted_reply_text:
        author_info = f"пользователя {reply_author_name}"
        if its_me(reply_author_id):
            author_info = "твоего создателя (Lonewolf239)"
        elif reply_author_id == bot.id:
            author_info = "тебя самого (бота)"

        reply_context = f"[ВНИМАНИЕ: Пользователь отвечает на сообщение от {author_info}. Текст этого сообщения:\n«{extracted_reply_text}»]\n\n"

        if raw_prompt and raw_prompt != extracted_reply_text:
            final_prompt = (
                f"{reply_context}Ответ/Запрос текущего пользователя: {raw_prompt}"
            )
        else:
            final_prompt = f"{reply_context}Ответь на это сообщение."
    else:
        final_prompt = raw_prompt

    if not final_prompt:
        return "ERROR:EMPTY_PROMPT"

    if persona.get("is_twin", False):
        from bot.twin.persona import ask_twin

        answer = await ask_twin(
            user_prompt=final_prompt,
            user_id=user_id,
            first_name=first_name,
            temperature=persona.get("temperature", 0.7),
            top_p=persona.get("top_p", 0.9),
            max_tokens=persona.get("max_tokens", 1024),
            presence_penalty=persona.get("presence_penalty", 0.3),
            frequency_penalty=persona.get("frequency_penalty", 0.3),
        )
        return answer

    system_prompt = _build_system_prompt(persona, user_id, first_name, chat_mode=False)

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


async def chat_ai_worker(
    msg: types.Message,
    bot,
    text: str,
    history: list,
    persona: dict,
    user_id: int,
    first_name: str = "",
) -> tuple[Optional[str], list]:

    if persona.get("is_twin"):
        from bot.twin.database import twin_db
        from bot.twin.persona import (
            _assemble_system_prompt,
            _resolve_needed_knowledge,
            _resolve_similar_examples,
            _maybe_learn_from_owner,
            _plan_reaction,
            _format_plan_note,
            SPLIT_INSTRUCTION_NOTE,
            TWIN_BACKGROUND_QUEUE,
        )
        from bot.utils.helpers import its_me
        from bot.utils.task_queue import queue_manager
        import asyncio

        is_owner = bool(user_id and its_me(user_id))
        if is_owner:
            await queue_manager.add_task(TWIN_BACKGROUND_QUEUE, _maybe_learn_from_owner, text)
        elif user_id:
            asyncio.create_task(twin_db.upsert_contact_seen(user_id, first_name))

        access_level = await twin_db.get_access_level(user_id, is_owner)

        system_prompt = await _assemble_system_prompt(
            user_id, first_name, chat_mode=True
        )

        knowledge_lines = await _resolve_needed_knowledge(text, access_level)
        if knowledge_lines:
            system_prompt += (
                "\n\n[ИЗВЕСТНЫЕ ФАКТЫ О ТЕБЕ, ЕСЛИ РЕЛЕВАНТНЫ ЗАПРОСУ]:\n"
                + "\n".join(f"- {line}" for line in knowledge_lines)
            )
        system_prompt += await _resolve_similar_examples(text)

        plan = await _plan_reaction(text)
        system_prompt += _format_plan_note(plan)
        system_prompt += SPLIT_INSTRUCTION_NOTE
    else:
        system_prompt = _build_system_prompt(
            persona, user_id, first_name, chat_mode=True
        )

    extracted_text, base64_images, err = await _process_message_media(msg, bot, text)
    if err:
        return err, history

    img_context = ""
    if base64_images:
        img_context, err = await _get_vision_context(base64_images)
        if err:
            return err, history
        base64_images = None

        if extracted_text:
            extracted_text = f"{img_context}Сообщение пользователя вместе с картинкой: {extracted_text}"
        else:
            extracted_text = (
                f"{img_context}Прокомментируй это изображение в своем стиле."
            )

    if not extracted_text and not base64_images:
        return "ERROR:EMPTY_PROMPT", history

    if len(extracted_text) > MAX_SINGLE_MSG_CHARS:
        extracted_text = extracted_text[:MAX_SINGLE_MSG_CHARS] + "..."

    local_history = history.copy()
    if len(local_history) > 9:
        local_history = local_history[-9:]
    local_history = truncate_history_to_budget(local_history)

    max_response_tokens = min(persona.get("max_tokens", 1024), 1024)

    if persona.get("is_twin"):
        from bot.twin.persona import generate_twin_reply, SPLIT_MARKER

        answer = await generate_twin_reply(
            extracted_text,
            system_prompt,
            {
                "temperature": persona.get("temperature", 0.5),
                "max_tokens": max_response_tokens,
            },
            history=local_history,
            images=base64_images,
            use_candidates=True,
        )
        history_answer = answer.replace(SPLIT_MARKER, "\n") if answer else answer
    else:
        answer = await ask_groq_ai(
            user_prompt=extracted_text,
            system_prompt=system_prompt,
            images=base64_images,
            history=local_history,
            temperature=persona.get("temperature", 0.5),
            max_tokens=max_response_tokens,
        )
        if answer:
            answer = re.sub(r"<think>.*?</think>", "", answer, flags=re.DOTALL).strip()
        history_answer = answer

    local_history.append({"role": "user", "content": extracted_text})
    if answer:
        local_history.append({"role": "assistant", "content": history_answer})
    local_history = truncate_history_to_budget(local_history)

    return answer, local_history


async def process_ai_request(message: types.Message, cmd_key: str):
    persona = AI_PERSONAS.get(cmd_key)
    meta = COMMAND_METADATA.get(cmd_key, {"icon": "🤖", "name": "ИИ"})

    if not persona:
        await message.reply(
            format_styled_message("❌", "ОШИБКА", f"Настройки для {cmd_key} не найдены.")
        )
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

    reply_author_name = (
        reply_msg.from_user.first_name if (reply_msg and reply_msg.from_user) else ""
    )
    reply_author_id = (
        reply_msg.from_user.id if (reply_msg and reply_msg.from_user) else 0
    )

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
        reply_author_name=reply_author_name,
        reply_author_id=reply_author_id,
    )

    if not answer:
        await refund_tokens(user_id, cmd_key, extra_cost)
        error_info = (
            "Groq API не ответил. Проверь API_KEY."
            if AI_PROVIDER == "groq"
            else f"Ollama не ответила. Проверь модели {OLLAMA_MODEL}."
        )
        error_api = format_styled_message(
            emoji=icon, title=name, message=f"❌ Нейросеть не ответила. {error_info}"
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

    feedback_keyboard = None
    if persona.get("is_twin"):
        from bot.twin.persona import split_twin_answer
        from bot.twin.feedback import build_feedback_keyboard

        pieces = split_twin_answer(answer) or [answer]
        feedback_keyboard = await build_feedback_keyboard(
            user_id, raw_prompt or reply_text or "", answer
        )
    else:
        pieces = [answer]

    chunks = [c for piece in pieces for c in split_text(piece)]
    first_chunk = format_styled_message(
        emoji=icon,
        title=name,
        message=f"{format_md_to_html(chunks[0])}{persona['disclaimer']}",
    )

    try:
        await wait_msg.edit_text(first_chunk, reply_markup=feedback_keyboard)
    except Exception:
        await message.reply(first_chunk, reply_markup=feedback_keyboard)

    for chunk in chunks[1:]:
        await message.answer(format_md_to_html(chunk))

    await db.increment_commands()
    await db.log_command(cmd_key, user_id)


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
        await callback.message.edit_text(
            format_styled_message("❌", "ИИ-ЧАТ", "Вход в режим чата отменен.")
        )
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
        await message.reply(
            format_styled_message("❌", "ИИ-ЧАТ", "ИИ-чат отключен (режим провайдера изменён).")
        )
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

    user_chat_histories[user_id] = new_history
    await state.update_data(msg_count=msg_count + 1)

    base_cost = COMMAND_COSTS.get("!ии_чат", 5)
    current_cost = base_cost + total_extra_cost
    token_info = (
        f"\n\n<i>🪙 Стоимость сообщения: {current_cost} токенов</i>\n"
        f"<i>🛑 Для выхода из чата напиши <code>!выход</code></i>"
    )
    disclaimer = persona.get("disclaimer", "")

    feedback_keyboard = None
    if persona.get("is_twin"):
        from bot.twin.persona import split_twin_answer
        from bot.twin.feedback import build_feedback_keyboard

        pieces = split_twin_answer(answer) or [answer]
        feedback_keyboard = await build_feedback_keyboard(user_id, text, answer)
    else:
        pieces = [answer]

    formatted_pieces = [format_md_to_html(p) for p in pieces]
    formatted_pieces[-1] = formatted_pieces[-1] + token_info + disclaimer
    chunks = [c for piece in formatted_pieces for c in split_text(piece)]

    first_chunk = format_styled_message(emoji=icon, title=name, message=chunks[0])

    try:
        await wait_msg.edit_text(first_chunk, reply_markup=feedback_keyboard)
    except Exception:
        await message.reply(first_chunk, reply_markup=feedback_keyboard)

    for chunk in chunks[1:]:
        await message.answer(chunk)


def make_ai_handler(cmd_key: str):
    async def handler(message: types.Message):
        await process_ai_request(message, cmd_key)

    return handler


for cmd in AI_PERSONAS.keys():
    COMMAND_HANDLERS[cmd] = make_ai_handler(cmd)

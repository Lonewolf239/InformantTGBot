from aiogram import types
from config import AI_PROVIDER
from bot.utils.helpers import its_me, get_raw_text, format_styled_message
from bot.utils.registry import register_command
from bot.utils.queue_wrapper import process_with_queue
from bot.twin.interview import (
    start_session,
    start_sequential_session,
    submit_answers,
    skip_sequential_question,
    cancel_active_session,
    QUESTIONS_MIN,
    QUESTIONS_MAX,
)

QUEUE_NAME = "lightweights" if AI_PROVIDER == "groq" else "heavyweights"


def _parse_count(message: types.Message, default: int = 7) -> int:
    raw = get_raw_text(message) or ""
    parts = raw.split()
    if len(parts) > 1:
        try:
            return max(QUESTIONS_MIN, min(QUESTIONS_MAX, int(parts[1])))
        except ValueError:
            pass
    return default


@register_command("!двойник_вопросы")
async def cmd_twin_questions(message: types.Message):
    if not its_me(message.from_user.id):
        return False

    count = _parse_count(message)

    result, wait_msg = await process_with_queue(
        message=message,
        queue_name=QUEUE_NAME,
        icon="🧬",
        title="Вопросы для двойника",
        action_text="Генерация вопросов",
        func=start_session,
        owner_id=message.from_user.id,
        count=count,
    )
    if result is None:
        return True

    questions, error = result

    if error == "already_active":
        await wait_msg.edit_text(
            format_styled_message(
                "🧬",
                "Вопросы для двойника",
                "У тебя уже есть незавершённая сессия вопросов. Ответь на неё "
                "через <code>!двойник_ответы</code> или сбрось <code>!двойник_отмена</code>.",
            )
        )
        return True
    if error == "generation_failed" or not questions:
        await wait_msg.edit_text(
            format_styled_message(
                "❌", "Вопросы для двойника", "Не удалось сгенерировать вопросы, попробуй ещё раз."
            )
        )
        return True

    lines = [f"{i}. {q['question']}" for i, q in enumerate(questions, 1)]
    body = "\n".join(lines)
    await wait_msg.edit_text(
        format_styled_message(
            "🧬",
            "ВОПРОСЫ ДЛЯ ДВОЙНИКА",
            "Ответь одним сообщением в формате:\n"
            "<code>!двойник_ответы</code>\n"
            "<code>1. ...</code>\n"
            "<code>2. ...</code>\n"
            "и так далее (можно пропускать номера)\n\n"
            f"{body}",
        )
    )
    return True


@register_command("!двойник_ответы")
async def cmd_twin_answers(message: types.Message):
    if not its_me(message.from_user.id):
        return False

    raw = get_raw_text(message) or ""
    parts = raw.split(maxsplit=1)
    payload = parts[1].strip() if len(parts) > 1 else ""

    if not payload and message.reply_to_message:
        reply = message.reply_to_message
        payload = (reply.text or reply.caption or "").strip()

    if not payload:
        await message.reply(
            format_styled_message(
                "🧬",
                "ОТВЕТЫ НА ИНТЕРВЬЮ",
                "Пришли ответы после команды или реплаем на своё сообщение с ними, "
                "в формате <code>1. ...</code> с новой строки на каждый пункт.",
            )
        )
        return True

    result, wait_msg = await process_with_queue(
        message=message,
        queue_name=QUEUE_NAME,
        icon="🧬",
        title="Ответы на интервью",
        action_text="Разбор ответов и обучение двойника",
        func=submit_answers,
        owner_id=message.from_user.id,
        raw_text=payload,
    )
    if result is None:
        return True

    count, error = result

    if error == "no_active_session":
        await wait_msg.edit_text(
            format_styled_message(
                "🧬",
                "Ответы на интервью",
                "Нет активной сессии вопросов. Сначала запроси их: "
                "<code>!двойник_вопросы</code>.",
            )
        )
        return True
    if error == "unparsable":
        await wait_msg.edit_text(
            format_styled_message(
                "❌",
                "Ответы на интервью",
                "Не удалось разобрать ответы. Формат: каждый пункт с новой строки, "
                "начиная с номера — <code>1. текст</code>, <code>2. текст</code>…",
            )
        )
        return True

    await wait_msg.edit_text(
        format_styled_message(
            "✅",
            "Ответы приняты",
            f"Принято ответов: {count}. Отправлено в обучение двойника "
            "(стиль + факты). Спасибо, это заметно уточняет личность.",
        )
    )
    return True


@register_command("!двойник_отмена")
async def cmd_twin_cancel(message: types.Message):
    if not its_me(message.from_user.id):
        return False

    ok = await cancel_active_session(message.from_user.id)
    if ok:
        await message.reply(
            format_styled_message("✅", "ИНТЕРВЬЮ", "Активная сессия вопросов отменена.")
        )
    else:
        await message.reply(
            format_styled_message("ℹ️", "ИНТЕРВЬЮ", "Нет активной сессии для отмены.")
        )
    return True


@register_command("!двойник_подряд")
async def cmd_twin_questions_sequential(message: types.Message):
    if not its_me(message.from_user.id):
        return False

    count = _parse_count(message)

    result, wait_msg = await process_with_queue(
        message=message,
        queue_name=QUEUE_NAME,
        icon="🧬",
        title="Интервью по одному",
        action_text="Генерация вопросов",
        func=start_sequential_session,
        owner_id=message.from_user.id,
        count=count,
    )
    if result is None:
        return True

    questions, error = result

    if error == "already_active":
        await wait_msg.edit_text(
            format_styled_message(
                "🧬",
                "Интервью по одному",
                "У тебя уже есть незавершённая сессия вопросов. Ответь на неё, "
                "пропусти <code>!двойник_пропустить</code> или сбрось <code>!двойник_отмена</code>.",
            )
        )
        return True
    if error == "generation_failed" or not questions:
        await wait_msg.edit_text(
            format_styled_message(
                "❌", "Интервью по одному", "Не удалось сгенерировать вопросы, попробуй ещё раз."
            )
        )
        return True

    await wait_msg.edit_text(
        format_styled_message(
            "🧬",
            "ИНТЕРВЬЮ ПО ОДНОМУ ВОПРОСУ",
            "Просто отвечай обычным сообщением на каждый вопрос.\n"
            "Пропустить вопрос: <code>!двойник_пропустить</code>\n"
            "Прервать интервью: <code>!двойник_отмена</code>\n\n"
            f"<b>Вопрос 1/{len(questions)}:</b>\n{questions[0]['question']}",
        )
    )
    return True


@register_command("!двойник_пропустить")
async def cmd_twin_skip_question(message: types.Message):
    if not its_me(message.from_user.id):
        return False

    result = await skip_sequential_question(message.from_user.id)
    if not result:
        await message.reply(
            format_styled_message(
                "ℹ️", "ИНТЕРВЬЮ", "Нет активного последовательного интервью, нечего пропускать."
            )
        )
        return True

    if result["done"]:
        await message.reply(
            format_styled_message("✅", "ИНТЕРВЬЮ", "Интервью завершено (последний вопрос пропущен).")
        )
    else:
        await message.reply(
            format_styled_message(
                "⏭",
                "ВОПРОС ПРОПУЩЕН",
                f"<b>Вопрос {result['next_index']}/{result['total']}:</b>\n"
                f"{result['next_question']}",
            )
        )
    return True

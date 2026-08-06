import ast
import inspect
import logging
import re
import textwrap
from typing import Optional
from aiogram import types
from config import AI_PROVIDER, COMMAND_METADATA
from bot.commands.ai_api import ask_ai, format_md_to_html, split_text
from bot.utils.database import db
from bot.utils.helpers import (
    format_styled_message,
    freeze_tokens,
    get_raw_text,
    refund_tokens,
)
from bot.utils.queue_wrapper import process_with_queue
from bot.utils.registry import register_command

API_ICON = COMMAND_METADATA["!анализ"]["icon"]
API_NAME = COMMAND_METADATA["!анализ"]["name"]

logger = logging.getLogger(__name__)


def get_deep_source(func, max_depth=2):
    visited = set()
    sources = []

    def crawl(f, current_depth):
        if current_depth > max_depth or f in visited:
            return
        visited.add(f)

        try:
            src = inspect.getsource(f)
            sources.append(
                f"# --- Функция: {f.__name__} (Уровень {current_depth + 1}) ---\n{src.strip()}"
            )
        except (TypeError, OSError):
            return

        if current_depth < max_depth:
            try:
                tree = ast.parse(textwrap.dedent(src))
            except SyntaxError:
                return

            for node in ast.walk(tree):
                target_obj = None

                if isinstance(node, ast.Call):
                    if isinstance(node.func, ast.Name):
                        func_name = node.func.id
                        target_obj = getattr(f, "__globals__", {}).get(func_name)

                    elif isinstance(node.func, ast.Attribute) and isinstance(
                        node.func.value, ast.Name
                    ):
                        obj_name = node.func.value.id
                        attr_name = node.func.attr
                        obj = getattr(f, "__globals__", {}).get(obj_name)
                        if obj:
                            target_obj = getattr(obj, attr_name, None)

                    if target_obj and inspect.isroutine(target_obj):
                        mod = inspect.getmodule(target_obj)
                        if mod and getattr(mod, "__name__", "").startswith(
                            ("bot", "config")
                        ):
                            crawl(target_obj, current_depth + 1)

    crawl(func, 0)
    return "\n\n".join(sources)


async def code_explain_worker(source_code: str, base_command: str) -> Optional[str]:
    system_prompt = (
        "Ты — дружелюбный ИИ-проводник по возможности бота.\n"
        "Твоя задача — изучить исходный код команды бота и объяснить РЯДОВОМУ ПОЛЬЗОВАТЕЛЮ (не программисту), "
        "как и почему эта команда работает.\n\n"
        "Требования к ответу:\n"
        "1. Объясняй принцип работы простым, понятным и увлекательным языком. Избегай сложного программистского сленга "
        "(переменные, функции, AST, декораторы, асинхронность и т.д.) и не вдавайся в ревью кода.\n"
        "2. НЕ ищи ошибки, баги или узкие места — сосредоточься только на объяснении алгоритма для обычного юзера.\n"
        "3. Пошагово расскажи: что команда делает в момент вызова, с какими данными работает и какой результат отдаёт."
    )

    user_prompt = (
        f"Объясни простому пользователю, как работает команда <code>{base_command}</code>, основываясь на её коде:\n\n"
        f"<pre>{source_code}</pre>"
    )

    answer = await ask_ai(user_prompt=user_prompt, system_prompt=system_prompt)
    if answer:
        answer = re.sub(r"<think>.*?</think>", "", answer, flags=re.DOTALL).strip()
    return answer


@register_command("!анализ")
async def cmd_analyze_code(message: types.Message):
    from bot.handlers.public import ALIAS_TO_BASE, COMMAND_HANDLERS

    raw_text = get_raw_text(message)
    args = raw_text.split(maxsplit=1) if raw_text else []
    user_id = message.from_user.id
    cmd_key = "!анализ"

    if len(args) < 2:
        error_msg = format_styled_message(
            emoji=API_ICON,
            title=API_NAME,
            message="❌ <b>Укажи команду для анализа.</b>\n📝 Пример: <code>!анализ !курс_крипты</code>",
        )
        return await message.reply(error_msg)

    target_cmd = args[1].lower().strip()
    base_command = ALIAS_TO_BASE.get(target_cmd, target_cmd)

    if base_command not in COMMAND_HANDLERS:
        error_msg = format_styled_message(
            emoji="❌",
            title="НЕ НАЙДЕНО",
            message=f"Команда <code>{target_cmd}</code> не найдена в словаре обработчиков.",
        )
        return await message.reply(error_msg)

    handler_func = COMMAND_HANDLERS[base_command]

    try:
        source_code = get_deep_source(handler_func, 2)
    except Exception as e:
        logger.error(f"Ошибка получения исходников для {base_command}: {e}")
        return await message.reply(
            format_styled_message(
                emoji="❌",
                title="ОШИБКА ИСХОДНИКОВ",
                message=f"Не удалось получить исходный код:\n<code>{e}</code>",
            )
        )

    if not await freeze_tokens(message, user_id, cmd_key):
        return

    target_queue = "lightweights" if AI_PROVIDER == "groq" else "heavyweights"

    answer, wait_msg = await process_with_queue(
        message=message,
        queue_name=target_queue,
        icon=API_ICON,
        title=API_NAME,
        action_text="Разбор логики команды",
        func=code_explain_worker,
        source_code=source_code,
        base_command=base_command,
    )

    if not answer:
        await refund_tokens(user_id, cmd_key)
        error_msg = format_styled_message(
            emoji="❌",
            title="ОШИБКА",
            message="Нейросеть не ответила или не удалось сформировать объяснение.",
        )
        if wait_msg:
            try:
                await wait_msg.edit_text(error_msg)
            except Exception:
                await message.reply(error_msg)
        return

    chunks = split_text(answer)

    first_chunk = format_styled_message(
        emoji=API_ICON,
        title=f"КАК РАБОТАЕТ: {base_command}",
        message=format_md_to_html(chunks[0]),
    )

    try:
        await wait_msg.edit_text(first_chunk)
    except Exception:
        await message.reply(first_chunk)

    for chunk in chunks[1:]:
        await message.answer(format_md_to_html(chunk))

    await db.increment_commands()
    await db.log_command(cmd_key, user_id)

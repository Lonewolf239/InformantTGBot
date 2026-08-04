import ast
import inspect
import logging
import re
import textwrap
from aiogram import types
from config import COMMAND_METADATA
from bot.handlers.public import COMMAND_HANDLERS, ALIAS_TO_BASE
from bot.utils.ai_api import ask_ai
from bot.utils.database import db
from bot.utils.helpers import (
    format_styled_message,
    freeze_tokens,
    refund_tokens,
    get_raw_text,
)

API_ICON = COMMAND_METADATA["!анализ"]["icon"]
API_NAME = COMMAND_METADATA["!анализ"]["name"]

logger = logging.getLogger(__name__)


def get_deep_source(func, max_depth=1):
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


async def cmd_analyze_code(message: types.Message):
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
        source_code = get_deep_source(handler_func, max_depth=1)
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

    system_prompt = (
        "Ты — Senior Python Developer и опытный AI-анализатор кода. "
        "Твоя задача — принимать исходный код функций Telegram-бота (на aiogram 3) и проводить их ревью.\n"
        "Тебе будет передан код основного обработчика (Уровень 1), а также код вспомогательных функций (Уровень 2), которые он вызывает.\n"
        "1. Кратко объясни логику работы этой цепочки вызовов.\n"
        "2. Укажи на возможные ошибки, баги, или узкие места.\n"
        "3. Предложи улучшения.\n"
        "Отвечай структурированно. Обязательно используй HTML-теги (<b>жирный</b>, <i>курсив</i>, <code>код</code>, <pre>блоки кода</pre>). Категорически запрещено использовать Markdown."
    )

    user_prompt = f"Проанализируй цепочку вызовов для команды <code>{base_command}</code>:\n\n<pre>{source_code}</pre>"

    wait_msg = await message.reply(
        format_styled_message(
            emoji="⏳",
            title=API_NAME,
            message="<i>Ищу связи, читаю функции и анализирую исходный код...</i>",
        )
    )

    try:
        answer = await ask_ai(user_prompt=user_prompt, system_prompt=system_prompt)

        if not answer:
            await refund_tokens(user_id, cmd_key)
            return await wait_msg.edit_text(
                format_styled_message(
                    emoji="❌", title="ОШИБКА", message="Нейросеть не ответила."
                )
            )

        answer = re.sub(r"<think>.*?</think>", "", answer, flags=re.DOTALL).strip()

        await wait_msg.edit_text(
            format_styled_message(
                emoji=API_ICON, title=f"РЕВЬЮ: {base_command}", message=answer
            )
        )

        await db.increment_commands()
        await db.log_command(cmd_key, user_id)

    except Exception as e:
        logger.error(f"Ошибка при анализе кода ИИ: {e}")
        await refund_tokens(user_id, cmd_key)
        await wait_msg.edit_text(
            format_styled_message(
                emoji="❌",
                title="ОШИБКА ИИ",
                message=f"Произошла ошибка при анализе:\n<code>{e}</code>",
            )
        )

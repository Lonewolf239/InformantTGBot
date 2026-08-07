from aiogram import types
import inspect
import logging
from aiogram.fsm.context import FSMContext
from config import (
    COMMAND_ALIASES,
    WELCOME_TEXT,
    KEYWORD_REACTIONS,
    SIMPLE_ANSWERS,
    COMMAND_METADATA,
    SFW_RP_ACTIONS,
    NSFW_RP_ACTIONS,
)
from bot.utils.keyword_handlers import KEYWORD_COMMANDS_REGISTRY
from bot.utils.user_settings import user_settings_db
from bot.utils.helpers import (
    its_me,
    get_raw_text,
    format_styled_message,
)
from bot.utils.database import db
from bot.owner_settings.config_getters import (
    is_payments_enabled,
    is_auto_reply_enabled,
    is_reply_to_owner,
)
from bot.utils.registry import COMMAND_HANDLERS, register_command
from bot.handlers.help_menus import send_universal_menu

logger = logging.getLogger(__name__)


@register_command("!баланс")
async def cmd_balance(message: types.Message):
    from bot.handlers.payments import cmd_user_balance

    await cmd_user_balance(message)


@register_command("!настройки")
async def cmd_user_settings(message: types.Message):
    from bot.handlers.nsfw_settings import cmd_nsfw_settings

    await cmd_nsfw_settings(message)


@register_command("!отключенные")
async def cmd_disabled_list(message: types.Message):
    disabled_cmds = []

    for cmd, data in COMMAND_METADATA.items():
        if data.get("disabled", False):
            reason = data.get("disabled_reason", "Причина не указана")
            icon = data.get("icon", "🚫")
            disabled_cmds.append(f"<b>{icon}</b> <code>{cmd}</code> — {reason}")

    if not disabled_cmds:
        text = "В данный момент все команды работают в штатном режиме!"
        await message.reply(format_styled_message("✅", "ВСЕ РАБОТАЕТ", text))
    else:
        text = "\n".join(disabled_cmds)
        await message.reply(format_styled_message("🚫", "ОТКЛЮЧЕННЫЕ КОМАНДЫ", text))

    await db.increment_commands()
    await db.log_command("!отключенные", message.from_user.id)
    return True


async def get_rp_commands(user_id: int = None):
    sfw_list = [
        f"{action[0] if action else '🎭'} <code>{cmd}</code>"
        for cmd, action in SFW_RP_ACTIONS.items()
    ]
    body = "🎭 SFW RP КОМАНДЫ:\n" + "\n".join(sfw_list)

    if user_id and await user_settings_db.get_nsfw_setting(user_id):
        nsfw_list = [
            f"{action[0] if action else '🎭'} <code>{cmd}</code>"
            for cmd, action in NSFW_RP_ACTIONS.items()
        ]
        body += "\n\n🔞 NSFW RP КОМАНДЫ (18+):\n" + "\n".join(nsfw_list)

    body += "\n\nОтветь на сообщение и напиши: [команда] &lt;слова&gt;"
    return format_styled_message("🎭", "RP КОМАНДЫ", body)


@register_command("!старт")
async def cmd_start(message: types.Message):
    await message.reply(WELCOME_TEXT)
    await db.increment_commands()
    await db.log_command("!старт", message.from_user.id)
    return True


@register_command("!помощь")
async def cmd_help(message: types.Message):
    return await send_universal_menu(message, "help", "!помощь")


@register_command("!алиасы")
async def cmd_aliases(message: types.Message):
    return await send_universal_menu(message, "aliases", "!алиасы")


@register_command("!прайс")
async def cmd_prices(message: types.Message):
    return await send_universal_menu(message, "prices", "!прайс")


@register_command("!рп")
async def cmd_rp_commands(message: types.Message):
    user_id = message.from_user.id
    await message.reply(await get_rp_commands(user_id))
    await db.increment_commands()
    await db.log_command("!рп", message.from_user.id)
    return True


@register_command("!о_боте")
async def cmd_about(message: types.Message):
    bot_user = await message.bot.get_me()
    bot_name = bot_user.full_name
    bot_username = bot_user.username

    about_text = format_styled_message(
        "🤖",
        "О БОТЕ",
        f"📝 Название: <a href='https://t.me/{bot_username}'>{bot_name}</a> "
        "(<a href='https://github.com/Lonewolf239/InformantTGBot'>GitHub</a>)\n"
        "🛠️ Функции:\n"
        "  • Автоответчик при режиме «отошёл»\n"
        "  • RP команды (обнять, поцеловать и др.)\n"
        "  • Анекдоты из API и Мемы с описанием\n"
        "  • Погода в любом городе\n"
        "  • Локальный ИИ через Ollama\n"
        "  • Расшифровка и перевод медиа\n"
        "  • Скачивание с YouTube\n"
        "💻 Разработчик: <a href='https://t.me/an1onime'>Lonewolf239</a>\n"
        "📊 Статистика: <code>!статистика</code> (только для владельца)\n"
        "🎭 Для RP команд: ответь на сообщение и напиши <code>!обнять</code>",
    )
    await message.reply(about_text, disable_web_page_preview=True)
    await db.increment_commands()
    await db.log_command("!о_боте", message.from_user.id)
    return True


@register_command("!donut")
async def cmd_donut(message: types.Message):
    donut_text = format_styled_message(
        "🍩",
        "ПОДДЕРЖАТЬ РАЗРАБОТЧИКА",
        "💖 Если тебе нравится бот и ты хочешь помочь его развитию:\n\n"
        "🔗 DonationAlerts:\n"
        "https://www.donationalerts.com/r/lonewolf239\n\n"
        "🙏 Спасибо за поддержку! ❤️\n"
        "🍩 Даже маленькая сумма помогает боту жить!",
    )
    await message.reply(donut_text, disable_web_page_preview=True)
    await db.increment_commands()
    await db.log_command("!donut", message.from_user.id)
    return True


async def handle_keywords(message: types.Message):
    import re

    raw_text = get_raw_text(message, False)
    if not raw_text:
        return False

    for keyword_key, reply in KEYWORD_REACTIONS.items():
        match_found = False

        if keyword_key.startswith("[{") and keyword_key.endswith("}]"):
            actual_kw = keyword_key[2:-2]
            pattern = r"\b" + re.escape(actual_kw) + r"\b"

            if re.search(pattern, raw_text):
                match_found = True

        elif keyword_key.startswith("[[") and keyword_key.endswith("]]"):
            actual_kw = keyword_key[2:-2]
            pattern = r"\b" + re.escape(actual_kw) + r"\b"

            matches = re.finditer(pattern, raw_text, re.IGNORECASE)

            for match in matches:
                if match.group(0) != actual_kw:
                    match_found = True
                    break

        else:
            pattern = r"\b" + re.escape(keyword_key) + r"\b"

            if re.search(pattern, raw_text, re.IGNORECASE):
                match_found = True

        if match_found:
            if reply.startswith("cmd:"):
                method_name = reply.split("cmd:")[1]
                handler_func = KEYWORD_COMMANDS_REGISTRY.get(method_name)

                if handler_func:
                    await handler_func(message)
                    return True
                else:
                    logging.error(
                        f"Метод {method_name} не найден в KEYWORD_COMMANDS_REGISTRY"
                    )
            else:
                await message.reply(reply)
                return True

    return False


async def handle_simple_answers(message: types.Message):
    raw_text = get_raw_text(message)
    if not raw_text:
        return False

    text = raw_text

    text_normalized = text.rstrip("?").rstrip("!").rstrip(".").strip()

    if text_normalized in SIMPLE_ANSWERS:
        await message.reply(SIMPLE_ANSWERS[text_normalized])
        return True
    if text in SIMPLE_ANSWERS:
        await message.reply(SIMPLE_ANSWERS[text])
        return True
    return False


ALIAS_TO_BASE = {}
for base_cmd, aliases in COMMAND_ALIASES.items():
    for alias in aliases:
        ALIAS_TO_BASE[alias] = base_cmd


async def process_public_commands(message: types.Message, state: FSMContext = None):
    raw_text = get_raw_text(message)
    if not raw_text:
        return False

    text = raw_text
    command_trigger = text.split()[0]
    base_command = ALIAS_TO_BASE.get(command_trigger)

    if not base_command:
        if await is_auto_reply_enabled():
            if not its_me(message.from_user.id) or await is_reply_to_owner():
                if await handle_simple_answers(message):
                    return True

                if await handle_keywords(message):
                    return True
        return False

    if COMMAND_METADATA.get(base_command, {}).get("disabled", False):
        await message.reply(
            format_styled_message(
                emoji="❌",
                title="ОШИБКА",
                message="Данная команда временно отключена администратором.",
            )
        )
        return True

    if (
        base_command in ("!прайс", "!баланс", "!рулетка", "!дуэль")
        and not await is_payments_enabled()
    ):
        return False

    handler = COMMAND_HANDLERS.get(base_command)
    if handler:
        sig = inspect.signature(handler)
        if "state" in sig.parameters and state is not None:
            await handler(message, state)
        else:
            await handler(message)
        return True

    return False

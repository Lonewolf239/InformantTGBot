from aiogram import types
import inspect
import logging
from aiogram.fsm.context import FSMContext
from aiogram.types import InlineKeyboardButton
from config import (
    COMMAND_ALIASES,
    WELCOME_TEXT,
    KEYWORD_REACTIONS,
    SIMPLE_ANSWERS,
    HELP_GROUPS,
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
    create_user_keyboard,
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
    sfw_list = []
    for cmd, action in SFW_RP_ACTIONS.items():
        emoji = action[0] if action else "🎭"
        sfw_list.append(f"<b>├─ {emoji}</b> <code>{cmd}</code>")

    sfw_text = "\n".join(sfw_list)
    result = f"<b>┌─ 🎭 SFW RP КОМАНДЫ</b>\n{sfw_text}"

    if user_id and await user_settings_db.get_nsfw_setting(user_id):
        nsfw_list = []
        for cmd, action in NSFW_RP_ACTIONS.items():
            emoji = action[0] if action else "🎭"
            nsfw_list.append(f"<b>├─ {emoji}</b> <code>{cmd}</code>")
        nsfw_text = "\n".join(nsfw_list)
        result += f"\n<b>│</b>\n<b>├─ 🔞 NSFW RP КОМАНДЫ (18+)</b>\n{nsfw_text}"

    result += (
        "\n<b>│</b>\n<b>└─</b> Ответь на сообщение и напиши: [команда] &lt;слова&gt;\n"
    )
    return result


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


async def get_main_help_text() -> str:
    from bot.state import state

    is_away = await state.is_away_mode

    status_emoji = "🚶‍♂️" if is_away else "🟢"
    status_text = "режим ОТОШЁЛ активен" if is_away else "режим ОНЛАЙН"

    text = (
        "<b>┌─ 🤖 МЕНЮ КОМАНД</b>\n"
        "<b>├─</b> Выбери нужную категорию ниже, чтобы\n"
        "<b>├─</b> посмотреть список доступных команд.\n"
        "<b>│</b>\n"
        "<b>├─ 🔗 <i>Авто-сохранение ссылок</i></b>\n"
        "<b>├─   Отправь ссылку на музыку/видео, и она</b>\n"
        "<b>├─   появится у владельца в !ссылки</b>\n"
        "<b>│</b>\n"
        f"<b>├─ {status_emoji} Статус:</b> {status_text}\n"
        "<b>└─ 🤖 Автоответ:</b> Мгновенный при включённом режиме"
    )
    return text


async def send_help_menu(
    target: types.Message | types.CallbackQuery, is_edit: bool = False
):
    buttons = []

    for group_id, group_name in HELP_GROUPS.items():
        buttons.append(
            [
                InlineKeyboardButton(
                    text=group_name, callback_data=f"help_cat_{group_id}"
                )
            ]
        )

    user_id = target.from_user.id
    keyboard = create_user_keyboard(buttons, user_id)
    text = await get_main_help_text()

    if is_edit:
        await target.message.edit_text(text, reply_markup=keyboard)
    else:
        await target.reply(text, reply_markup=keyboard)


async def process_help_category(call: types.CallbackQuery, group_id: str):
    category_name = HELP_GROUPS.get(group_id, "Команды")
    text = ""
    payments_on = await is_payments_enabled()

    for cmd, data in COMMAND_METADATA.items():
        if data.get("group") == group_id and not data.get("disabled", False):
            if not payments_on and cmd in ("!прайс", "!баланс", "!рулетка", "!дуэль"):
                continue

            args_str = f" {data['args']}" if "args" in data else ""
            text += (
                f"<b>{data['icon']}</b> <code>{cmd}</code>{args_str} — {data['desc']}\n"
            )

    buttons = [
        [InlineKeyboardButton(text="🔙 Назад в меню", callback_data="help_main")]
    ]

    keyboard = create_user_keyboard(buttons, call.from_user.id)
    await call.message.edit_text(
        format_styled_message(emoji="", title=category_name.upper(), message=text),
        reply_markup=keyboard,
    )


async def process_help_main(call: types.CallbackQuery):
    await send_help_menu(call, is_edit=True)


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

    about_text = (
        f"<b>┌─ 🤖 О БОТЕ</b>\n"
        f"<b>├─ 📝 Название:</b> <a href='https://t.me/{bot_username}'>{bot_name}</a> (<a href='https://github.com/Lonewolf239/InformantTGBot'>GitHub</a>)\n"
        "<b>├─ 🛠️ Функции:</b>\n"
        "<b>├─  •</b> Автоответчик при режиме «отошёл»\n"
        "<b>├─  •</b> RP команды (обнять, поцеловать и др.)\n"
        "<b>├─  •</b> Анекдоты из API и Мемы с описанием\n"
        "<b>├─  •</b> Погода в любом городе\n"
        "<b>├─  •</b> Локальный ИИ через Ollama\n"
        "<b>├─  •</b> Расшифровка и перевод медиа\n"
        "<b>├─  •</b> Скачивание с YouTube\n"
        "<b>├─ 💻 Разработчик:</b> <a href='https://t.me/an1onime'>Lonewolf239</a>\n"
        "<b>├─ 📊 Статистика:</b> <code>!статистика</code> (только для владельца)\n"
        "<b>└─ 🎭 Для RP команд:</b> ответь на сообщение и напиши <code>!обнять</code>"
    )
    await message.reply(about_text, disable_web_page_preview=True)
    await db.increment_commands()
    await db.log_command("!о_боте", message.from_user.id)
    return True


@register_command("!donut")
async def cmd_donut(message: types.Message):
    donut_text = (
        "<b>┌─ 🍩 ПОДДЕРЖАТЬ РАЗРАБОТЧИКА</b>\n"
        "<b>├─ 💖 Если тебе нравится бот и ты хочешь помочь\n├─ его развитию:</b>\n"
        "<b>│</b>\n"
        "<b>├─ 🔗 DonationAlerts:</b>\n"
        "<b>├─</b> https://www.donationalerts.com/r/lonewolf239\n"
        "<b>│</b>\n"
        "<b>├─ 🙏 Спасибо за поддержку! ❤️</b>\n"
        "<b>└─ 🍩 Даже маленькая сумма помогает боту жить!</b>"
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

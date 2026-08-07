from aiogram import types
from aiogram.types import InlineKeyboardButton
from config import (
    COMMAND_ALIASES,
    HELP_GROUPS,
    COMMAND_METADATA,
    DEFAULT_DAILY_TOKENS,
)
from bot.utils.helpers import (
    format_styled_message,
    create_user_keyboard,
)
from bot.utils.database import db
from bot.owner_settings.config_getters import is_payments_enabled


def get_token_word(cost: int) -> str:
    if cost % 10 == 1 and cost % 100 != 11:
        return "токен"
    elif 2 <= cost % 10 <= 4 and (cost % 100 < 10 or cost % 100 >= 20):
        return "токена"
    return "токенов"


async def build_main_menu_data(view_type: str, user_id: int):
    if view_type == "help":
        from bot.state import state

        is_away = await state.is_away_mode
        status_emoji = "🚶‍♂️" if is_away else "🟢"
        status_text = "режим ОТОШЁЛ активен" if is_away else "режим ОНЛАЙН"

        text = format_styled_message(
            "🤖",
            "МЕНЮ КОМАНД",
            "Выбери нужную категорию ниже, чтобы посмотреть список доступных команд.\n\n"
            "🔗 <i>Авто-сохранение ссылок</i>\n"
            "Отправь ссылку на музыку/видео, и она появится у владельца в !ссылки\n\n"
            f"{status_emoji} Статус: {status_text}\n"
            "🤖 Автоответ: Мгновенный при включённом режиме",
        )
    elif view_type == "aliases":
        text = format_styled_message(
            "🔀",
            "СИНОНИМЫ КОМАНД (АЛИАСЫ)",
            "Выбери категорию ниже.\n<i>Регистр букв значения не имеет.</i>",
        )
    elif view_type == "prices":
        text = format_styled_message(
            "💰",
            "ПРАЙС-ЛИСТ КОМАНД",
            f"🎁 Ежедневный лимит: {DEFAULT_DAILY_TOKENS} токенов\n"
            "💳 Узнать свой баланс: <code>!баланс</code>\n\n"
            "Выбери категорию ниже:",
        )

    buttons = [
        [
            InlineKeyboardButton(
                text=name.upper(), callback_data=f"{view_type}_cat_{gid}"
            )
        ]
        for gid, name in HELP_GROUPS.items()
    ]
    keyboard = create_user_keyboard(buttons, user_id)
    return text, keyboard


async def build_category_view_data(view_type: str, group_id: str, user_id: int):
    category_name = HELP_GROUPS.get(group_id, "Категория")
    payments_on = await is_payments_enabled()
    lines = []

    for cmd, data in COMMAND_METADATA.items():
        if data.get("group") != group_id or data.get("disabled", False):
            continue
        if not payments_on and cmd in ("!прайс", "!баланс", "!рулетка", "!дуэль"):
            continue

        icon = data.get("icon", "🔹")

        if view_type == "help":
            args_str = f" {data['args']}" if "args" in data else ""
            lines.append(f"<b>{icon}</b> <code>{cmd}</code>{args_str} — {data['desc']}")

        elif view_type == "aliases":
            aliases = [a for a in COMMAND_ALIASES.get(cmd, []) if a != cmd]
            if aliases:
                aliases_formatted = ", ".join(f"<code>{a}</code>" for a in aliases)
                lines.append(f"<b>{icon}</b> <code>{cmd}</code> ➔ {aliases_formatted}")

        elif view_type == "prices":
            cost = data.get("cost", 0)
            if cost > 0:
                lines.append(
                    f"<b>{icon}</b> <code>{cmd}</code> — {cost} {get_token_word(cost)}"
                )

    if not lines:
        lines.append("<i>В этой категории нет доступных данных.</i>")

    text = format_styled_message(
        emoji="", title=category_name.upper(), message="\n".join(lines)
    )
    buttons = [
        [
            InlineKeyboardButton(
                text="🔙 Назад к категориям", callback_data=f"{view_type}_main"
            )
        ]
    ]
    keyboard = create_user_keyboard(buttons, user_id)

    return text, keyboard


async def process_menu_main_callback(call: types.CallbackQuery):
    view_type = call.data.split("_")[0]
    text, keyboard = await build_main_menu_data(view_type, call.from_user.id)
    await call.message.edit_text(text, reply_markup=keyboard)
    await call.answer()


async def process_menu_category_callback(call: types.CallbackQuery):
    parts = call.data.split("_")
    view_type = parts[0]
    group_id = parts[2]

    text, keyboard = await build_category_view_data(
        view_type, group_id, call.from_user.id
    )
    await call.message.edit_text(text, reply_markup=keyboard)
    await call.answer()


async def send_universal_menu(message: types.Message, view_type: str, cmd_name: str):
    text, keyboard = await build_main_menu_data(view_type, message.from_user.id)
    await message.reply(text, reply_markup=keyboard)
    await db.increment_commands()
    await db.log_command(cmd_name, message.from_user.id)
    return True

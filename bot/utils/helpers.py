from config import OWNER_ID
from typing import Union, List
from aiogram.types import InlineKeyboardMarkup
from aiogram import types


def its_me(user_id: int) -> bool:
    return user_id == OWNER_ID


def get_raw_text(message: types.Message, normalize: bool = True) -> str | None:
    raw_text = message.text or message.caption
    if not raw_text:
        return None
    if normalize:
        raw_text = raw_text.lower().strip()
    return raw_text


def get_reply_raw_text(message: types.Message, normalize: bool = True) -> str | None:
    if not message.reply_to_message:
        return None
    raw_reply_text = message.reply_to_message.text or message.reply_to_message.caption
    if not raw_reply_text:
        return None
    if normalize:
        raw_reply_text = raw_reply_text.lower().strip()
    return raw_reply_text


def create_user_keyboard(inline_keyboard: list, user_id: int) -> InlineKeyboardMarkup:
    for row in inline_keyboard:
        for btn in row:
            if btn.callback_data and not btn.callback_data.startswith("nsfw_"):
                btn.callback_data = f"{btn.callback_data}:usr_{user_id}"
    return InlineKeyboardMarkup(inline_keyboard=inline_keyboard)


def format_styled_message(emoji: str, title: str, message: str, html: bool = True) -> str:
    bold_start = "<b>"
    bold_end = "</b>"
    if not html:
        bold_start = "*"
        bold_end = "*"

    lines = message.split('\n')

    last_content_idx = -1
    for idx in range(len(lines) - 1, -1, -1):
        if lines[idx].strip():
            last_content_idx = idx
            break

    formatted_lines = [f"{bold_start}┌─ {emoji} {title}{bold_end}"]

    for i, line in enumerate(lines):
        if not line.strip():
            formatted_lines.append(f"{bold_start}│{bold_end}")
        else:
            if i == last_content_idx or (last_content_idx == -1 and i == len(lines) - 1):
                prefix = f"{bold_start}└─{bold_end} "
            else:
                prefix = f"{bold_start}├─{bold_end} "
            formatted_lines.append(f"{prefix}{line}")

    return "\n".join(formatted_lines)


async def spend_tokens(message: types.Message, command):
    from config import COMMAND_COSTS, VIP_IDS, PAYMENTS_ENABLED
    if PAYMENTS_ENABLED:
        from bot.utils.tokens_database import tokens_db
        cost = COMMAND_COSTS.get(command, 0)
        if cost > 0 and message.from_user.id not in VIP_IDS:
            await tokens_db.spend_tokens(message.from_user.id, cost)

from config import OWNER_ID
from typing import Union, List
from aiogram.types import InlineKeyboardMarkup


def its_me(user_id: int) -> bool:
    return user_id == OWNER_ID


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

from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from bot.links.database import get_type_emoji_and_name, format_date


def create_submenu_keyboard(grouped_links: dict):
    if not grouped_links:
        return "<b>┌─ 🎉 НОВЫХ ССЫЛОК НЕТ</b>\n└─ Кто-нибудь пришлёт вам музыку.", None

    total_count = sum(grouped_links.values())
    text = (
        f"<b>┌─ 📬 НОВЫЕ ССЫЛКИ</b>\n"
        f"<b>├─ Всего:</b> {total_count} шт.\n"
        f"<b>├─</b>\n"
        f"<b>└─ Выберите категорию:</b>"
    )

    keyboard = []
    for link_type, count in grouped_links.items():
        emoji, type_name = get_type_emoji_and_name(link_type)
        keyboard.append([
            InlineKeyboardButton(
                text=f"{emoji} {type_name} ({count})", 
                callback_data=f"links_submenu|{link_type}"
            )
        ])

    keyboard.append([InlineKeyboardButton(text="🔄 Обновить", callback_data="links_refresh")])

    return text, InlineKeyboardMarkup(inline_keyboard=keyboard)


def create_unviewed_list_keyboard(links: list, link_type: str, page: int = 0) -> tuple:
    ITEMS_PER_PAGE = 10

    if not links:
        emoji, type_name = get_type_emoji_and_name(link_type)
        return f"<b>┌─ {emoji} НЕТ ССЫЛОК</b>\n└─ В категории <b>{type_name}</b> нет непросмотренных ссылок.", None

    total_pages = (len(links) - 1) // ITEMS_PER_PAGE + 1
    start_idx = page * ITEMS_PER_PAGE
    end_idx = min(start_idx + ITEMS_PER_PAGE, len(links))
    page_links = links[start_idx:end_idx]

    emoji, type_name = get_type_emoji_and_name(link_type)

    text = (
        f"<b>┌─ {emoji} {type_name}</b>\n"
        f"<b>├─ Всего:</b> {len(links)} шт.\n"
    )

    if total_pages > 1:
        text += f"<b>├─ Страница:</b> {page + 1}/{total_pages}\n"

    text += (
        f"<b>├─</b>\n"
        f"<b>└─ Нажмите на ссылку, чтобы открыть:</b>"
    )

    keyboard = []
    for link in page_links:
        link_id, url, _, from_username, from_first_name, date_str = link
        sender = from_first_name or from_username or "неизвестный"
        display_text = f"📅 {format_date(date_str)} от {sender}"
        keyboard.append([
            InlineKeyboardButton(
                text=display_text, 
                callback_data=f"links_open|{link_id}"
            )
        ])

    nav_row = []
    if page > 0:
        nav_row.append(
            InlineKeyboardButton(text="⬅️ Назад", callback_data=f"links_typepage|{link_type}|{page-1}")
        )
    if page < total_pages - 1:
        nav_row.append(
            InlineKeyboardButton(text="Вперёд ➡️", callback_data=f"links_typepage|{link_type}|{page+1}")
        )
    if nav_row:
        keyboard.append(nav_row)

    keyboard.append([
        InlineKeyboardButton(text="✅ Отметить все", callback_data=f"links_markall|{link_type}"),
        InlineKeyboardButton(text="↩️ К категориям", callback_data="links_back")
    ])

    return text, InlineKeyboardMarkup(inline_keyboard=keyboard)

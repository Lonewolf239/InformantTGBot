import re
from aiogram import types
from bot.links.database import (
    save_link, get_link, detect_link_type, get_unviewed_links_grouped,
    get_unviewed_links_by_type, delete_link, get_stats
)
from bot.links.keyboard import create_submenu_keyboard, create_unviewed_list_keyboard
from bot.utils.helpers import get_raw_text
from config import OWNER_ID
import logging

logger = logging.getLogger(__name__)

URL_PATTERN = re.compile(r'https?://[^\s]+')


async def process_incoming_link(message: types.Message):
    raw_text = get_raw_text(message)
    if not raw_text:
        return False

    text = raw_text

    urls = URL_PATTERN.findall(text)
    if not urls:
        return False

    user = message.from_user
    chat_id = message.chat.id

    saved_count = 0
    for url in urls:
        link_type = detect_link_type(url)
        if await save_link(
            url=url,
            link_type=link_type,
            from_user_id=user.id,
            from_username=user.username or "",
            from_first_name=user.first_name or "",
            chat_id=chat_id
        ):
            saved_count += 1

    if saved_count > 0:
        emoji = "🎵" if saved_count == 1 else "📚"
        await message.reply(
            f"<b>┌─ {emoji} ССЫЛКА СОХРАНЕНА</b>\n"
            f"├─ Сохранено ссылок: {saved_count}\n"
            f"└─ Владелец увидит их в меню <code>!ссылки</code>"
        )
        return True

    return False


async def cmd_links(message: types.Message):
    if message.from_user.id != OWNER_ID:
        await message.reply("<b>┌─ ❌ Ошибка</b>\n└─ Эта команда только для владельца бота.")
        return True

    grouped = await get_unviewed_links_grouped()
    text, reply_markup = create_submenu_keyboard(grouped)

    if reply_markup:
        await message.reply(text, reply_markup=reply_markup)
    else:
        await message.reply(text)
    return True


async def cmd_links_stats(message: types.Message):
    if message.from_user.id != OWNER_ID:
        return False

    stats = await get_stats()
    await message.reply(
        "<b>┌─ 📊 СТАТИСТИКА ССЫЛОК</b>\n"
        f"<b>├─ 📎 Всего ссылок:</b> {stats['total']}\n"
        f"<b>├─ 👀 Непросмотренных:</b> {stats['unviewed']}\n"
        f"<b>├─ 📋 Типов сервисов:</b> {stats['types_count']}\n"
        f"<b>└─ 👥 Отправителей:</b> {stats['senders_count']}"
    )
    return True


async def links_callback_handler(callback_query: types.CallbackQuery):
    if callback_query.from_user.id != OWNER_ID:
        await callback_query.answer("❌ Недоступно", show_alert=False)
        return

    data = callback_query.data

    if data.startswith("links_submenu|"):
        link_type = data.split("|")[1]
        links = await get_unviewed_links_by_type(link_type)
        text, reply_markup = create_unviewed_list_keyboard(links, link_type)

        await callback_query.message.edit_text(
            text,
            reply_markup=reply_markup
        )

    elif data == "links_back":
        grouped = await get_unviewed_links_grouped()
        text, reply_markup = create_submenu_keyboard(grouped)

        await callback_query.message.edit_text(
            text,
            reply_markup=reply_markup
        )

    elif data.startswith("links_typepage|"):
        parts = data.split("|")
        link_type = parts[1]
        page = int(parts[2])
        links = await get_unviewed_links_by_type(link_type)
        text, reply_markup = create_unviewed_list_keyboard(links, link_type, page)

        await callback_query.message.edit_text(
            text,
            reply_markup=reply_markup
        )

    elif data.startswith("links_open|"):
        link_id = int(data.split("|")[1])

        try:
            url = await get_link(link_id)

            if url:
                await callback_query.message.reply(url)
                await delete_link(link_id)

                await callback_query.answer("✅ Ссылка отмечена как просмотренная")
                grouped = await get_unviewed_links_grouped()
                if grouped:
                    text, reply_markup = create_submenu_keyboard(grouped)
                    await callback_query.message.edit_text(
                        text,
                        reply_markup=reply_markup
                    )
                else:
                    await callback_query.message.edit_text(
                        "<b>┌─ 🎉 ВСЕ ССЫЛКИ ПРОСМОТРЕНЫ</b>\n"
                        "└─ Больше нет непросмотренных ссылок!"
                    )
            else:
                await callback_query.answer("❌ Ссылка не найдена", show_alert=True)
        except Exception as e:
            logger.error(f"Ошибка при открытии ссылки: {e}")
            await callback_query.answer("Ошибка", show_alert=True)

    elif data.startswith("links_markall|"):
        link_type = data.split("|")[1]
        links = await get_unviewed_links_by_type(link_type)
        marked_count = len(links)

        deleted_count = 0
        for link in links:
            if await delete_link(link[0]):
                deleted_count += 1

        grouped = await get_unviewed_links_grouped()
        if grouped:
            text, reply_markup = create_submenu_keyboard(grouped)
            await callback_query.message.edit_text(
                text,
                reply_markup=reply_markup
            )
        else:
            await callback_query.message.edit_text(
                f"<b>┌─ ✅ ОТМЕЧЕНО</b>\n"
                f"├─ Отмечено как просмотренные: {marked_count} ссылок\n"
                f"└─ 🎉 Больше нет непросмотренных ссылок!"
            )

    elif data == "links_refresh":
        grouped = await get_unviewed_links_grouped()
        text, reply_markup = create_submenu_keyboard(grouped)

        if reply_markup:
            await callback_query.message.edit_text(
                text,
                reply_markup=reply_markup
            )
        else:
            await callback_query.message.edit_text(text)

    await callback_query.answer()

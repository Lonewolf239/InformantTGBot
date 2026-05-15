from aiogram import types
from bot.state import state
from bot.stats import stats
from bot.utils.database import db
from datetime import datetime
from bot.links.handlers import cmd_links, cmd_links_stats
from functools import lru_cache

@lru_cache(maxsize=1)
def get_owner_help_text():
    return (
        "<b>┌─ 👑 КОМАНДЫ ВЛАДЕЛЬЦА</b>\n"
        "<b>├─</b> <code>!отошёл</code>\n"
        "<b>├─</b> <code>!вернулся</code>\n"
        "<b>├─</b> <code>!статус</code>\n"
        "<b>├─</b> <code>!статистика</code>\n"
        "<b>├─</b> <code>!сброс_таймеров</code>\n"
        "<b>├─</b> <code>!очистить_статус [id]</code>\n"
        "<b>├─</b> <code>!ссылки</code>\n"
        "<b>├─</b> <code>!линкстат</code>\n"
        "<b>├─</b> <code>!ждущие</code>\n"
        "<b>├─</b> <code>!nsfw</code>\n"
        "<b>│</b>\n"
        "<b>└─ 📖 Публичная справка:</b> <code>!помощь</code>"
    )

async def process_owner_commands(message: types.Message):
    text = message.text.strip()

    commands = {
        "!отошёл": cmd_away_on,
        "!вернулся": cmd_away_off,
        "!статус": cmd_status,
        "!ownerhelp": cmd_owner_help,
        "/help": cmd_owner_help,
        "!статистика": cmd_stats,
        "!сброс_таймеров": cmd_reset_timers,
        "!ссылки": cmd_links,
        "!линкстат": cmd_links_stats,
        "!ждущие": cmd_waiting,
        "!nsfw": cmd_nsfw_stats,
    }

    if text.startswith("!очистить_статус"):
        return await cmd_clear_status(message)

    if text in commands:
        return await commands[text](message)

    return False

async def cmd_away_on(message: types.Message):
    if not await state.is_away_mode:
        await state.set_away_mode(True)
        await message.reply(
            "<b>┌─ 🚶‍♂️ Режим «ОТОШЁЛ»</b>\n"
            "<b>├─ Статус:</b> Включён\n"
            "<b>├─ Действие:</b> Автоответ приходит мгновенно, 1 раз на пользователя\n"
            "<b>└─ Выключение:</b> <code>!вернулся</code>"
        )
        db.increment_away_toggled()
    else:
        await message.reply("<b>┌─ ⚠️ Ошибка</b>\n└─ Режим «отошёл» уже включён! Чтобы выключить — напиши <code>!вернулся</code>")
    return True

async def cmd_away_off(message: types.Message):
    if await state.is_away_mode:
        awaiting_users = await state.get_awaiting_users()
        awaiting_count = len(awaiting_users)

        await state.reset_session()
        await state.set_away_mode(False)

        report = (
            "<b>┌─ 🏠 Режим «ОТОШЁЛ» ВЫКЛЮЧЕН</b>\n"
            "<b>├─ Статус:</b> Выключен\n"
            "<b>├─ Автоответчик:</b> Отключён\n"
            f"<b>├─ 👥 Ожидали ответа:</b> {awaiting_count} человек\n"
        )

        if awaiting_count > 0:
            report += "<b>│</b>\n<b>├─ 📋 СПИСОК ОЖИДАВШИХ:</b>\n"

            for user in awaiting_users:
                name = user["name"]
                username = user.get("username")

                if username:
                    link = f'<a href="https://t.me/{username}">{name}</a>'
                else:
                    link = f'<a href="tg://user?id={user.get("user_id")}">{name}</a>'

                msg_time = user.get("first_msg_time")
                time_str = msg_time.strftime("%H:%M") if msg_time else "?"
                report += f"<b>├─</b> {link} — {time_str}\n"

            report += "<b>│</b>\n<b>└─ 💡 Напиши им, когда будет время!</b>"
        else:
            report += "<b>└─ 💤 За время отсутствия никто не писал</b>"

        await message.reply(report, disable_web_page_preview=True)
        db.increment_away_toggled()
    else:
        await message.reply("<b>┌─ ✅ Информация</b>\n└─ Ты и так в режиме онлайн! Чтобы включить «отошёл» — напиши <code>!отошёл</code>")
    return True

async def cmd_status(message: types.Message):
    state_info = await state.get_stats()
    status_text = "🚶‍♂️ ОТОШЁЛ (автоответ включён)" if state_info["is_away"] else "🟢 ОНЛАЙН (автоответ выключен)"

    await message.reply(
        "<b>┌─ 📊 Текущий статус</b>\n"
        f"<b>├─ Режим:</b> {status_text}\n"
        f"<b>├─ Получили автоответ:</b> {state_info['auto_replied_count']}\n"
        f"<b>├─ Ожидают ответа:</b> {state_info['awaiting_count']}\n"
        f"<b>└─ Всего автоответов за всё время:</b> {stats.auto_replies_sent}"
    )
    return True

async def cmd_waiting(message: types.Message):
    if not await state.is_away_mode:
        await message.reply("<b>┌─ ℹ️ Инфо</b>\n└─ Режим «отошёл» не активен, список ожидающих пуст.")
        return True

    awaiting_users = await state.get_awaiting_users()
    count = len(awaiting_users)

    if count == 0:
        await message.reply("<b>┌─ 📭 Пусто</b>\n└─ Пока никто не написал в твоё отсутствие.")
        return True

    users_list = []
    for user in awaiting_users:
        user_id = user.get("user_id", "?")
        name = user["name"]
        username = user.get("username")

        if username:
            link = f'<a href="https://t.me/{username}">{name}</a>'
        else:
            link = f'<a href="tg://user?id={user_id}">{name}</a> (нет username)'

        msg_time = user.get("first_msg_time")
        time_str = msg_time.strftime("%H:%M") if msg_time else "?"

        users_list.append(f"<b>├─</b> {link} — {time_str}")

    report = (
        "<b>┌─ 📋 КТО ЖДЁТ ОТВЕТА</b>\n"
        f"<b>├─ Всего:</b> {count}\n"
        f"<b>│</b>\n"
        + "\n".join(users_list[:20]) + ("\n<b>├─</b> ...и другие" if count > 20 else "") + "\n"
        "<b>│</b>\n"
        "<b>└─ 💡 Напиши !вернулся, чтобы очистить список</b>"
    )

    await message.reply(report, disable_web_page_preview=False)
    return True

async def cmd_owner_help(message: types.Message):
    await message.reply(get_owner_help_text())
    db.increment_commands()
    return True

async def cmd_stats(message: types.Message):
    full_stats = db.get_full_stats()

    uptime_seconds = full_stats.get("uptime_seconds", 0)
    hours = uptime_seconds // 3600
    minutes = (uptime_seconds % 3600) // 60

    top_users_text = ""
    for i, user in enumerate(full_stats.get("top_users", []), 1):
        top_users_text += f"<b>├─ {i}.</b> ID {user['user_id']}: {user['messages']} сообщений\n"

    top_commands_text = ""
    for cmd in full_stats.get("top_commands", []):
        top_commands_text += f"<b>├─</b> {cmd['command']}: {cmd['count']}\n"

    state_info = await state.get_stats()

    await message.reply(
        "<b>┌─ 📊 СТАТИСТИКА БОТА</b>\n"
        f"<b>├─ Сообщений:</b> {full_stats.get('total_messages', 0)}\n"
        f"<b>├─ Автоответов (всего):</b> {full_stats.get('auto_replies_sent', 0)}\n"
        f"<b>├─ Автоответов (текущая сессия):</b> {state_info['auto_replied_count']}\n"
        f"<b>├─ RP действий:</b> {full_stats.get('rp_actions_used', 0)}\n"
        f"<b>├─ Анекдотов:</b> {full_stats.get('jokes_sent', 0)}\n"
        f"<b>├─ Мемов:</b> {full_stats.get('memes_sent', 0)}\n"
        f"<b>├─ Команд:</b> {full_stats.get('commands_used', 0)}\n"
        f"<b>├─ Переключений режима:</b> {full_stats.get('away_mode_toggled', 0)}\n"
        f"<b>├─ Аптайм:</b> {int(hours)}ч {int(minutes)}мин\n"
        f"<b>├─ Уникальных собеседников:</b> {full_stats.get('users_count', 0)}\n"
        f"<b>│</b>\n"
        f"<b>├─ 🏆 Топ пользователей:</b>\n{top_users_text}"
        f"<b>│</b>\n"
        f"<b>├─ 📋 Популярные команды:</b>\n{top_commands_text}"
        f"<b>│</b>\n"
        f"<b>└─ 📍 Режим:</b> {'Отошёл' if await state.is_away_mode else 'Онлайн'}"
    )

    db.increment_commands()
    return True

async def cmd_reset_timers(message: types.Message):
    await state.reset_session()
    await message.reply("<b>┌─ ✅ Сброс</b>\n└─ Все таймеры и статусы автоответа сброшены!")
    db.increment_commands()
    return True

async def cmd_clear_status(message: types.Message):
    try:
        target_id = int(message.text.split()[1])
        await state.clear_user_status(target_id)
        await message.reply(f"<b>┌─ ✅ Очистка статуса</b>\n└─ Статус пользователя {target_id} очищен!")
    except (IndexError, ValueError):
        await message.reply("<b>┌─ ❌ Ошибка</b>\n└─ Используй: <code>!очистить_статус [user_id]</code>")
    db.increment_commands()
    return True

async def cmd_nsfw_stats(message: types.Message):
    from bot.utils.user_settings import user_settings_db

    stats = user_settings_db.get_stats()
    text = (
        "<b>┌─ 🔞 СТАТИСТИКА NSFW НАСТРОЕК</b>\n"
        f"<b>├─ 👥 Всего настроек:</b> {stats['total_users']}\n"
        f"<b>├─ 🔞 NSFW включено:</b> {stats['nsfw_enabled']}\n"
        f"<b>├─ ✅ NSFW выключено:</b> {stats['nsfw_disabled']}\n"
        "<b>└─ 📊 Пользователи сами выбирают режим</b>"
    )
    await message.reply(text)

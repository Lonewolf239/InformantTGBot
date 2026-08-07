from aiogram import types
from bot.state import state
from bot.stats import stats
from bot.utils.database import db
from bot.links.handlers import cmd_links, cmd_links_stats
from config import OWNER_COMMAND_METADATA
from functools import lru_cache
from bot.utils.helpers import its_me, get_raw_text, format_styled_message
from bot.owner_settings.handlers import cmd_system_settings
from bot.utils.registry import OWNER_COMMAND_HANDLERS, register_owner_command


OWNER_GROUP_LABELS = {
    "admin": "🛠 АДМИНИСТРИРОВАНИЕ",
    "twin": "🧬 ЦИФРОВОЙ ДВОЙНИК",
}


@lru_cache(maxsize=1)
def get_owner_help_text():
    sections = []
    for group_id, label in OWNER_GROUP_LABELS.items():
        lines = []
        for cmd, data in OWNER_COMMAND_METADATA.items():
            if data.get("group") != group_id:
                continue
            args = f" {data['args']}" if "args" in data else ""
            icon = data.get("icon", "🔹")
            lines.append(f"<b>{icon}</b> <code>{cmd}{args}</code> — {data['desc']}")
        if lines:
            sections.append(f"<b>{label}</b>\n" + "\n".join(lines))

    sections.append("Публичная справка: <code>!помощь</code>")

    return format_styled_message("👑", "КОМАНДЫ ВЛАДЕЛЬЦА", "\n\n".join(sections))


async def process_owner_commands(message: types.Message):
    if not its_me(message.from_user.id):
        return False

    raw_text = get_raw_text(message)
    if not raw_text:
        return False

    command_trigger = raw_text.split()[0]
    handler = OWNER_COMMAND_HANDLERS.get(command_trigger)
    if not handler:
        return False

    return await handler(message)


register_owner_command("!ссылки")(cmd_links)
register_owner_command("!линкстат")(cmd_links_stats)
register_owner_command("!система")(cmd_system_settings)


@register_owner_command("!отошёл")
async def cmd_away_on(message: types.Message):
    if not await state.is_away_mode:
        await state.set_away_mode(True)
        await message.reply(
            format_styled_message(
                "🚶‍♂️",
                "Режим «ОТОШЁЛ»",
                "Статус: Включён\n"
                "Действие: Автоответ приходит мгновенно, 1 раз на пользователя\n"
                "Выключение: <code>!вернулся</code>",
            )
        )
        await db.increment_away_toggled()
    else:
        await message.reply(
            format_styled_message(
                "⚠️",
                "Ошибка",
                "Режим «отошёл» уже включён! Чтобы выключить — напиши <code>!вернулся</code>",
            )
        )
    return True


@register_owner_command("!вернулся")
async def cmd_away_off(message: types.Message):
    if await state.is_away_mode:
        awaiting_users = await state.get_awaiting_users()
        awaiting_count = len(awaiting_users)

        await state.reset_session()
        await state.set_away_mode(False)

        body = (
            "Статус: Выключен\n"
            "Автоответчик: Отключён\n"
            f"👥 Ожидали ответа: {awaiting_count} человек\n"
        )

        if awaiting_count > 0:
            body += "\n📋 СПИСОК ОЖИДАВШИХ:\n"

            for user in awaiting_users:
                name = user["name"]
                username = user.get("username")

                if username:
                    link = f'<a href="https://t.me/{username}">{name}</a>'
                else:
                    link = f'<a href="tg://user?id={user.get("user_id")}">{name}</a>'

                msg_time = user.get("first_msg_time")
                time_str = msg_time.strftime("%H:%M") if msg_time else "?"
                body += f"{link} — {time_str}\n"

            body += "\n💡 Напиши им, когда будет время!"
        else:
            body += "💤 За время отсутствия никто не писал"

        await message.reply(
            format_styled_message("🏠", "Режим «ОТОШЁЛ» ВЫКЛЮЧЕН", body),
            disable_web_page_preview=True,
        )
        await db.increment_away_toggled()
    else:
        await message.reply(
            format_styled_message(
                "✅",
                "Информация",
                "Ты и так в режиме онлайн! Чтобы включить «отошёл» — напиши <code>!отошёл</code>",
            )
        )
    return True


@register_owner_command("!статус")
async def cmd_status(message: types.Message):
    state_info = await state.get_stats()
    status_text = (
        "🚶‍♂️ ОТОШЁЛ (автоответ включён)"
        if state_info["is_away"]
        else "🟢 ОНЛАЙН (автоответ выключен)"
    )
    total_auto_replies = await stats.auto_replies_sent

    await message.reply(
        format_styled_message(
            "📊",
            "Текущий статус",
            f"Режим: {status_text}\n"
            f"Получили автоответ: {state_info['auto_replied_count']}\n"
            f"Ожидают ответа: {state_info['awaiting_count']}\n"
            f"Всего автоответов за всё время: {total_auto_replies}",
        )
    )
    return True


@register_owner_command("!ждущие")
async def cmd_waiting(message: types.Message):
    if not await state.is_away_mode:
        await message.reply(
            format_styled_message(
                "ℹ️", "Инфо", "Режим «отошёл» не активен, список ожидающих пуст."
            )
        )
        return True

    awaiting_users = await state.get_awaiting_users()
    count = len(awaiting_users)

    if count == 0:
        await message.reply(
            format_styled_message("📭", "Пусто", "Пока никто не написал в твоё отсутствие.")
        )
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

        users_list.append(f"{link} — {time_str}")

    body = (
        f"Всего: {count}\n\n"
        + "\n".join(users_list[:20])
        + ("\n...и другие" if count > 20 else "")
        + "\n\n💡 Напиши !вернулся, чтобы очистить список"
    )

    await message.reply(
        format_styled_message("📋", "КТО ЖДЁТ ОТВЕТА", body), disable_web_page_preview=False
    )
    return True


@register_owner_command("!ownerhelp")
@register_owner_command("/help")
async def cmd_owner_help(message: types.Message):
    await message.reply(get_owner_help_text())
    await db.increment_commands()
    return True


@register_owner_command("!статистика")
async def cmd_stats(message: types.Message):
    full_stats = await db.get_full_stats()
    state_info = await state.get_stats()

    uptime_seconds = full_stats.get("uptime_seconds", 0)
    hours = uptime_seconds // 3600
    minutes = (uptime_seconds % 3600) // 60

    top_users_lines = []
    for index, user in enumerate(full_stats.get("top_users", []), 1):
        if user["username"] and not user["username"].startswith("user_"):
            name = f"@{user['username']}"
        else:
            name = f"<a href='{user['user_link']}'>{user['username']}</a>"

        top_users_lines.append(f"{index}. {name}: {user['messages']} сообщений")
    top_users_text = "\n".join(top_users_lines) or "(пока пусто)"

    top_commands_lines = [
        f"{cmd['command']}: {cmd['count']}" for cmd in full_stats.get("top_commands", [])
    ]
    top_commands_text = "\n".join(top_commands_lines) or "(пока пусто)"

    metrics = {
        "total_messages": full_stats.get("total_messages", 0),
        "auto_replies_total": full_stats.get("auto_replies_sent", 0),
        "auto_replies_session": state_info["auto_replied_count"],
        "rp_actions": full_stats.get("rp_actions_used", 0),
        "jokes": full_stats.get("jokes_sent", 0),
        "memes": full_stats.get("memes_sent", 0),
        "commands": full_stats.get("commands_used", 0),
        "away_toggles": full_stats.get("away_mode_toggled", 0),
        "users": full_stats.get("users_count", 0),
    }

    body = (
        f"Сообщений: {metrics['total_messages']}\n"
        f"Автоответов (всего): {metrics['auto_replies_total']}\n"
        f"Автоответов (текущая сессия): {metrics['auto_replies_session']}\n"
        f"RP действий: {metrics['rp_actions']}\n"
        f"Анекдотов: {metrics['jokes']}\n"
        f"Мемов: {metrics['memes']}\n"
        f"Команд: {metrics['commands']}\n"
        f"Переключений режима: {metrics['away_toggles']}\n"
        f"Аптайм: {hours}ч {minutes}мин\n"
        f"Уникальных собеседников: {metrics['users']}\n\n"
        f"🏆 Топ пользователей:\n{top_users_text}\n\n"
        f"📋 Популярные команды:\n{top_commands_text}\n\n"
        f"📍 Режим: {'Отошёл' if await state.is_away_mode else 'Онлайн'}"
    )

    await message.reply(format_styled_message("📊", "СТАТИСТИКА БОТА", body))
    await db.increment_commands()
    return True


@register_owner_command("!сброс_таймеров")
async def cmd_reset_timers(message: types.Message):
    await state.reset_session()
    await message.reply(
        format_styled_message("✅", "Сброс", "Все таймеры и статусы автоответа сброшены!")
    )
    await db.increment_commands()
    return True


@register_owner_command("!очистить_статус")
async def cmd_clear_status(message: types.Message):
    try:
        raw_text = get_raw_text(message)
        if not raw_text:
            return False

        text = raw_text
        target_id = int(text.split()[1])
        await state.clear_user_status(target_id)
        await message.reply(
            format_styled_message(
                "✅", "Очистка статуса", f"Статус пользователя {target_id} очищен!"
            )
        )
    except (IndexError, ValueError):
        await message.reply(
            format_styled_message(
                "❌", "Ошибка", "Используй: <code>!очистить_статус [user_id]</code>"
            )
        )
    await db.increment_commands()
    return True


@register_owner_command("!nsfw")
async def cmd_nsfw_stats(message: types.Message):
    from bot.utils.user_settings import user_settings_db

    nsfw_stats = await user_settings_db.get_stats()
    text = format_styled_message(
        "🔞",
        "СТАТИСТИКА NSFW НАСТРОЕК",
        f"👥 Всего настроек: {nsfw_stats['total_users']}\n"
        f"🔞 NSFW включено: {nsfw_stats['nsfw_enabled']}\n"
        f"✅ NSFW выключено: {nsfw_stats['nsfw_disabled']}\n"
        "📊 Пользователи сами выбирают режим",
    )
    await message.reply(text)
    return True

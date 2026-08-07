from aiogram import types
from bot.utils.helpers import its_me, get_raw_text, format_styled_message
from bot.utils.registry import register_command
from bot.twin.database import twin_db

RELATIONSHIP_PRESETS = {
    "близкий": 0.9,
    "приятель": 0.6,
    "знакомый": 0.4,
    "чужой": 0.1,
}


@register_command("!двойник_контакт")
async def cmd_twin_contact(message: types.Message):
    if not its_me(message.from_user.id):
        return False

    reply = message.reply_to_message
    if not reply or not reply.from_user:
        await message.reply(
            format_styled_message(
                "👥",
                "КОНТАКТ ДВОЙНИКА",
                "Ответь (reply) этой командой на сообщение человека, чей профиль "
                "хочешь посмотреть или изменить.",
            )
        )
        return True

    target = reply.from_user
    raw = get_raw_text(message) or ""
    parts = raw.split(maxsplit=1)
    relation = parts[1].strip() if len(parts) > 1 else ""

    if not relation:
        contact = await twin_db.get_contact(target.id)
        if not contact:
            await message.reply(
                format_styled_message(
                    "👥",
                    "КОНТАКТ ДВОЙНИКА",
                    f"Про {target.first_name} пока ничего не знаю. Чтобы задать тип: "
                    f"реплай на его сообщение + <code>!двойник_контакт "
                    f"{'|'.join(RELATIONSHIP_PRESETS)}</code>",
                )
            )
        else:
            await message.reply(
                format_styled_message(
                    "👥",
                    contact["display_name"] or "КОНТАКТ ДВОЙНИКА",
                    f"Тип отношений: {contact['relationship_type']}\n"
                    f"Близость: {contact['closeness']}\n"
                    f"Взаимодействий: {contact['interaction_count']}",
                )
            )
        return True

    if relation not in RELATIONSHIP_PRESETS:
        await message.reply(
            format_styled_message(
                "❌",
                "ОШИБКА",
                "Тип должен быть одним из: " + ", ".join(RELATIONSHIP_PRESETS),
            )
        )
        return True

    await twin_db.set_contact_relationship(
        target.id, target.first_name, relation, RELATIONSHIP_PRESETS[relation]
    )
    await message.reply(
        format_styled_message(
            "✅", "КОНТАКТ ОБНОВЛЁН", f"{target.first_name} теперь отмечен как «{relation}»."
        )
    )
    return True

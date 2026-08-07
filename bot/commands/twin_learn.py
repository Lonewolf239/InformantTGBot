from aiogram import types
from bot.utils.helpers import its_me
from bot.utils.registry import register_command
from bot.twin.onboarding import seed_personality_from_text, ingest_facts_text


def _resolve_reply_text(message: types.Message) -> tuple[str | None, str | None]:
    reply = message.reply_to_message

    if not reply:
        return None, "нужно ответить (reply) этой командой на сообщение владельца."

    if not reply.from_user or not its_me(reply.from_user.id):
        return (
            None,
            "эта команда работает только с сообщениями владельца — реплай был не на его сообщение.",
        )

    text = (reply.text or reply.caption or "").strip()
    if not text:
        return None, "в сообщении, на которое ты ответил, нет текста."

    return text, None


@register_command("!двойник_стиль")
async def cmd_twin_seed_style(message: types.Message):
    text, error = _resolve_reply_text(message)
    if error:
        await message.reply(f"❌ {error}")
        return True

    merged = await seed_personality_from_text(text)
    if not merged:
        await message.reply("❌ Не удалось разобрать ни одного профиля из текста.")
        return True

    preview = merged[:600] + ("…" if len(merged) > 600 else "")
    await message.reply(
        f"✅ Блок личности двойника обновлён:\n\n<code>{preview}</code>"
    )
    return True


@register_command("!двойник_факты")
async def cmd_twin_learn_facts(message: types.Message):
    text, error = _resolve_reply_text(message)
    if error:
        await message.reply(f"❌ {error}")
        return True

    facts = await ingest_facts_text(text)
    if not facts:
        await message.reply("Не нашёл в тексте новых фактов для базы знаний.")
        return True

    lines = "\n".join(f"• <b>{k}</b> ({c}): {v}" for k, c, v in facts)
    await message.reply(f"✅ В базу знаний добавлено фактов: {len(facts)}\n\n{lines}")
    return True

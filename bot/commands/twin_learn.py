from aiogram import types
from config import AI_PROVIDER
from bot.utils.helpers import its_me, get_raw_text, format_styled_message
from bot.utils.registry import register_command
from bot.utils.queue_wrapper import process_with_queue
from bot.twin.database import twin_db
from bot.twin.onboarding import seed_personality_from_text, ingest_facts_text

MANUAL_BLOCKS = {"identity_core", "negative_rules"}
VISIBILITY_LEVELS = {"public", "friends", "private"}
VERSIONED_BLOCKS = MANUAL_BLOCKS | {"speech_style"}
QUEUE_NAME = "lightweights" if AI_PROVIDER == "groq" else "heavyweights"


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
        await message.reply(format_styled_message("❌", "ДВОЙНИК: СТИЛЬ", error))
        return True

    merged, wait_msg = await process_with_queue(
        message=message,
        queue_name=QUEUE_NAME,
        icon="🧬",
        title="Двойник: стиль",
        action_text="Разбор стиля и обновление личности",
        func=seed_personality_from_text,
        text=text,
    )
    if merged is None:
        return True
    if not merged:
        await wait_msg.edit_text(
            format_styled_message(
                "❌", "ДВОЙНИК: СТИЛЬ", "Не удалось разобрать ни одного профиля из текста."
            )
        )
        return True

    preview = merged[:600] + ("…" if len(merged) > 600 else "")
    await wait_msg.edit_text(
        format_styled_message(
            "✅", "ДВОЙНИК: СТИЛЬ", f"Блок личности двойника обновлён:\n\n<code>{preview}</code>"
        )
    )
    return True


@register_command("!двойник_факты")
async def cmd_twin_learn_facts(message: types.Message):
    text, error = _resolve_reply_text(message)
    if error:
        await message.reply(format_styled_message("❌", "ДВОЙНИК: ФАКТЫ", error))
        return True

    facts, wait_msg = await process_with_queue(
        message=message,
        queue_name=QUEUE_NAME,
        icon="🧬",
        title="Двойник: факты",
        action_text="Извлечение фактов",
        func=ingest_facts_text,
        raw_text=text,
    )
    if facts is None:
        return True
    if not facts:
        await wait_msg.edit_text(
            format_styled_message(
                "ℹ️", "ДВОЙНИК: ФАКТЫ", "Не нашёл в тексте новых фактов для базы знаний."
            )
        )
        return True

    lines = "\n".join(f"• <b>{k}</b> ({c}): {v}" for k, c, v in facts)
    await wait_msg.edit_text(
        format_styled_message(
            "✅", "ДВОЙНИК: ФАКТЫ", f"В базу знаний добавлено фактов: {len(facts)}\n\n{lines}"
        )
    )
    return True


@register_command("!двойник_блок")
async def cmd_twin_set_block(message: types.Message):
    if not its_me(message.from_user.id):
        return False

    raw = get_raw_text(message, normalize=False) or ""
    parts = raw.split(maxsplit=1)
    block_name = parts[1].strip() if len(parts) > 1 else ""

    if block_name not in MANUAL_BLOCKS:
        await message.reply(
            format_styled_message(
                "🧩",
                "ДВОЙНИК: БЛОК",
                "Формат: реплаем на текст блока напиши <code>!двойник_блок "
                f"{'|'.join(MANUAL_BLOCKS)}</code>.",
            )
        )
        return True

    text, error = _resolve_reply_text(message)
    if error:
        await message.reply(format_styled_message("❌", "ДВОЙНИК: БЛОК", error))
        return True

    await twin_db.upsert_prompt_block(block_name, text)
    preview = text[:600] + ("…" if len(text) > 600 else "")
    await message.reply(
        format_styled_message(
            "✅", "ДВОЙНИК: БЛОК", f"Блок '{block_name}' обновлён:\n\n<code>{preview}</code>"
        )
    )
    return True


@register_command("!двойник_видимость")
async def cmd_twin_set_visibility(message: types.Message):
    if not its_me(message.from_user.id):
        return False

    raw = get_raw_text(message, normalize=False) or ""
    parts = raw.split()

    if len(parts) != 3 or parts[2].lower() not in VISIBILITY_LEVELS:
        await message.reply(
            format_styled_message(
                "🔒",
                "ДВОЙНИК: ВИДИМОСТЬ",
                "Формат: <code>!двойник_видимость ключ_факта "
                f"{'|'.join(VISIBILITY_LEVELS)}</code>\n"
                "public — видно всем, friends — только близким/приятелям, "
                "private — только тебе.",
            )
        )
        return True

    key, visibility = parts[1], parts[2].lower()
    updated = await twin_db.set_knowledge_visibility(key, visibility)
    if updated:
        await message.reply(
            format_styled_message(
                "✅", "ДВОЙНИК: ВИДИМОСТЬ", f"Видимость факта '{key}' → {visibility}."
            )
        )
    else:
        await message.reply(
            format_styled_message(
                "❌", "ДВОЙНИК: ВИДИМОСТЬ", f"Факт с ключом '{key}' не найден."
            )
        )
    return True


@register_command("!двойник_версии")
async def cmd_twin_block_versions(message: types.Message):
    if not its_me(message.from_user.id):
        return False

    raw = get_raw_text(message, normalize=False) or ""
    parts = raw.split()
    block_name = parts[1] if len(parts) > 1 else ""

    if block_name not in VERSIONED_BLOCKS:
        await message.reply(
            format_styled_message(
                "🕰", "ДВОЙНИК: ВЕРСИИ", f"Формат: <code>!двойник_версии {'|'.join(VERSIONED_BLOCKS)}</code>"
            )
        )
        return True

    history = await twin_db.get_prompt_block_history(block_name)
    if not history:
        await message.reply(
            format_styled_message(
                "ℹ️", "ДВОЙНИК: ВЕРСИИ", f"У блока '{block_name}' пока нет прошлых версий."
            )
        )
        return True

    lines = []
    for h in history:
        preview = h["content"][:100] + ("…" if len(h["content"]) > 100 else "")
        lines.append(
            f"<b>#{h['id']}</b> (v{h['version']}, {h['created_at'][:16]}): {preview}"
        )

    await message.reply(
        format_styled_message(
            "🕰",
            f"ВЕРСИИ БЛОКА '{block_name}'",
            "\n".join(lines) + f"\n\nОткатить: <code>!двойник_откат {block_name} [id]</code>",
        )
    )
    return True


@register_command("!двойник_откат")
async def cmd_twin_rollback_block(message: types.Message):
    if not its_me(message.from_user.id):
        return False

    raw = get_raw_text(message, normalize=False) or ""
    parts = raw.split()

    if len(parts) != 3 or parts[1] not in VERSIONED_BLOCKS:
        await message.reply(
            format_styled_message(
                "⏪",
                "ДВОЙНИК: ОТКАТ",
                f"Формат: <code>!двойник_откат {'|'.join(VERSIONED_BLOCKS)} "
                "[id из !двойник_версии]</code>",
            )
        )
        return True

    block_name = parts[1]
    try:
        history_id = int(parts[2])
    except ValueError:
        await message.reply(
            format_styled_message("❌", "ДВОЙНИК: ОТКАТ", "Id версии должен быть числом.")
        )
        return True

    ok = await twin_db.rollback_prompt_block(block_name, history_id)
    if ok:
        await message.reply(
            format_styled_message(
                "✅",
                "ДВОЙНИК: ОТКАТ",
                f"Блок '{block_name}' откачен к версии #{history_id}. "
                "Это действие тоже обратимо через !двойник_версии.",
            )
        )
    else:
        await message.reply(
            format_styled_message(
                "❌", "ДВОЙНИК: ОТКАТ", f"Версия #{history_id} для блока '{block_name}' не найдена."
            )
        )
    return True

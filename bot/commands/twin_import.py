import io
from aiogram import types
from bot.utils.helpers import its_me, format_styled_message
from bot.utils.registry import register_command
from bot.twin.importer import import_telegram_export

MAX_IMPORT_FILE_MB = 19


@register_command("!двойник_импорт")
async def cmd_twin_import(message: types.Message):
    if not its_me(message.from_user.id):
        return False

    target = message if message.document else message.reply_to_message
    if not target or not target.document:
        await message.reply(
            format_styled_message(
                "📥",
                "ИМПОРТ ИСТОРИИ",
                "Прикрепи JSON-файл экспорта чата Telegram (result.json) с подписью "
                "<code>!двойник_импорт</code>, либо ответь этой командой на уже "
                "отправленный файл.",
            )
        )
        return True

    doc = target.document
    if doc.file_size and doc.file_size > MAX_IMPORT_FILE_MB * 1024 * 1024:
        await message.reply(
            format_styled_message(
                "❌",
                "ОШИБКА",
                f"Файл слишком большой (лимит Telegram Bot API — {MAX_IMPORT_FILE_MB} МБ).",
            )
        )
        return True

    wait = await message.reply(
        format_styled_message(
            "📥", "ИМПОРТ ИСТОРИИ", "Импортирую историю переписки, это может занять время..."
        )
    )

    try:
        buf = io.BytesIO()
        await message.bot.download(doc, destination=buf)
        raw_bytes = buf.getvalue()
    except Exception as e:
        await wait.edit_text(
            format_styled_message("❌", "ОШИБКА", f"Не удалось скачать файл: {e}")
        )
        return True

    result = await import_telegram_export(raw_bytes)
    if "error" in result:
        await wait.edit_text(format_styled_message("❌", "ОШИБКА", result["error"]))
        return True

    await wait.edit_text(
        format_styled_message(
            "📥",
            "ИМПОРТ ЗАВЕРШЁН",
            f"Всего сообщений в файле: {result['total_messages']}\n"
            f"Найдено твоих сообщений: {result['owner_messages_found']}\n"
            f"Сохранено сэмплов (после склейки серий): {result['stored_samples']}\n"
            f"Диалоговых пар записано: {result['dialogue_pairs']}",
        )
    )
    return True

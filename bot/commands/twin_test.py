from aiogram import types
from config import AI_PROVIDER
from bot.utils.helpers import its_me, format_styled_message
from bot.utils.registry import register_command
from bot.utils.queue_wrapper import process_with_queue
from bot.twin.testset import run_test_set

QUEUE_NAME = "lightweights" if AI_PROVIDER == "groq" else "heavyweights"


@register_command("!двойник_тест")
async def cmd_twin_test(message: types.Message):
    if not its_me(message.from_user.id):
        return False

    results, wait_msg = await process_with_queue(
        message=message,
        queue_name=QUEUE_NAME,
        icon="🧪",
        title="Контрольные сценарии двойника",
        action_text="Прогон контрольных сценариев",
        func=run_test_set,
    )
    if results is None:
        return True

    passed = sum(1 for r in results if r["passed"])
    total = len(results)

    lines = [f"<b>Пройдено:</b> {passed}/{total}"]
    for r in results:
        icon = "✅" if r["passed"] else "❌"
        answer_preview = (r["answer"] or "(нет ответа)")[:150]
        lines.append(f"\n{icon} <b>{r['situation']}</b>")
        lines.append(f"<i>«{r['prompt']}»</i>")
        lines.append(f"→ {answer_preview}")
        if r["flags"]:
            lines.append(f"⚠️ Подозрительные паттерны: {', '.join(r['flags'])}")

    text = format_styled_message(
        "🧪", "КОНТРОЛЬНЫЕ СЦЕНАРИИ ДВОЙНИКА", "\n".join(lines)
    )

    try:
        await wait_msg.edit_text(text)
    except Exception:
        for i in range(0, len(text), 3500):
            await message.reply(text[i : i + 3500])
    return True

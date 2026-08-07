from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from bot.twin.database import twin_db
from bot.twin.pipeline import get_status
from bot.twin.interview import _category_coverage, CATEGORY_HINTS, get_interview_stats
from bot.twin.metrics import estimate_similarity
from bot.utils.helpers import create_user_keyboard, format_styled_message
from config import OWNER_ID

COMPONENT_LABELS = {
    "feedback": "Обратная связь",
    "test_set": "Контрольные сценарии",
    "data_volume": "Объём данных",
    "fact_confidence": "Уверенность в фактах",
}


def _fmt_percent(value: float | None) -> str:
    return f"{value * 100:.0f}%" if value is not None else "—"


def _similarity_bar(value: float | None, length: int = 10) -> str:
    if value is None:
        return "░" * length
    filled = round(value * length)
    return "█" * filled + "░" * (length - filled)

BLOCK_LABELS = {
    "identity_core": "🧠 Ядро идентичности",
    "speech_style": "🗣 Речевой стиль",
    "negative_rules": "🚫 Отрицательные правила",
}

RELATIONSHIP_ICONS = {
    "близкий": "💚",
    "приятель": "🙂",
    "знакомый": "😐",
    "чужой": "❄️",
    "unknown": "❓",
}


def _kb(rows: list, back_to: str | None = None) -> InlineKeyboardMarkup:
    buttons = list(rows)
    if back_to:
        buttons.append([InlineKeyboardButton(text="🔙 Назад", callback_data=back_to)])
    return create_user_keyboard(buttons, OWNER_ID)


async def build_main_view():
    status = await get_status()
    similarity = await estimate_similarity()
    overall = similarity["overall"]

    text = format_styled_message(
        "🧬",
        "МЕНЮ ЦИФРОВОГО ДВОЙНИКА",
        f"Похожесть (оценочно): <b>{_fmt_percent(overall)}</b> "
        f"{_similarity_bar(overall)}\n"
        f"Необработанных сэмплов в очереди: {status['pool_size']}\n"
        f"Диалоговых примеров: {status['dialogue_examples_count']}\n"
        f"Фактов в базе знаний: {status['knowledge_count']}\n"
        f"Последний цикл обучения: {status['last_cycle_run']}\n\n"
        "<i>Похожесть — грубая эвристика по накопленным данным, а не "
        "измерение. Подробный расклад: кнопка «Статус».</i>",
    )
    rows = [
        [InlineKeyboardButton(text="📊 Статус", callback_data="twin_menu:status")],
        [InlineKeyboardButton(text="🧠 Личность", callback_data="twin_menu:personality")],
        [InlineKeyboardButton(text="📚 Знания", callback_data="twin_menu:knowledge")],
        [InlineKeyboardButton(text="🗣 Интервью", callback_data="twin_menu:interview")],
        [InlineKeyboardButton(text="👥 Контакты", callback_data="twin_menu:contacts")],
        [InlineKeyboardButton(text="📝 Обратная связь", callback_data="twin_menu:feedback")],
        [InlineKeyboardButton(text="🕰 Версии блоков", callback_data="twin_menu:versions")],
    ]
    return text, _kb(rows)


async def build_status_view():
    status = await get_status()
    feedback_stats = await twin_db.get_feedback_stats()
    processed_samples = await twin_db.get_processed_samples_count()
    contacts_count = await twin_db.get_contacts_count()
    blocks_meta = await twin_db.get_prompt_blocks_meta()
    interview_stats = await get_interview_stats()
    similarity = await estimate_similarity()

    blocks_lines = (
        "\n".join(
            f"  • {b['block_name']}: v{b['version']}, {b['content_len']} симв., "
            f"обновлён {b['updated_at'][:16]}"
            for b in blocks_meta
        )
        or "  (пока пусто)"
    )

    component_lines = []
    for key, label in COMPONENT_LABELS.items():
        comp = similarity["components"].get(key)
        if not comp:
            component_lines.append(f"  • {label}: нет данных")
            continue
        component_lines.append(
            f"  • {label}: {_fmt_percent(comp['score'])} "
            f"(вес {comp['weight'] * 100:.0f}%)"
        )

    text = format_styled_message(
        "📊",
        "ПОЛНАЯ СТАТИСТИКА ДВОЙНИКА",
        f"<b>Похожесть (оценочно): {_fmt_percent(similarity['overall'])}</b>\n"
        + "\n".join(component_lines)
        + "\n\n<b>Данные для обучения</b>\n"
        f"  • Необработанных сэмплов в очереди: {status['pool_size']}\n"
        f"  • Обработано сэмплов за всё время: {processed_samples}\n"
        f"  • Диалоговых примеров: {status['dialogue_examples_count']}\n"
        f"  • Фактов в базе знаний: {status['knowledge_count']}\n"
        f"  • Контактов: {contacts_count}\n"
        f"  • Последний цикл обучения: {status['last_cycle_run']}\n"
        "\n<b>Блоки промпта</b>\n"
        f"{blocks_lines}\n"
        "\n<b>Интервью</b>\n"
        f"  • Завершённых сессий: {interview_stats['completed_sessions']}\n"
        f"  • Отвечено вопросов всего: {interview_stats['total_answers']}\n"
        "\n<b>Обратная связь</b>\n"
        f"  • ✅ это я: {feedback_stats['good']}  🟡 мог бы: {feedback_stats['maybe']}  "
        f"❌ не я: {feedback_stats['bad']}  ⌛ без оценки: {feedback_stats['pending']}",
    )
    return text, _kb([], back_to="twin_menu:main")


async def build_personality_view():
    blocks = await twin_db.get_all_prompt_blocks()
    parts = []
    for name, label in BLOCK_LABELS.items():
        content = blocks.get(name)
        preview = (
            content[:250] + ("…" if len(content) > 250 else "")
            if content
            else "(не задано)"
        )
        parts.append(f"<b>{label}</b>\n{preview}")

    text = format_styled_message(
        "🧠",
        "ЛИЧНОСТЬ ДВОЙНИКА",
        "\n\n".join(parts)
        + "\n\nИзменить: <code>!двойник_блок</code> / <code>!двойник_стиль</code> "
        "(реплаем на текст)",
    )
    return text, _kb([], back_to="twin_menu:main")


async def build_knowledge_view():
    summary = await twin_db.get_knowledge_summary()
    vis = summary["by_visibility"]

    lines = [
        f"Public: {vis['public']} | Friends: {vis['friends']} | Private: {vis['private']}",
        "",
        "<b>Топ фактов по подтверждениям:</b>",
    ]
    for fact in summary["top_facts"]:
        lines.append(
            f"• <b>{fact['key']}</b> ({fact['evidence_count']}x): {fact['value']}"
        )
    if not summary["top_facts"]:
        lines.append("(пока пусто)")

    text = format_styled_message("📚", "БАЗА ЗНАНИЙ ДВОЙНИКА", "\n".join(lines))
    return text, _kb([], back_to="twin_menu:main")


async def build_interview_view():
    coverage = await _category_coverage()
    lines = []
    for cat, hint in CATEGORY_HINTS.items():
        stat = coverage.get(cat)
        if stat:
            lines.append(
                f"<b>{cat}</b>: отвечено {stat['answered']}/{stat['asked']}, "
                f"последний раз {stat['last_asked_at'][:10]}"
            )
        else:
            lines.append(f"<b>{cat}</b>: ещё не спрашивали")

    text = format_styled_message(
        "🗣",
        "ИНТЕРВЬЮ — ПОКРЫТИЕ КАТЕГОРИЙ",
        "\n".join(lines)
        + "\n\nНачать: <code>!двойник_вопросы</code> или <code>!двойник_подряд</code>",
    )
    return text, _kb([], back_to="twin_menu:main")


async def build_contacts_view():
    contacts = await twin_db.get_all_contacts()
    if not contacts:
        lines = ["Пока никого нет."]
    else:
        lines = []
        for c in contacts:
            icon = RELATIONSHIP_ICONS.get(c["relationship_type"], "❓")
            name = c["display_name"] or str(c["user_id"])
            lines.append(
                f"{icon} <b>{name}</b> — {c['relationship_type']}, "
                f"близость {c['closeness']:.1f}, взаимодействий {c['interaction_count']}"
            )

    text = format_styled_message(
        "👥",
        "КОНТАКТЫ ДВОЙНИКА",
        "\n".join(lines)
        + "\n\nИзменить тип: реплай на сообщение человека + "
        "<code>!двойник_контакт близкий|приятель|знакомый|чужой</code>",
    )
    return text, _kb([], back_to="twin_menu:main")


async def build_feedback_view():
    stats = await twin_db.get_feedback_stats()
    total_rated = stats["good"] + stats["maybe"] + stats["bad"]
    accuracy = f"{(stats['good'] / total_rated * 100):.0f}%" if total_rated else "—"

    text = format_styled_message(
        "📝",
        "ОБРАТНАЯ СВЯЗЬ ПО ОТВЕТАМ",
        f"✅ Это я: {stats['good']}\n"
        f"🟡 Мог бы так ответить: {stats['maybe']}\n"
        f"❌ Не похоже на меня: {stats['bad']}\n"
        f"⌛ Без оценки: {stats['pending']}\n\n"
        f"Точность («это я» из оценённых): {accuracy}",
    )
    return text, _kb([], back_to="twin_menu:main")


async def build_versions_picker_view():
    rows = [
        [InlineKeyboardButton(text=label, callback_data=f"twin_menu:versions:{name}")]
        for name, label in BLOCK_LABELS.items()
    ]
    text = format_styled_message("🕰", "ВЕРСИИ БЛОКОВ", "Выбери блок для просмотра истории:")
    return text, _kb(rows, back_to="twin_menu:main")


async def build_block_versions_view(block_name: str):
    label = BLOCK_LABELS.get(block_name, block_name)
    history = await twin_db.get_prompt_block_history(block_name, limit=5)

    if not history:
        text = format_styled_message("🕰", label, "Прошлых версий пока нет.")
        return text, _kb([], back_to="twin_menu:versions")

    lines = []
    rows = []
    for h in history:
        preview = h["content"][:80] + ("…" if len(h["content"]) > 80 else "")
        lines.append(f"<b>#{h['id']}</b> (v{h['version']}, {h['created_at'][:16]}): {preview}")
        rows.append(
            [
                InlineKeyboardButton(
                    text=f"⏪ Откатить к #{h['id']}",
                    callback_data=f"twin_menu:rollback:{block_name}:{h['id']}",
                )
            ]
        )

    text = format_styled_message("🕰", label, "\n".join(lines))
    return text, _kb(rows, back_to="twin_menu:versions")


async def handle_menu_callback(callback_query, data: str) -> None:
    parts = data.split(":")
    action = parts[1] if len(parts) > 1 else "main"
    answered = False

    if action == "rollback" and len(parts) >= 4:
        block_name, history_id_str = parts[2], parts[3]
        try:
            ok = await twin_db.rollback_prompt_block(block_name, int(history_id_str))
        except ValueError:
            ok = False
        await callback_query.answer(
            "✅ Откачено" if ok else "❌ Не удалось откатить", show_alert=not ok
        )
        answered = True
        text, keyboard = await build_block_versions_view(block_name)
    elif action == "versions" and len(parts) >= 3:
        text, keyboard = await build_block_versions_view(parts[2])
    elif action == "status":
        text, keyboard = await build_status_view()
    elif action == "personality":
        text, keyboard = await build_personality_view()
    elif action == "knowledge":
        text, keyboard = await build_knowledge_view()
    elif action == "interview":
        text, keyboard = await build_interview_view()
    elif action == "contacts":
        text, keyboard = await build_contacts_view()
    elif action == "feedback":
        text, keyboard = await build_feedback_view()
    elif action == "versions":
        text, keyboard = await build_versions_picker_view()
    else:
        text, keyboard = await build_main_view()

    try:
        await callback_query.message.edit_text(text, reply_markup=keyboard)
    except Exception:
        pass

    if not answered:
        await callback_query.answer()

import re
import json
import logging
from datetime import datetime, timezone

import aiosqlite

from config import AI_PROVIDER
from bot.twin.database import twin_db, DB_PATH
from bot.twin.onboarding import ingest_facts_text
from bot.utils.ai_core import ask_ai
from bot.utils.helpers import its_me, format_styled_message
from bot.utils.queue_wrapper import process_with_queue

logger = logging.getLogger(__name__)

QUESTIONS_MIN = 5
QUESTIONS_MAX = 10
STALE_RECHECK_DAYS = 21
QUEUE_NAME = "lightweights" if AI_PROVIDER == "groq" else "heavyweights"
COVERAGE_SESSIONS_SCANNED = 30

CATEGORY_HINTS = {
    "scenario_reaction": "конкретная ситуация с репликой собеседника, на которую нужно ответить",
    "conflict_reaction": "реакция на обесценивание, критику, непонимание, провокацию",
    "values": "ценности, моральные позиции, что непростительно, когда нарушить правило",
    "preferences": "вкусы в музыке/играх/интерфейсах, что нравится и раздражает",
    "humor": "как реагирует на пафос, плохие шутки, как продолжает чужую шутку",
    "relationships": "чем общение с близкими отличается от общения с незнакомыми",
    "self_perception": "что двойник поймёт о нём неправильно, какую черту переоценивают",
    "autobiography": "важные события, старые поступки, значимые проекты",
    "current_state": "что занимает мысли сейчас, что изменилось за последние дни",
}

GENERATOR_SYSTEM = (
    "Ты помогаешь обучать цифрового двойника человека. Сгенерируй {n} "
    "вопросов К ЭТОМУ человеку, чтобы лучше понять его личность, реакции "
    "и ценности. Требования:\n"
    "- вопросы НЕ наводящие: не подсказывай ожидаемый ответ, не описывай "
    "заранее, какой он ('ты ведь обычно...') — спрашивай открыто;\n"
    "- приоритет отдавай СЦЕНАРНЫМ вопросам вида 'кто-то написал X, что "
    "ответишь?' — они учат реакции, а не самоописанию;\n"
    "- покрой разные категории из списка ниже, не более 1-2 на категорию;\n"
    "- вопросы короткие, живые, на 'ты';\n"
    "- для категорий с пометкой [ПОВТОРНАЯ ПРОВЕРКА] не повторяй старую "
    "формулировку дословно — придумай другой сценарий на ту же тему, чтобы "
    "проверить, не изменился ли ответ.\n"
    "Категории (охват): {categories}\n\n"
    "{avoid_block}"
    "Ответь СТРОГО в виде JSON-массива, без пояснений и markdown:\n"
    '[{{"question": "...", "category": "scenario_reaction"}}, ...]'
)


async def init_interview_db() -> None:
    async with aiosqlite.connect(DB_PATH) as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS twin_interview_sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                owner_id INTEGER NOT NULL,
                status TEXT NOT NULL DEFAULT 'active',
                questions_json TEXT NOT NULL,
                answers_json TEXT,
                mode TEXT NOT NULL DEFAULT 'batch',
                current_index INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                completed_at TEXT
            )
            """)
        existing_columns = {
            row[1]
            for row in await (
                await conn.execute("PRAGMA table_info(twin_interview_sessions)")
            ).fetchall()
        }
        if "mode" not in existing_columns:
            await conn.execute(
                "ALTER TABLE twin_interview_sessions ADD COLUMN mode "
                "TEXT NOT NULL DEFAULT 'batch'"
            )
        if "current_index" not in existing_columns:
            await conn.execute(
                "ALTER TABLE twin_interview_sessions ADD COLUMN current_index "
                "INTEGER NOT NULL DEFAULT 0"
            )
        await conn.commit()
    logger.info("🧬 Twin interview DB инициализирована")


async def get_interview_stats() -> dict:
    async with aiosqlite.connect(DB_PATH) as conn:
        cursor = await conn.execute(
            "SELECT answers_json FROM twin_interview_sessions WHERE status = 'completed'"
        )
        rows = await cursor.fetchall()

    total_answers = 0
    for (answers_json,) in rows:
        if not answers_json:
            continue
        try:
            total_answers += len(json.loads(answers_json))
        except Exception:
            pass

    return {"completed_sessions": len(rows), "total_answers": total_answers}


async def _has_active_session(owner_id: int) -> int | None:
    async with aiosqlite.connect(DB_PATH) as conn:
        cursor = await conn.execute(
            "SELECT id FROM twin_interview_sessions "
            "WHERE owner_id = ? AND status = 'active' ORDER BY id DESC LIMIT 1",
            (owner_id,),
        )
        row = await cursor.fetchone()
        return row[0] if row else None


async def _get_active_session_full(owner_id: int) -> dict | None:
    async with aiosqlite.connect(DB_PATH) as conn:
        conn.row_factory = aiosqlite.Row
        cursor = await conn.execute(
            "SELECT id, mode, current_index, questions_json, answers_json "
            "FROM twin_interview_sessions "
            "WHERE owner_id = ? AND status = 'active' ORDER BY id DESC LIMIT 1",
            (owner_id,),
        )
        row = await cursor.fetchone()
        return dict(row) if row else None


async def _category_coverage() -> dict[str, dict]:
    async with aiosqlite.connect(DB_PATH) as conn:
        cursor = await conn.execute(
            "SELECT questions_json, answers_json, created_at "
            "FROM twin_interview_sessions WHERE status != 'active' "
            "ORDER BY id DESC LIMIT ?",
            (COVERAGE_SESSIONS_SCANNED,),
        )
        rows = await cursor.fetchall()

    coverage: dict[str, dict] = {}
    for questions_json, answers_json, created_at in rows:
        try:
            questions = json.loads(questions_json)
        except Exception:
            questions = []
        try:
            answers = json.loads(answers_json) if answers_json else {}
        except Exception:
            answers = {}

        for idx, q in enumerate(questions, 1):
            category = q.get("category", "scenario_reaction")
            stat = coverage.setdefault(
                category, {"asked": 0, "answered": 0, "last_asked_at": None}
            )
            stat["asked"] += 1
            if str(idx) in answers:
                stat["answered"] += 1
            if not stat["last_asked_at"] or created_at > stat["last_asked_at"]:
                stat["last_asked_at"] = created_at

    return coverage


async def _recent_question_texts(limit: int = 30) -> list[str]:
    async with aiosqlite.connect(DB_PATH) as conn:
        cursor = await conn.execute(
            "SELECT questions_json FROM twin_interview_sessions "
            "WHERE status != 'active' ORDER BY id DESC LIMIT 5"
        )
        rows = await cursor.fetchall()

    texts: list[str] = []
    for (questions_json,) in rows:
        try:
            questions = json.loads(questions_json)
        except Exception:
            continue
        texts.extend(q.get("question", "") for q in questions if q.get("question"))

    return texts[:limit]


def _select_categories(coverage: dict[str, dict], count: int) -> tuple[list[str], list[str]]:
    all_categories = list(CATEGORY_HINTS.keys())

    def _score(cat: str) -> tuple[int, str]:
        stat = coverage.get(cat)
        if not stat:
            return (0, "")
        return (stat["answered"], stat["last_asked_at"] or "")

    weak = sorted(all_categories, key=_score)[: min(len(all_categories), count + 2)]

    recheck = []
    now = datetime.now(timezone.utc)
    for cat, stat in coverage.items():
        if cat in weak or stat["answered"] < 2 or not stat["last_asked_at"]:
            continue
        try:
            last = datetime.fromisoformat(stat["last_asked_at"])
        except ValueError:
            continue
        if (now - last).days >= STALE_RECHECK_DAYS:
            recheck.append(cat)

    return weak, recheck[:2]


def _safe_json_array(raw: str) -> list[dict]:
    if not raw:
        return []
    cleaned = re.sub(r"```(json)?", "", raw).strip()
    try:
        data = json.loads(cleaned)
    except Exception:
        match = re.search(r"\[.*\]", cleaned, re.DOTALL)
        if not match:
            logger.warning(
                "Twin interview: не удалось распарсить вопросы: %s", raw[:300]
            )
            return []
        try:
            data = json.loads(match.group(0))
        except Exception:
            return []
    if not isinstance(data, list):
        return []
    out = []
    for item in data:
        if isinstance(item, dict) and item.get("question"):
            out.append(
                {
                    "question": str(item["question"]).strip(),
                    "category": str(item.get("category", "scenario_reaction")),
                }
            )
    return out


async def generate_questions(count: int = 7) -> list[dict]:
    count = max(QUESTIONS_MIN, min(QUESTIONS_MAX, count))

    coverage = await _category_coverage()
    weak, recheck = _select_categories(coverage, count)

    category_parts = [f"{cat} ({CATEGORY_HINTS[cat]})" for cat in weak]
    category_parts += [f"{cat} [ПОВТОРНАЯ ПРОВЕРКА] ({CATEGORY_HINTS[cat]})" for cat in recheck]
    categories = ", ".join(category_parts)

    recent_questions = await _recent_question_texts()
    avoid_block = ""
    if recent_questions:
        avoid_block = (
            "Не повторяй эти уже заданные вопросы:\n"
            + "\n".join(f"- {q}" for q in recent_questions)
            + "\n\n"
        )

    system = GENERATOR_SYSTEM.format(n=count, categories=categories, avoid_block=avoid_block)
    raw = await ask_ai(
        user_prompt="Сгенерируй вопросы согласно инструкции.",
        system_prompt=system,
        temperature=0.8,
        max_tokens=700,
    )
    questions = _safe_json_array(raw or "")
    return questions[:count]


async def start_session(
    owner_id: int, count: int = 7
) -> tuple[list[dict] | None, str | None]:
    active = await _has_active_session(owner_id)
    if active is not None:
        return None, "already_active"

    questions = await generate_questions(count)
    if not questions:
        return None, "generation_failed"

    async with aiosqlite.connect(DB_PATH) as conn:
        await conn.execute(
            """
            INSERT INTO twin_interview_sessions
                (owner_id, status, questions_json, created_at)
            VALUES (?, 'active', ?, ?)
            """,
            (
                owner_id,
                json.dumps(questions, ensure_ascii=False),
                datetime.now(timezone.utc).isoformat(),
            ),
        )
        await conn.commit()

    return questions, None


async def start_sequential_session(
    owner_id: int, count: int = 7
) -> tuple[list[dict] | None, str | None]:
    active = await _has_active_session(owner_id)
    if active is not None:
        return None, "already_active"

    questions = await generate_questions(count)
    if not questions:
        return None, "generation_failed"

    async with aiosqlite.connect(DB_PATH) as conn:
        await conn.execute(
            """
            INSERT INTO twin_interview_sessions
                (owner_id, status, questions_json, mode, current_index, created_at)
            VALUES (?, 'active', ?, 'sequential', 0, ?)
            """,
            (
                owner_id,
                json.dumps(questions, ensure_ascii=False),
                datetime.now(timezone.utc).isoformat(),
            ),
        )
        await conn.commit()

    return questions, None


def _parse_numbered_answers(text: str) -> dict[int, str]:
    answers: dict[int, str] = {}
    current: int | None = None
    for line in text.splitlines():
        m = re.match(r"^\s*(\d{1,2})[\.\)]\s*(.*)$", line)
        if m:
            current = int(m.group(1))
            answers[current] = m.group(2).strip()
        elif current is not None and line.strip():
            answers[current] = (answers[current] + " " + line.strip()).strip()
    return {k: v for k, v in answers.items() if v}


async def submit_answers(owner_id: int, raw_text: str) -> tuple[int, str | None]:
    session_id = await _has_active_session(owner_id)
    if session_id is None:
        return 0, "no_active_session"

    parsed = _parse_numbered_answers(raw_text)
    if not parsed:
        return 0, "unparsable"

    async with aiosqlite.connect(DB_PATH) as conn:
        cursor = await conn.execute(
            "SELECT questions_json FROM twin_interview_sessions WHERE id = ?",
            (session_id,),
        )
        row = await cursor.fetchone()
        questions = json.loads(row[0]) if row else []

        await conn.execute(
            """
            UPDATE twin_interview_sessions
            SET answers_json = ?, status = 'completed', completed_at = ?
            WHERE id = ?
            """,
            (
                json.dumps(parsed, ensure_ascii=False),
                datetime.now(timezone.utc).isoformat(),
                session_id,
            ),
        )
        await conn.commit()

    combined_for_facts = []
    for idx, answer in parsed.items():
        q_text = ""
        if 1 <= idx <= len(questions):
            q_text = questions[idx - 1].get("question", "")

        try:
            sample = f"{q_text}\n{answer}" if q_text else answer
            await twin_db.add_raw_sample(text=sample, tag="interview")
        except Exception as e:
            logger.error(f"Twin interview: ошибка записи ответа в пул: {e}")

        if q_text:
            combined_for_facts.append(f"Вопрос: {q_text}\nОтвет: {answer}")
        else:
            combined_for_facts.append(answer)

    if combined_for_facts:
        try:
            await ingest_facts_text("\n\n".join(combined_for_facts))
        except Exception as e:
            logger.error(f"Twin interview: ошибка извлечения фактов: {e}")

    return len(parsed), None


async def cancel_active_session(owner_id: int) -> bool:
    session_id = await _has_active_session(owner_id)
    if session_id is None:
        return False
    async with aiosqlite.connect(DB_PATH) as conn:
        await conn.execute(
            "UPDATE twin_interview_sessions SET status = 'cancelled' WHERE id = ?",
            (session_id,),
        )
        await conn.commit()
    return True


async def _record_sequential_sample(question: str, answer: str) -> None:
    try:
        sample = f"{question}\n{answer}" if question else answer
        await twin_db.add_raw_sample(text=sample, tag="interview")
    except Exception as e:
        logger.error(f"Twin interview: ошибка записи ответа в пул: {e}")

    try:
        combined = f"Вопрос: {question}\nОтвет: {answer}" if question else answer
        await ingest_facts_text(combined)
    except Exception as e:
        logger.error(f"Twin interview: ошибка извлечения фактов: {e}")


async def submit_sequential_answer(owner_id: int, text: str) -> dict | None:
    session = await _get_active_session_full(owner_id)
    if not session or session["mode"] != "sequential":
        return None

    questions = json.loads(session["questions_json"])
    idx = session["current_index"]
    if idx >= len(questions):
        return None

    answers = json.loads(session["answers_json"]) if session["answers_json"] else {}
    answers[str(idx + 1)] = text.strip()

    await _record_sequential_sample(questions[idx].get("question", ""), text.strip())

    next_idx = idx + 1
    is_done = next_idx >= len(questions)

    async with aiosqlite.connect(DB_PATH) as conn:
        if is_done:
            await conn.execute(
                """
                UPDATE twin_interview_sessions
                SET answers_json = ?, status = 'completed', completed_at = ?, current_index = ?
                WHERE id = ?
                """,
                (
                    json.dumps(answers, ensure_ascii=False),
                    datetime.now(timezone.utc).isoformat(),
                    next_idx,
                    session["id"],
                ),
            )
        else:
            await conn.execute(
                """
                UPDATE twin_interview_sessions
                SET answers_json = ?, current_index = ?
                WHERE id = ?
                """,
                (json.dumps(answers, ensure_ascii=False), next_idx, session["id"]),
            )
        await conn.commit()

    return {
        "done": is_done,
        "answered_count": len(answers),
        "total": len(questions),
        "next_question": questions[next_idx]["question"] if not is_done else None,
        "next_index": next_idx + 1,
    }


async def skip_sequential_question(owner_id: int) -> dict | None:
    session = await _get_active_session_full(owner_id)
    if not session or session["mode"] != "sequential":
        return None

    questions = json.loads(session["questions_json"])
    idx = session["current_index"]
    if idx >= len(questions):
        return None

    next_idx = idx + 1
    is_done = next_idx >= len(questions)

    async with aiosqlite.connect(DB_PATH) as conn:
        if is_done:
            await conn.execute(
                """
                UPDATE twin_interview_sessions
                SET status = 'completed', completed_at = ?, current_index = ?
                WHERE id = ?
                """,
                (datetime.now(timezone.utc).isoformat(), next_idx, session["id"]),
            )
        else:
            await conn.execute(
                "UPDATE twin_interview_sessions SET current_index = ? WHERE id = ?",
                (next_idx, session["id"]),
            )
        await conn.commit()

    return {
        "done": is_done,
        "total": len(questions),
        "next_question": questions[next_idx]["question"] if not is_done else None,
        "next_index": next_idx + 1,
    }


async def try_handle_sequential_message(message) -> bool:
    if not message.from_user or not its_me(message.from_user.id):
        return False

    text = (message.text or message.caption or "").strip()
    if not text or text.startswith(("!", "/")):
        return False

    session = await _get_active_session_full(message.from_user.id)
    if not session or session["mode"] != "sequential":
        return False

    result, wait_msg = await process_with_queue(
        message=message,
        queue_name=QUEUE_NAME,
        icon="🧬",
        title="Интервью по одному",
        action_text="Разбор ответа и обучение двойника",
        func=submit_sequential_answer,
        owner_id=message.from_user.id,
        text=text,
    )
    if result is None:
        return True

    if result["done"]:
        await wait_msg.edit_text(
            format_styled_message(
                "✅",
                "Интервью завершено",
                f"Отвечено вопросов: {result['answered_count']}/{result['total']}. "
                "Отправлено в обучение двойника.",
            )
        )
    else:
        await wait_msg.edit_text(
            format_styled_message(
                "🧬",
                "Интервью по одному",
                f"Принято ({result['next_index'] - 1}/{result['total']}).\n\n"
                f"<b>Вопрос {result['next_index']}/{result['total']}:</b>\n"
                f"{result['next_question']}",
            )
        )
    return True

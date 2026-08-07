import re
import json
import asyncio
import logging
from datetime import datetime, timedelta, timezone
from bot.twin.database import twin_db, TWIN_BACKGROUND_QUEUE
from bot.utils.ai_core import ask_ai
from bot.utils.task_queue import queue_manager

logger = logging.getLogger(__name__)

CYCLE_INTERVAL_DAYS = 7
CHECK_INTERVAL_SECONDS = 6 * 60 * 60
MIN_SAMPLES_TO_RUN = 12
PRIMARY_BLOCK_NAME = "speech_style"
STATE_TTL_DAYS = 14

META_LAST_RUN_KEY = "last_cycle_run"


EXTRACTOR_SYSTEM = (
    "Ты аналитик стиля общения и мышления человека. Тебе дают список сырых "
    "сообщений одного человека, иногда с контекстом (на что он отвечал). "
    "Раздели наблюдения на два блока:\n"
    "ЧЕРТЫ — устойчивые паттерны, повторяющиеся в разных сообщениях "
    "(стиль речи, лексика, логика аргументации, характерные обороты).\n"
    "СОСТОЯНИЕ — то, что похоже на текущий временный контекст (разовые "
    "темы, дела, настроение в моменте), а не устойчивую черту.\n"
    "Не выдумывай ничего, чего нет в тексте. Отвечай СТРОГО в виде JSON, "
    "без пояснений и без markdown-разметки:\n"
    '{"traits": ["...", "..."], "state": ["...", "..."]}\n'
    "Каждый пункт — короткая законченная мысль, не более 15 слов."
)

GENERATOR_SYSTEM = (
    "Ты пишешь техническое описание стиля речи и мышления человека для "
    "системного промпта его ИИ-двойника. На основе списка устойчивых черт "
    "собери ОДИН связный блок инструкций: как двойнику говорить и "
    "рассуждать, чтобы это было похоже на реального человека. Только "
    "конкретные, применимые инструкции (лексика, длина фраз, характерные "
    "обороты, типичные реакции) — без общих слов вроде 'будь дружелюбным'. "
    "80-120 слов. Ответь только текстом блока, без заголовков и пояснений."
)

JUDGE_SYSTEM = (
    "Ты редактор системных промптов. Тебе дан СТАРЫЙ блок инструкций по "
    "стилю двойника и НОВЫЙ блок-кандидат, собранный из свежих наблюдений "
    "за последнюю неделю. Собери из них ОДИН финальный блок:\n"
    "- сохраняй черты, которые повторяются в обоих — это подтверждённый паттерн;\n"
    "- добавляй новое из кандидата, если оно не противоречит старому;\n"
    "- при противоречии предпочитай более конкретную формулировку, а не общую;\n"
    "- не раздувай объём ради объёма, 80-130 слов.\n"
    "Ответь только финальным текстом блока, без пояснений и заголовков."
)

DISTILLER_SYSTEM = (
    "Из сырых сообщений вытяни устойчивые фактические данные о человеке: "
    "профессия/работа, интересы, увлечения, явно выраженные мнения по темам, "
    "повторяющиеся предпочтения. Игнорируй разовые бытовые детали, эмоции "
    "момента и чужие реплики (контекст ответа используй только для смысла, "
    "не как факт о нём). Формат ответа — строго построчно, без нумерации:\n"
    "ключ | категория | значение\n"
    "Пример: работа | профессия | пишет телеграм-ботов на python, aiogram\n"
    "Если фактов нет — ответь одним словом: NONE."
)


def _format_samples(samples: list[dict]) -> str:
    lines = []
    for s in samples:
        tag = s.get("tag", "?")
        text = s.get("text", "")
        reply_context = s.get("reply_context")
        reply_author = s.get("reply_author")
        if reply_context:
            lines.append(
                f"[{tag}] (в ответ на {reply_author or 'кого-то'}: "
                f"«{reply_context[:200]}») -> {text}"
            )
        else:
            lines.append(f"[{tag}] {text}")
    return "\n".join(lines)


def _safe_json_extract(raw: str) -> dict:
    if not raw:
        return {}
    cleaned = re.sub(r"```(json)?", "", raw).strip()
    try:
        return json.loads(cleaned)
    except Exception:
        match = re.search(r"\{.*\}", cleaned, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(0))
            except Exception:
                pass
    logger.warning(
        "Twin pipeline: не удалось распарсить JSON экстрактора: %s", raw[:300]
    )
    return {}


async def _run_extractor(samples_text: str) -> tuple[list[str], list[str]]:
    raw = await ask_ai(
        user_prompt=samples_text,
        system_prompt=EXTRACTOR_SYSTEM,
        temperature=0.2,
        max_tokens=800,
    )
    data = _safe_json_extract(raw or "")
    traits = data.get("traits") or []
    state = data.get("state") or []
    return traits, state


async def _run_generator(traits: list[str]) -> str | None:
    prompt = "ЧЕРТЫ:\n" + "\n".join(f"- {t}" for t in traits)
    return await ask_ai(
        user_prompt=prompt,
        system_prompt=GENERATOR_SYSTEM,
        temperature=0.5,
        max_tokens=400,
    )


async def merge_block(old_block: str, candidate_block: str) -> str | None:
    return await _run_judge(old_block, candidate_block)


async def _run_judge(old_block: str, candidate_block: str) -> str | None:
    if not old_block:
        return candidate_block
    if not candidate_block:
        return old_block

    prompt = f"СТАРЫЙ БЛОК:\n{old_block}\n\nНОВЫЙ БЛОК-КАНДИДАТ:\n{candidate_block}"
    result = await ask_ai(
        user_prompt=prompt,
        system_prompt=JUDGE_SYSTEM,
        temperature=0.3,
        max_tokens=400,
    )
    return result or old_block


async def _run_distiller(samples_text: str) -> list[tuple[str, str, str]]:
    raw = await ask_ai(
        user_prompt=samples_text,
        system_prompt=DISTILLER_SYSTEM,
        temperature=0.2,
        max_tokens=800,
    )
    if not raw or raw.strip().upper().startswith("NONE"):
        return []

    facts = []
    for line in raw.strip().splitlines():
        parts = [p.strip() for p in line.split("|", maxsplit=2)]
        if len(parts) == 3 and all(parts):
            key, category, value = parts
            facts.append((key, category, value))
        else:
            logger.warning(
                "Twin pipeline: пропущена нераспарсенная строка дистиллятора: %s", line
            )
    return facts


async def run_weekly_cycle() -> bool:
    samples = await twin_db.get_unprocessed_raw_samples()

    if len(samples) < MIN_SAMPLES_TO_RUN:
        logger.info(
            "🧬 Twin pipeline: недостаточно сэмплов (%s/%s), пропуск цикла",
            len(samples),
            MIN_SAMPLES_TO_RUN,
        )
        return False

    samples_text = _format_samples(samples)

    traits, state = await _run_extractor(samples_text)
    if not traits and not state:
        logger.error(
            "🧬 Twin pipeline: экстрактор не дал результата, пул сохранён для повтора"
        )
        return False

    if traits:
        candidate_block = await _run_generator(traits)
        if not candidate_block:
            logger.error(
                "🧬 Twin pipeline: генератор не дал результата, пул сохранён для повтора"
            )
            return False

        old_block = await twin_db.get_prompt_block(PRIMARY_BLOCK_NAME) or ""
        final_block = await _run_judge(old_block, candidate_block)
        if final_block:
            await twin_db.upsert_prompt_block(PRIMARY_BLOCK_NAME, final_block)
            logger.info("🧬 Twin pipeline: блок '%s' обновлён", PRIMARY_BLOCK_NAME)
        else:
            logger.warning("🧬 Twin pipeline: судья не дал результата, блок не тронут")

    if state:
        await twin_db.set_state(state, STATE_TTL_DAYS)
        logger.info("🧬 Twin pipeline: текущее состояние обновлено")

    facts = await _run_distiller(samples_text)
    for key, category, value in facts:
        await twin_db.upsert_knowledge(key, value, category)
    logger.info("🧬 Twin pipeline: в базу знаний записано фактов: %s", len(facts))

    await twin_db.mark_samples_processed([s["id"] for s in samples])
    await twin_db.set_meta(META_LAST_RUN_KEY, datetime.now(timezone.utc).isoformat())
    logger.info("🧬 Twin pipeline: цикл обслуживания успешно завершён")
    return True


async def _is_cycle_due() -> bool:
    last_run_raw = await twin_db.get_meta(META_LAST_RUN_KEY)
    if not last_run_raw:
        return True
    try:
        last_run = datetime.fromisoformat(last_run_raw)
    except ValueError:
        return True
    return datetime.now(timezone.utc) - last_run >= timedelta(days=CYCLE_INTERVAL_DAYS)


async def weekly_worker() -> None:
    logger.info("🧬 Twin weekly worker запущен в фоне")
    while True:
        try:
            if await _is_cycle_due():
                future, _position = await queue_manager.add_task(
                    TWIN_BACKGROUND_QUEUE, run_weekly_cycle
                )
                await future
        except Exception as e:
            logger.error(
                "🧬 Twin pipeline: необработанная ошибка цикла: %s", e, exc_info=True
            )
        await asyncio.sleep(CHECK_INTERVAL_SECONDS)


async def get_status() -> dict:
    pool_size = await twin_db.get_pool_size()
    blocks = await twin_db.get_all_prompt_blocks()
    keys = await twin_db.list_knowledge_keys()
    dialogue_examples_count = await twin_db.get_dialogue_examples_count()
    last_run = await twin_db.get_meta(META_LAST_RUN_KEY, "ещё не запускался")
    return {
        "pool_size": pool_size,
        "blocks": list(blocks.keys()),
        "knowledge_count": len(keys),
        "dialogue_examples_count": dialogue_examples_count,
        "last_cycle_run": last_run,
    }

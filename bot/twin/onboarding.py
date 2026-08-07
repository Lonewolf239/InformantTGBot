import re
import logging

from bot.twin.database import twin_db
from bot.twin.pipeline import merge_block, PRIMARY_BLOCK_NAME
from bot.utils.ai_core import ask_ai

logger = logging.getLogger(__name__)

FACTS_SYSTEM = (
    "Тебе дают текст, в котором человек прямо рассказывает факты о себе. "
    "Извлеки устойчивые фактические данные: профессия/занятость, интересы, "
    "увлечения, явно выраженные мнения по темам, повторяющиеся предпочтения. "
    "Не выдумывай ничего, чего нет в тексте, и не додумывай выводы. Формат "
    "ответа — строго построчно, без нумерации и пояснений:\n"
    "ключ | категория | значение\n"
    "Пример: работа | профессия | фронтенд-разработчик, верстает интерфейсы\n"
    "Если фактов нет — ответь одним словом: NONE."
)


def split_style_blocks(text: str) -> list[str]:
    parts = re.split(r"(?=СТИЛЬ\s*:)", text)
    return [p.strip() for p in parts if p.strip()]


async def seed_personality_from_text(text: str) -> str:
    blocks = split_style_blocks(text)
    if not blocks:
        blocks = [text.strip()] if text.strip() else []
    if not blocks:
        return ""

    current = await twin_db.get_prompt_block(PRIMARY_BLOCK_NAME) or ""
    for block in blocks:
        merged = await merge_block(current, block)
        if merged:
            current = merged
        else:
            logger.warning(
                "Twin onboarding: судья не смог смёржить один из профилей, пропущен"
            )

    if current:
        await twin_db.upsert_prompt_block(PRIMARY_BLOCK_NAME, current)

    return current


def _parse_fact_lines(raw: str) -> list[tuple[str, str, str]]:
    if not raw or raw.strip().upper().startswith("NONE"):
        return []
    facts = []
    for line in raw.strip().splitlines():
        parts = [p.strip() for p in line.split("|", maxsplit=2)]
        if len(parts) == 3 and all(parts):
            facts.append((parts[0], parts[1], parts[2]))
        elif line.strip():
            logger.warning("Twin onboarding: нераспарсенная строка фактов: %s", line)
    return facts


async def ingest_facts_text(raw_text: str) -> list[tuple[str, str, str]]:
    raw_text = (raw_text or "").strip()
    if not raw_text:
        return []

    response = await ask_ai(
        user_prompt=raw_text,
        system_prompt=FACTS_SYSTEM,
        temperature=0.2,
        max_tokens=800,
    )
    facts = _parse_fact_lines(response or "")

    for key, category, value in facts:
        await twin_db.upsert_knowledge(key, value, category)

    return facts

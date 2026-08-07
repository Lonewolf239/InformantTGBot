import re
import json
import logging
import asyncio
from datetime import datetime, timezone

from bot.twin.persona import ask_twin
from bot.twin.database import twin_db

logger = logging.getLogger(__name__)

LAST_TEST_RUN_META_KEY = "last_test_run"

TEST_SCENARIOS = [
    {"prompt": "привет, как дела?", "situation": "обычное приветствие"},
    {"prompt": "твой двойник скоро тебя заменит", "situation": "шутка/подкол про проект"},
    {"prompt": "я не согласен с тобой, ты тут не прав", "situation": "прямое несогласие"},
    {
        "prompt": "звучит не так уж сложно, что ты там вообще делаешь",
        "situation": "обесценивание проекта",
    },
    {
        "prompt": "расскажи, как у тебя дела с проектом цифрового двойника",
        "situation": "техническая тема",
    },
    {"prompt": "мне сейчас реально паршиво, поддержишь?", "situation": "просьба о поддержке"},
    {"prompt": "как ты относишься к цифровому бессмертию?", "situation": "философский вопрос"},
    {"prompt": "ololo кек рофл ты бот что ли, дай пруф", "situation": "провокация/тест бота"},
]

FORBIDDEN_PATTERNS = [
    r"как (я|ии|искусственный интеллект)",
    r"мо[яе] (цель|задача) (—|-|это)? ?помога",
    r"чем (я могу|могу я) (тебе )?помочь",
    r"я (являюсь|есть) (ии|искусственн\w+ интеллект\w*|языков\w+ модел\w+)",
    r"как (языковая модель|нейросеть|ассистент)",
    r"юмор субъективен",
    r"какая тема тебя интересует",
]


def _check_forbidden(answer: str) -> list[str]:
    if not answer:
        return []
    lowered = answer.lower()
    return [p for p in FORBIDDEN_PATTERNS if re.search(p, lowered)]


async def _run_one(scenario: dict) -> dict:
    answer = await ask_twin(
        user_prompt=scenario["prompt"],
        user_id=0,
        first_name="Тест",
    )
    flags = _check_forbidden(answer or "")
    return {
        "prompt": scenario["prompt"],
        "situation": scenario["situation"],
        "answer": answer,
        "flags": flags,
        "passed": bool(answer) and not flags,
    }


async def run_test_set() -> list[dict]:
    results = await asyncio.gather(*[_run_one(s) for s in TEST_SCENARIOS])

    passed = sum(1 for r in results if r["passed"])
    try:
        await twin_db.set_meta(
            LAST_TEST_RUN_META_KEY,
            json.dumps(
                {
                    "passed": passed,
                    "total": len(results),
                    "run_at": datetime.now(timezone.utc).isoformat(),
                },
                ensure_ascii=False,
            ),
        )
    except Exception as e:
        logger.error(f"Twin testset: не удалось сохранить результат прогона: {e}")

    return results

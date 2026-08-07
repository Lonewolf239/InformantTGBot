import re
import json
import asyncio
import logging
from typing import Optional
from bot.twin.database import twin_db, TWIN_BACKGROUND_QUEUE
from bot.twin.collector import MAX_POOL_SIZE
from bot.utils.ai_core import ask_ai
from bot.utils.helpers import its_me
from bot.utils.task_queue import queue_manager

logger = logging.getLogger(__name__)

SPLIT_MARKER = "[[SPLIT]]"
CANDIDATE_COUNT = 2

SPLIT_INSTRUCTION_NOTE = (
    "\n\n[Если мысль естественно распадается на несколько отдельных сообщений "
    "подряд (как ты иногда пишешь в переписке), раздели их строкой "
    f"{SPLIT_MARKER} на отдельной строке. Не злоупотребляй этим — большинство "
    "ответов должно оставаться одним сообщением.]"
)

PLANNER_SYSTEM = (
    "Ты планируешь ответ цифрового двойника человека перед тем, как он его "
    "напишет. По сообщению собеседника и контексту определи вероятную реакцию "
    "оригинала. Ответь СТРОГО в виде JSON, без пояснений и markdown:\n"
    '{"seriousness": 0.0-1.0, "warmth": 0.0-1.0, "sarcasm": 0.0-1.0, '
    '"preferred_length": "короткий"|"средний"|"длинный", '
    '"strategy": "краткое описание стратегии ответа в 5-10 слов"}'
)

CRITIC_SYSTEM = (
    "Тебе дано сообщение собеседника и несколько пронумерованных вариантов "
    "ответа цифрового двойника человека на него. Выбери вариант, который "
    "больше похож на живую, естественную реакцию реального человека — не "
    "самый вежливый или полный, а самый правдоподобный. Ответь СТРОГО одним "
    "числом — номером варианта, без пояснений."
)

FILTER_SYSTEM = (
    "Тебе показывают одно сообщение, которое человек написал СВОЕМУ "
    "собственному ИИ-двойнику в личном диалоге с ним. Определи: это "
    "отражает реальный стиль речи и образ мыслей этого человека, или это "
    "шутка/троллинг/проверка бота/чушь ради прикола, специально не похожая "
    "на то, как человек обычно пишет и думает?\n"
    "Ответь РОВНО одним словом:\n"
    "ДА — если это естественная речь этого человека, можно учиться на этом.\n"
    "НЕТ — если это похоже на шутку, тест системы, провокацию или чушь не всерьёз."
)

ROUTER_SYSTEM = (
    "Ты — маршрутизатор запросов для ИИ-двойника человека. Тебе дан список "
    "тем, которые двойник может знать о себе, и сообщение собеседника. "
    "Если для точного и живого ответа нужны конкретные факты из этого "
    "списка — перечисли подходящие пункты через запятую, максимально "
    "близко к тому, как они названы в списке. Если ничего из списка не "
    "требуется — ответь ровно одним словом: NONE. Больше ничего не пиши, "
    "без пояснений."
)

BLITZ_MODE_NOTE = (
    "\n[РЕЖИМ: БЛИЦ. Ты отвечаешь на одно разовое сообщение без памяти "
    "истории переписки. Не делай вид, что помнишь предыдущие сообщения "
    "этого диалога, и не проси собеседника напомнить контекст без повода.]"
)

DEFAULT_IDENTITY_CORE = (
    "Ты — цифровой двойник Lonewolf239, отвечаешь от его лица. Твоя задача — "
    "воспроизводить его правдоподобные реакции, стиль и образ мыслей, а не "
    "вести себя как обычный универсальный ассистент."
)

DEFAULT_SPEECH_STYLE = (
    "Персональный стиль ещё не накоплен — общайся нейтрально и по-человечески, "
    "не упоминай, что у тебя нет данных, и не изображай робота."
)

KNOWN_BLOCK_NAMES = {"identity_core", "speech_style", "negative_rules"}


def _build_identity_note(user_id: int, first_name: str) -> str:
    if user_id and its_me(user_id):
        return (
            "\n[СИСТЕМНОЕ УВЕДОМЛЕНИЕ: С тобой сейчас говорит твой оригинал — "
            "настоящий Lonewolf239, человек, чью личность ты копируешь. "
            "Это не повод соглашаться со всем или подыгрывать — общайся с ним "
            "так, как обычно вёл бы себя Lonewolf239, оставаясь собой.]"
        )
    safe_name = (first_name or "Собеседник").replace("\n", " ")
    return (
        f"\n[СИСТЕМНОЕ УВЕДОМЛЕНИЕ: Имя собеседника — '{safe_name}'. Это НЕ "
        f"твой оригинал, а другой человек, который сейчас общается с тобой "
        f"как с двойником Lonewolf239. Веди себя с ним так, как обычно "
        f"вёл бы себя настоящий Lonewolf239 в переписке с этим человеком.]"
    )


RELATIONSHIP_LABELS = {
    "близкий": "близкий человек, можно общаться прямо, тепло и без лишней вежливости",
    "приятель": "приятель/знакомый, тон дружелюбный, но без самых личных тем",
    "знакомый": "шапочное знакомство, держи дистанцию чуть больше обычного",
    "чужой": "малознакомый или чужой человек, будь сдержаннее и не раскрывай личное",
}


async def _relationship_note(user_id: int) -> str:
    if not user_id or its_me(user_id):
        return ""
    contact = await twin_db.get_contact(user_id)
    if not contact or contact["relationship_type"] == "unknown":
        return ""
    label = RELATIONSHIP_LABELS.get(contact["relationship_type"])
    if not label:
        return ""
    return f"\n[ОТНОШЕНИЯ С СОБЕСЕДНИКОМ: {label}.]"


async def _assemble_system_prompt(
    user_id: int, first_name: str, chat_mode: bool = False
) -> str:
    blocks = await twin_db.get_all_prompt_blocks()

    parts = [blocks.get("identity_core") or DEFAULT_IDENTITY_CORE]
    parts.append(blocks.get("speech_style") or DEFAULT_SPEECH_STYLE)

    negative_rules = blocks.get("negative_rules")
    if negative_rules:
        parts.append(negative_rules)

    for name, content in blocks.items():
        if name not in KNOWN_BLOCK_NAMES and content:
            parts.append(content)

    state = await twin_db.get_state()
    if state and state.get("items"):
        parts.append(
            "[ТЕКУЩЕЕ СОСТОЯНИЕ, МОЖЕТ БЫТЬ УЖЕ НЕАКТУАЛЬНО]:\n"
            + "\n".join(f"- {item}" for item in state["items"])
        )

    prompt = "\n\n".join(parts)
    prompt += _build_identity_note(user_id, first_name)
    prompt += await _relationship_note(user_id)
    if not chat_mode:
        prompt += BLITZ_MODE_NOTE
    return prompt


async def _resolve_needed_knowledge(
    user_prompt: str, access_level: str = "private"
) -> list[str]:
    keys = await twin_db.list_knowledge_keys(access_level)
    if not keys:
        return []

    router_prompt = (
        f"Доступные темы: {', '.join(keys)}\n\nСообщение собеседника: {user_prompt}"
    )

    try:
        raw_response = await ask_ai(
            user_prompt=router_prompt,
            system_prompt=ROUTER_SYSTEM,
            temperature=0.0,
            max_tokens=80,
        )
    except Exception as e:
        logger.error(f"Twin persona: ошибка роутинга знаний: {e}")
        return []

    if not raw_response:
        return []

    try:
        return await twin_db.resolve_knowledge_request(raw_response, access_level)
    except Exception as e:
        logger.error(f"Twin persona: ошибка резолва знаний: {e}")
        return []


async def _resolve_similar_examples(user_prompt: str) -> str:
    try:
        examples = await twin_db.find_similar_dialogue_examples(user_prompt)
    except Exception as e:
        logger.error(f"Twin persona: ошибка поиска диалоговых примеров: {e}")
        return ""

    if not examples:
        return ""

    formatted = "\n\n".join(
        f"Реплика собеседника: {ex['trigger']}\nТвой реальный ответ: {ex['response']}"
        for ex in examples
    )
    return (
        "\n\n[ПРИМЕРЫ ТВОИХ РЕАЛЬНЫХ ОТВЕТОВ В ПОХОЖИХ СИТУАЦИЯХ, НЕ КОПИРУЙ "
        "ИХ ДОСЛОВНО, ОРИЕНТИРУЙСЯ НА ТОН И ДЛИНУ]:\n" + formatted
    )


async def _maybe_learn_from_owner(user_prompt: str) -> None:
    try:
        verdict = await ask_ai(
            user_prompt=user_prompt,
            system_prompt=FILTER_SYSTEM,
            temperature=0.0,
            max_tokens=10,
        )
        if verdict and verdict.strip().upper().startswith("ДА"):
            await twin_db.add_raw_sample(text=user_prompt, tag="self_chat")
            await twin_db.trim_pool(MAX_POOL_SIZE)
    except Exception as e:
        logger.error(f"Twin persona: ошибка фильтра самообучения: {e}")


def split_twin_answer(answer: str | None) -> list[str]:
    if not answer:
        return []
    parts = [p.strip() for p in answer.split(SPLIT_MARKER)]
    return [p for p in parts if p]


async def _plan_reaction(user_prompt: str) -> dict | None:
    try:
        raw = await ask_ai(
            user_prompt=user_prompt,
            system_prompt=PLANNER_SYSTEM,
            temperature=0.3,
            max_tokens=150,
        )
    except Exception as e:
        logger.error(f"Twin persona: ошибка планировщика реакции: {e}")
        return None

    if not raw:
        return None

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
    return None


def _format_plan_note(plan: dict | None) -> str:
    if not plan:
        return ""
    return (
        "\n\n[ПЛАН РЕАКЦИИ (внутренний, не показывай и не упоминай "
        f"собеседнику): серьёзность {plan.get('seriousness', '?')}, "
        f"теплота {plan.get('warmth', '?')}, сарказм {plan.get('sarcasm', '?')}, "
        f"предпочтительная длина ответа: {plan.get('preferred_length', '?')}, "
        f"стратегия: {plan.get('strategy', '?')}]"
    )


async def _pick_best_candidate(
    user_prompt: str, candidates: list[str]
) -> str:
    if len(candidates) <= 1:
        return candidates[0] if candidates else ""

    listing = "\n\n".join(f"Вариант {i + 1}:\n{c}" for i, c in enumerate(candidates))
    prompt = f"Сообщение собеседника: {user_prompt}\n\n{listing}"

    try:
        raw = await ask_ai(
            user_prompt=prompt,
            system_prompt=CRITIC_SYSTEM,
            temperature=0.0,
            max_tokens=10,
        )
    except Exception as e:
        logger.error(f"Twin persona: ошибка критика кандидатов: {e}")
        return candidates[0]

    if raw:
        match = re.search(r"\d+", raw)
        if match:
            idx = int(match.group()) - 1
            if 0 <= idx < len(candidates):
                return candidates[idx]
    return candidates[0]


async def _generate_candidates(
    user_prompt: str,
    system_prompt: str,
    count: int,
    ai_kwargs: dict,
    history: list[dict] | None,
    images: list[str] | None,
) -> list[str]:
    tasks = []
    for i in range(count):
        kwargs = dict(ai_kwargs)
        kwargs["temperature"] = min(1.0, kwargs.get("temperature", 0.7) + i * 0.15)
        tasks.append(
            ask_ai(
                user_prompt=user_prompt,
                system_prompt=system_prompt,
                history=history,
                images=images,
                **kwargs,
            )
        )
    results = await asyncio.gather(*tasks, return_exceptions=True)
    return [r for r in results if isinstance(r, str) and r]


async def generate_twin_reply(
    user_prompt: str,
    system_prompt: str,
    ai_kwargs: dict,
    history: list[dict] | None = None,
    images: list[str] | None = None,
    use_candidates: bool = False,
) -> Optional[str]:
    if use_candidates and not images:
        candidates = await _generate_candidates(
            user_prompt, system_prompt, CANDIDATE_COUNT, ai_kwargs, history, images
        )
        answer = await _pick_best_candidate(user_prompt, candidates) if candidates else None
    else:
        answer = await ask_ai(
            user_prompt=user_prompt,
            system_prompt=system_prompt,
            history=history,
            images=images,
            **ai_kwargs,
        )

    if answer:
        answer = re.sub(r"<think>.*?</think>", "", answer, flags=re.DOTALL).strip()

    return answer


async def ask_twin(
    user_prompt: str,
    user_id: int = 0,
    first_name: str = "",
    temperature: float = 0.7,
    top_p: float = 0.9,
    max_tokens: int = 1024,
    presence_penalty: float = 0.3,
    frequency_penalty: float = 0.3,
    use_candidates: bool = False,
) -> Optional[str]:
    if not user_prompt or not user_prompt.strip():
        return None

    is_owner = bool(user_id and its_me(user_id))
    if is_owner:
        await queue_manager.add_task(TWIN_BACKGROUND_QUEUE, _maybe_learn_from_owner, user_prompt)
    elif user_id:
        asyncio.create_task(twin_db.upsert_contact_seen(user_id, first_name))

    access_level = await twin_db.get_access_level(user_id, is_owner)
    knowledge_lines = await _resolve_needed_knowledge(user_prompt, access_level)

    system_prompt = await _assemble_system_prompt(user_id, first_name)
    if knowledge_lines:
        system_prompt += (
            "\n\n[ИЗВЕСТНЫЕ ФАКТЫ О ТЕБЕ, ЕСЛИ РЕЛЕВАНТНЫ ЗАПРОСУ]:\n"
            + "\n".join(f"- {line}" for line in knowledge_lines)
        )
    system_prompt += await _resolve_similar_examples(user_prompt)

    plan = await _plan_reaction(user_prompt)
    system_prompt += _format_plan_note(plan)
    system_prompt += SPLIT_INSTRUCTION_NOTE

    answer = await generate_twin_reply(
        user_prompt,
        system_prompt,
        {
            "temperature": temperature,
            "top_p": top_p,
            "max_tokens": max_tokens,
            "presence_penalty": presence_penalty,
            "frequency_penalty": frequency_penalty,
        },
        use_candidates=use_candidates,
    )

    return answer

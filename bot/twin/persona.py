import re
import asyncio
import logging
from typing import Optional
from bot.twin.database import twin_db
from bot.twin.collector import MAX_POOL_SIZE
from bot.utils.ai_core import ask_ai
from bot.utils.helpers import its_me

logger = logging.getLogger(__name__)

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


async def _assemble_system_prompt(
    user_id: int, first_name: str, chat_mode: bool = False
) -> str:
    blocks = await twin_db.get_all_prompt_blocks()

    if blocks:
        body = "\n\n".join(blocks.values())
    else:
        body = (
            "Ты — цифровой двойник Lonewolf239. Персональный стиль "
            "ещё не накоплен — общайся нейтрально и по-человечески, не "
            "упоминай, что у тебя нет данных, и не изображай робота."
        )

    prompt = f"Ты — цифровой двойник Lonewolf239, отвечаешь от его лица.\n\n{body}"
    prompt += _build_identity_note(user_id, first_name)
    if not chat_mode:
        prompt += BLITZ_MODE_NOTE
    return prompt


async def _resolve_needed_knowledge(user_prompt: str) -> list[str]:
    keys = await twin_db.list_knowledge_keys()
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
        return await twin_db.resolve_knowledge_request(raw_response)
    except Exception as e:
        logger.error(f"Twin persona: ошибка резолва знаний: {e}")
        return []


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


async def ask_twin(
    user_prompt: str,
    user_id: int = 0,
    first_name: str = "",
    temperature: float = 0.7,
    top_p: float = 0.9,
    max_tokens: int = 1024,
    presence_penalty: float = 0.3,
    frequency_penalty: float = 0.3,
) -> Optional[str]:
    if not user_prompt or not user_prompt.strip():
        return None

    if user_id and its_me(user_id):
        asyncio.create_task(_maybe_learn_from_owner(user_prompt))

    knowledge_lines = await _resolve_needed_knowledge(user_prompt)

    system_prompt = await _assemble_system_prompt(user_id, first_name)
    if knowledge_lines:
        system_prompt += (
            "\n\n[ИЗВЕСТНЫЕ ФАКТЫ О ТЕБЕ, ЕСЛИ РЕЛЕВАНТНЫ ЗАПРОСУ]:\n"
            + "\n".join(f"- {line}" for line in knowledge_lines)
        )

    answer = await ask_ai(
        user_prompt=user_prompt,
        system_prompt=system_prompt,
        temperature=temperature,
        top_p=top_p,
        max_tokens=max_tokens,
        presence_penalty=presence_penalty,
        frequency_penalty=frequency_penalty,
    )

    if answer:
        answer = re.sub(r"<think>.*?</think>", "", answer, flags=re.DOTALL).strip()

    return answer

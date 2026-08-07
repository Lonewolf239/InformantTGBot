import re
import random
import logging
from aiogram import types
from bot.twin.database import twin_db

logger = logging.getLogger(__name__)

BATCH_SIZE = 30
RANDOM_SAMPLE_COUNT = 3
MIN_RANDOM_WORDS = 5
MAX_RANDOM_WORDS = 25
LONG_MSG_CHARS = 150
MAX_POOL_SIZE = 1500

BASE_KEYWORDS = [
    "работа",
    "проект",
    "код",
    "программир",
    "игра",
    "фильм",
    "сериал",
    "музыка",
    "книга",
    "думаю",
    "считаю",
    "бесит",
    "нравится",
    "ненавиж",
    "хочу",
    "мечта",
]

_buffer: list[dict] = []


def _word_count(text: str) -> int:
    return len(text.split())


def _is_natural_message(text: str) -> bool:
    return bool(text) and not text.startswith("!") and not text.startswith("/")


async def observe(message: types.Message) -> None:
    text = (message.text or message.caption or "").strip()
    if not _is_natural_message(text):
        return

    reply_context = None
    reply_author = None
    if message.reply_to_message:
        reply_msg = message.reply_to_message
        original_text = (reply_msg.text or reply_msg.caption or "").strip()
        if original_text and reply_msg.from_user:
            reply_context = original_text
            reply_author = reply_msg.from_user.first_name

    _buffer.append(
        {
            "text": text,
            "reply_context": reply_context,
            "reply_author": reply_author,
        }
    )

    if len(_buffer) >= BATCH_SIZE:
        await _flush()


async def _build_keyword_pattern() -> re.Pattern | None:
    try:
        learned_keys = await twin_db.list_knowledge_keys()
        learned_words = [k.split(" (")[0] for k in learned_keys]
        keywords = [k for k in (BASE_KEYWORDS + learned_words) if k]
        if not keywords:
            return None
        escaped = "|".join(re.escape(k) for k in keywords)
        return re.compile(rf"\b({escaped})", re.IGNORECASE)
    except Exception as e:
        logger.error(f"Twin collector: не удалось собрать паттерн ключевых слов: {e}")
        return None


async def _flush() -> None:
    batch = _buffer.copy()
    _buffer.clear()

    if not batch:
        return

    pattern = await _build_keyword_pattern()

    to_store: list[tuple[dict, str]] = []

    random_candidates = [
        item
        for item in batch
        if MIN_RANDOM_WORDS <= _word_count(item["text"]) <= MAX_RANDOM_WORDS
    ]
    if not random_candidates:
        random_candidates = [item for item in batch if _word_count(item["text"]) >= 3]

    if random_candidates:
        k = min(RANDOM_SAMPLE_COUNT, len(random_candidates))
        for item in random.sample(random_candidates, k=k):
            to_store.append((item, "random"))

    for item in batch:
        text = item["text"]
        if pattern and pattern.search(text):
            to_store.append((item, "keyword"))
        elif len(text) >= LONG_MSG_CHARS:
            to_store.append((item, "long"))

    seen_texts: set[str] = set()
    stored_count = 0
    for item, tag in to_store:
        if item["text"] in seen_texts:
            continue
        seen_texts.add(item["text"])
        try:
            await twin_db.add_raw_sample(
                text=item["text"],
                reply_context=item["reply_context"],
                reply_author=item["reply_author"],
                tag=tag,
            )
            stored_count += 1
        except Exception as e:
            logger.error(f"Twin collector: ошибка записи сэмпла: {e}")

    logger.info(
        f"🧬 Twin collector: обработан батч из {len(batch)} сообщений, "
        f"сохранено сэмплов: {stored_count}"
    )

    try:
        await twin_db.trim_pool(MAX_POOL_SIZE)
    except Exception as e:
        logger.error(f"Twin collector: ошибка обрезки пула: {e}")

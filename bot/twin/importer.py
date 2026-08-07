import json
import logging
from datetime import datetime, timezone

from bot.twin.database import twin_db
from bot.twin.collector import _merge_bursts
from config import OWNER_ID

logger = logging.getLogger(__name__)

MAX_IMPORT_MESSAGES = 20000


def _extract_text(raw_text) -> str:
    if isinstance(raw_text, str):
        return raw_text.strip()
    if isinstance(raw_text, list):
        parts = []
        for item in raw_text:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict) and "text" in item:
                parts.append(str(item["text"]))
        return "".join(parts).strip()
    return ""


def _parse_from_id(from_id) -> int | None:
    if not isinstance(from_id, str) or not from_id.startswith("user"):
        return None
    try:
        return int(from_id[4:])
    except ValueError:
        return None


def _parse_date(raw_date) -> datetime | None:
    if not isinstance(raw_date, str):
        return None
    try:
        dt = datetime.fromisoformat(raw_date)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


async def import_telegram_export(raw_bytes: bytes) -> dict:
    try:
        data = json.loads(raw_bytes)
    except Exception as e:
        return {"error": f"не удалось разобрать JSON: {e}"}

    messages = data.get("messages")
    if not isinstance(messages, list):
        return {"error": "в файле нет списка messages — это не экспорт чата Telegram?"}

    messages_by_id = {
        m.get("id"): m for m in messages if isinstance(m, dict) and "id" in m
    }

    owner_items = []
    dialogue_pairs = 0

    for msg in messages[:MAX_IMPORT_MESSAGES]:
        if not isinstance(msg, dict) or msg.get("type") != "message":
            continue

        from_user_id = _parse_from_id(msg.get("from_id"))
        if from_user_id != OWNER_ID:
            continue

        text = _extract_text(msg.get("text"))
        if not text or text.startswith(("!", "/")):
            continue

        timestamp = _parse_date(msg.get("date"))
        if not timestamp:
            continue

        reply_context = None
        reply_author = None
        reply_id = msg.get("reply_to_message_id")
        reply_msg = messages_by_id.get(reply_id) if reply_id else None

        if reply_msg:
            reply_text = _extract_text(reply_msg.get("text"))
            reply_from_id = _parse_from_id(reply_msg.get("from_id"))
            if reply_text:
                reply_context = reply_text
                reply_author = reply_msg.get("from") or "Неизвестно"
                if reply_from_id and reply_from_id != OWNER_ID:
                    try:
                        await twin_db.add_dialogue_example(
                            interlocutor_id=reply_from_id,
                            interlocutor_name=reply_author,
                            trigger_message=reply_text,
                            owner_response=text,
                        )
                        dialogue_pairs += 1
                    except Exception as e:
                        logger.error(
                            f"Twin importer: ошибка записи диалогового примера: {e}"
                        )

        owner_items.append(
            {
                "text": text,
                "reply_context": reply_context,
                "reply_author": reply_author,
                "chat_id": data.get("id", 0),
                "timestamp": timestamp,
            }
        )

    merged = _merge_bursts(owner_items)

    stored = 0
    for item in merged:
        try:
            await twin_db.add_raw_sample(
                text=item["text"],
                reply_context=item["reply_context"],
                reply_author=item["reply_author"],
                tag="chat_import",
            )
            stored += 1
        except Exception as e:
            logger.error(f"Twin importer: ошибка записи сэмпла: {e}")

    return {
        "total_messages": len(messages),
        "owner_messages_found": len(owner_items),
        "stored_samples": stored,
        "dialogue_pairs": dialogue_pairs,
    }

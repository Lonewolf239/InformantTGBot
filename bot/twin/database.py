import os
import re
import json
import difflib
import logging
from datetime import datetime, timezone, timedelta
import aiosqlite

logger = logging.getLogger(__name__)

DB_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "twin.db"
)

ACCESS_RANK = {"public": 0, "friends": 1, "private": 2}
FRIEND_CLOSENESS_THRESHOLD = 0.5
DEFAULT_CONTACT_CLOSENESS = 0.3
TWIN_BACKGROUND_QUEUE = "twin_background"


def _normalize(s: str) -> str:
    if not s:
        return ""
    s = s.strip().lower()
    s = re.sub(r"[_\-]+", " ", s)
    s = re.sub(r"[«»\"'.,!?;:]+", "", s)
    s = re.sub(r"\s+", " ", s)
    return s.strip()


class TwinDatabase:
    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path

    async def init_db(self) -> None:
        os.makedirs(os.path.dirname(self.db_path) or ".", exist_ok=True)
        async with aiosqlite.connect(self.db_path) as conn:
            await conn.execute("PRAGMA journal_mode=WAL;")
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS twin_raw_pool (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    text TEXT NOT NULL,
                    reply_context TEXT,
                    reply_author TEXT,
                    tag TEXT NOT NULL DEFAULT 'random',
                    created_at TEXT NOT NULL,
                    processed_at TEXT
                )
                """)
            existing_columns = {
                row[1]
                for row in await (
                    await conn.execute("PRAGMA table_info(twin_raw_pool)")
                ).fetchall()
            }
            if "processed_at" not in existing_columns:
                await conn.execute(
                    "ALTER TABLE twin_raw_pool ADD COLUMN processed_at TEXT"
                )
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS twin_prompt_blocks (
                    block_name TEXT PRIMARY KEY,
                    content TEXT NOT NULL,
                    version INTEGER NOT NULL DEFAULT 1,
                    updated_at TEXT NOT NULL
                )
                """)
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS twin_knowledge (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    category TEXT,
                    evidence_count INTEGER NOT NULL DEFAULT 1,
                    previous_value TEXT,
                    visibility TEXT NOT NULL DEFAULT 'friends',
                    updated_at TEXT NOT NULL
                )
                """)
            existing_knowledge_columns = {
                row[1]
                for row in await (
                    await conn.execute("PRAGMA table_info(twin_knowledge)")
                ).fetchall()
            }
            if "evidence_count" not in existing_knowledge_columns:
                await conn.execute(
                    "ALTER TABLE twin_knowledge ADD COLUMN evidence_count "
                    "INTEGER NOT NULL DEFAULT 1"
                )
            if "previous_value" not in existing_knowledge_columns:
                await conn.execute(
                    "ALTER TABLE twin_knowledge ADD COLUMN previous_value TEXT"
                )
            if "visibility" not in existing_knowledge_columns:
                await conn.execute(
                    "ALTER TABLE twin_knowledge ADD COLUMN visibility "
                    "TEXT NOT NULL DEFAULT 'friends'"
                )
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS twin_meta (
                    key TEXT PRIMARY KEY,
                    value TEXT
                )
                """)
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS twin_dialogue_examples (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    interlocutor_id INTEGER,
                    interlocutor_name TEXT,
                    trigger_message TEXT NOT NULL,
                    owner_response TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """)
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS twin_contacts (
                    user_id INTEGER PRIMARY KEY,
                    display_name TEXT,
                    relationship_type TEXT NOT NULL DEFAULT 'unknown',
                    closeness REAL NOT NULL DEFAULT 0.3,
                    interaction_count INTEGER NOT NULL DEFAULT 0,
                    first_seen TEXT NOT NULL,
                    last_interaction TEXT NOT NULL
                )
                """)
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS twin_feedback (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    user_prompt TEXT NOT NULL,
                    generated_answer TEXT NOT NULL,
                    rating TEXT,
                    created_at TEXT NOT NULL
                )
                """)
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS twin_prompt_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    block_name TEXT NOT NULL,
                    content TEXT NOT NULL,
                    version INTEGER NOT NULL,
                    created_at TEXT NOT NULL
                )
                """)
            await conn.commit()
        logger.info("🧬 Twin DB инициализирована (%s)", self.db_path)

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()

    async def add_raw_sample(
        self,
        text: str,
        reply_context: str | None = None,
        reply_author: str | None = None,
        tag: str = "random",
    ) -> None:
        async with aiosqlite.connect(self.db_path) as conn:
            await conn.execute(
                """
                INSERT INTO twin_raw_pool (text, reply_context, reply_author, tag, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (text, reply_context, reply_author, tag, self._now()),
            )
            await conn.commit()

    async def get_pool_size(self) -> int:
        async with aiosqlite.connect(self.db_path) as conn:
            cursor = await conn.execute(
                "SELECT COUNT(*) FROM twin_raw_pool WHERE processed_at IS NULL"
            )
            row = await cursor.fetchone()
            return row[0] if row else 0

    async def get_processed_samples_count(self) -> int:
        async with aiosqlite.connect(self.db_path) as conn:
            cursor = await conn.execute(
                "SELECT COUNT(*) FROM twin_raw_pool WHERE processed_at IS NOT NULL"
            )
            row = await cursor.fetchone()
            return row[0] if row else 0

    async def get_unprocessed_raw_samples(self, limit: int | None = None) -> list[dict]:
        async with aiosqlite.connect(self.db_path) as conn:
            conn.row_factory = aiosqlite.Row
            query = (
                "SELECT id, text, reply_context, reply_author, tag, created_at "
                "FROM twin_raw_pool WHERE processed_at IS NULL ORDER BY id ASC"
            )
            params: tuple = ()
            if limit is not None:
                query += " LIMIT ?"
                params = (limit,)
            cursor = await conn.execute(query, params)
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]

    async def mark_samples_processed(self, ids: list[int]) -> None:
        if not ids:
            return
        placeholders = ",".join("?" for _ in ids)
        async with aiosqlite.connect(self.db_path) as conn:
            await conn.execute(
                f"UPDATE twin_raw_pool SET processed_at = ? WHERE id IN ({placeholders})",
                [self._now(), *ids],
            )
            await conn.commit()

    async def trim_pool(self, max_size: int) -> None:
        size = await self.get_pool_size()
        if size <= max_size:
            return
        to_delete = size - max_size
        async with aiosqlite.connect(self.db_path) as conn:
            await conn.execute(
                """
                DELETE FROM twin_raw_pool WHERE id IN (
                    SELECT id FROM twin_raw_pool
                    WHERE processed_at IS NULL
                    ORDER BY id ASC LIMIT ?
                )
                """,
                (to_delete,),
            )
            await conn.commit()
        logger.warning(
            "🧬 Twin pool превысил лимит (%s), удалено %s старых необработанных сэмплов",
            max_size,
            to_delete,
        )

    async def get_prompt_block(self, block_name: str) -> str | None:
        async with aiosqlite.connect(self.db_path) as conn:
            cursor = await conn.execute(
                "SELECT content FROM twin_prompt_blocks WHERE block_name = ?",
                (block_name,),
            )
            row = await cursor.fetchone()
            return row[0] if row else None

    async def get_all_prompt_blocks(self) -> dict[str, str]:
        async with aiosqlite.connect(self.db_path) as conn:
            cursor = await conn.execute(
                "SELECT block_name, content FROM twin_prompt_blocks ORDER BY block_name ASC"
            )
            rows = await cursor.fetchall()
            return {name: content for name, content in rows}

    async def get_prompt_blocks_meta(self) -> list[dict]:
        async with aiosqlite.connect(self.db_path) as conn:
            conn.row_factory = aiosqlite.Row
            cursor = await conn.execute(
                "SELECT block_name, version, updated_at, LENGTH(content) AS content_len "
                "FROM twin_prompt_blocks ORDER BY block_name ASC"
            )
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]

    async def upsert_prompt_block(self, block_name: str, content: str) -> None:
        async with aiosqlite.connect(self.db_path) as conn:
            cursor = await conn.execute(
                "SELECT content, version FROM twin_prompt_blocks WHERE block_name = ?",
                (block_name,),
            )
            existing = await cursor.fetchone()

            if existing and existing[0] != content:
                await conn.execute(
                    """
                    INSERT INTO twin_prompt_history (block_name, content, version, created_at)
                    VALUES (?, ?, ?, ?)
                    """,
                    (block_name, existing[0], existing[1], self._now()),
                )

            await conn.execute(
                """
                INSERT INTO twin_prompt_blocks (block_name, content, version, updated_at)
                VALUES (?, ?, 1, ?)
                ON CONFLICT(block_name) DO UPDATE SET
                    content = excluded.content,
                    version = twin_prompt_blocks.version + 1,
                    updated_at = excluded.updated_at
                """,
                (block_name, content, self._now()),
            )
            await conn.commit()

    async def get_prompt_block_history(
        self, block_name: str, limit: int = 10
    ) -> list[dict]:
        async with aiosqlite.connect(self.db_path) as conn:
            conn.row_factory = aiosqlite.Row
            cursor = await conn.execute(
                "SELECT id, version, content, created_at FROM twin_prompt_history "
                "WHERE block_name = ? ORDER BY id DESC LIMIT ?",
                (block_name, limit),
            )
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]

    async def rollback_prompt_block(self, block_name: str, history_id: int) -> bool:
        async with aiosqlite.connect(self.db_path) as conn:
            cursor = await conn.execute(
                "SELECT content FROM twin_prompt_history WHERE id = ? AND block_name = ?",
                (history_id, block_name),
            )
            row = await cursor.fetchone()
        if not row:
            return False
        await self.upsert_prompt_block(block_name, row[0])
        return True

    async def upsert_knowledge(
        self,
        key: str,
        value: str,
        category: str | None = None,
        visibility: str = "friends",
    ) -> None:
        async with aiosqlite.connect(self.db_path) as conn:
            cursor = await conn.execute(
                "SELECT value FROM twin_knowledge WHERE key = ?", (key,)
            )
            row = await cursor.fetchone()

            if row is None:
                await conn.execute(
                    """
                    INSERT INTO twin_knowledge
                        (key, value, category, evidence_count, previous_value, visibility, updated_at)
                    VALUES (?, ?, ?, 1, NULL, ?, ?)
                    """,
                    (key, value, category, visibility, self._now()),
                )
            elif _normalize(row[0]) == _normalize(value):
                await conn.execute(
                    """
                    UPDATE twin_knowledge
                    SET evidence_count = evidence_count + 1,
                        category = ?,
                        updated_at = ?
                    WHERE key = ?
                    """,
                    (category, self._now(), key),
                )
            else:
                await conn.execute(
                    """
                    UPDATE twin_knowledge
                    SET value = ?,
                        previous_value = ?,
                        category = ?,
                        evidence_count = 1,
                        updated_at = ?
                    WHERE key = ?
                    """,
                    (value, row[0], category, self._now(), key),
                )
            await conn.commit()

    async def list_knowledge_keys(self, access_level: str = "private") -> list[str]:
        allowed_rank = ACCESS_RANK.get(access_level, 0)
        async with aiosqlite.connect(self.db_path) as conn:
            cursor = await conn.execute(
                "SELECT key, category, visibility FROM twin_knowledge ORDER BY key ASC"
            )
            rows = await cursor.fetchall()
            return [
                f"{key} ({cat})" if cat else key
                for key, cat, visibility in rows
                if ACCESS_RANK.get(visibility or "friends", 1) <= allowed_rank
            ]

    async def get_knowledge_by_keys(self, keys: list[str]) -> list[str]:
        if not keys:
            return []
        placeholders = ",".join("?" for _ in keys)
        async with aiosqlite.connect(self.db_path) as conn:
            cursor = await conn.execute(
                f"SELECT key, value FROM twin_knowledge WHERE key IN ({placeholders})",
                keys,
            )
            rows = await cursor.fetchall()
            return [f"{k}: {v}" for k, v in rows]

    async def resolve_knowledge_request(
        self,
        ai_response: str,
        access_level: str = "private",
        limit: int = 8,
        threshold: float = 0.4,
    ) -> list[str]:
        if not ai_response or ai_response.strip().upper().startswith("NONE"):
            return []

        raw_tokens = re.split(r"[,\n;]+", ai_response)
        tokens = [_normalize(t) for t in raw_tokens if _normalize(t)]
        if not tokens:
            return []

        allowed_rank = ACCESS_RANK.get(access_level, 0)
        async with aiosqlite.connect(self.db_path) as conn:
            cursor = await conn.execute(
                "SELECT key, value, category FROM twin_knowledge WHERE visibility IS NULL "
                "OR (CASE visibility "
                "WHEN 'private' THEN 2 WHEN 'friends' THEN 1 ELSE 0 END) <= ?",
                (allowed_rank,),
            )
            rows = await cursor.fetchall()

        if not rows:
            return []

        scored: dict[str, tuple[float, str]] = {}
        for key, value, category in rows:
            norm_key = _normalize(key)
            norm_cat = _normalize(category or "")
            best_score = 0.0

            for token in tokens:
                score = difflib.SequenceMatcher(None, token, norm_key).ratio()
                if norm_cat:
                    score = max(
                        score,
                        difflib.SequenceMatcher(None, token, norm_cat).ratio(),
                    )
                if norm_key and (token in norm_key or norm_key in token):
                    score = max(score, 0.85)

                best_score = max(best_score, score)

            if best_score >= threshold:
                scored[key] = (best_score, value)

        top = sorted(scored.items(), key=lambda kv: kv[1][0], reverse=True)[:limit]
        return [f"{key}: {value}" for key, (_, value) in top]

    async def set_state(self, items: list[str], ttl_days: int) -> None:
        payload = {
            "items": items,
            "updated_at": self._now(),
            "expires_at": (
                datetime.now(timezone.utc) + timedelta(days=ttl_days)
            ).isoformat(),
        }
        await self.set_meta("current_state", json.dumps(payload, ensure_ascii=False))

    async def get_state(self) -> dict | None:
        raw = await self.get_meta("current_state")
        if not raw:
            return None
        try:
            payload = json.loads(raw)
        except Exception:
            return None
        expires_at = payload.get("expires_at")
        if expires_at:
            try:
                if datetime.now(timezone.utc) > datetime.fromisoformat(expires_at):
                    return None
            except ValueError:
                pass
        return payload if payload.get("items") else None

    async def get_meta(self, key: str, default: str | None = None) -> str | None:
        async with aiosqlite.connect(self.db_path) as conn:
            cursor = await conn.execute(
                "SELECT value FROM twin_meta WHERE key = ?", (key,)
            )
            row = await cursor.fetchone()
            return row[0] if row else default

    async def set_meta(self, key: str, value: str) -> None:
        async with aiosqlite.connect(self.db_path) as conn:
            await conn.execute(
                """
                INSERT INTO twin_meta (key, value) VALUES (?, ?)
                ON CONFLICT(key) DO UPDATE SET value = excluded.value
                """,
                (key, value),
            )
            await conn.commit()

    async def add_dialogue_example(
        self,
        interlocutor_id: int | None,
        interlocutor_name: str | None,
        trigger_message: str,
        owner_response: str,
    ) -> None:
        async with aiosqlite.connect(self.db_path) as conn:
            await conn.execute(
                """
                INSERT INTO twin_dialogue_examples
                    (interlocutor_id, interlocutor_name, trigger_message, owner_response, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (interlocutor_id, interlocutor_name, trigger_message, owner_response, self._now()),
            )
            await conn.commit()

    async def get_dialogue_examples_count(self) -> int:
        async with aiosqlite.connect(self.db_path) as conn:
            cursor = await conn.execute("SELECT COUNT(*) FROM twin_dialogue_examples")
            row = await cursor.fetchone()
            return row[0] if row else 0

    async def find_similar_dialogue_examples(
        self, query: str, limit: int = 5, threshold: float = 0.25
    ) -> list[dict]:
        norm_query = _normalize(query)
        if not norm_query:
            return []

        async with aiosqlite.connect(self.db_path) as conn:
            cursor = await conn.execute(
                "SELECT trigger_message, owner_response FROM twin_dialogue_examples "
                "ORDER BY id DESC LIMIT 300"
            )
            rows = await cursor.fetchall()

        scored = []
        for trigger, response in rows:
            score = difflib.SequenceMatcher(None, norm_query, _normalize(trigger)).ratio()
            if score >= threshold:
                scored.append((score, trigger, response))

        scored.sort(key=lambda t: t[0], reverse=True)
        return [
            {"trigger": trigger, "response": response}
            for _, trigger, response in scored[:limit]
        ]

    async def get_knowledge_summary(self, limit: int = 10) -> dict:
        async with aiosqlite.connect(self.db_path) as conn:
            cursor = await conn.execute(
                "SELECT visibility, COUNT(*) FROM twin_knowledge GROUP BY visibility"
            )
            visibility_rows = await cursor.fetchall()
            cursor2 = await conn.execute(
                "SELECT key, value, category, evidence_count FROM twin_knowledge "
                "ORDER BY evidence_count DESC, updated_at DESC LIMIT ?",
                (limit,),
            )
            top_rows = await cursor2.fetchall()

        by_visibility = {"public": 0, "friends": 0, "private": 0}
        for visibility, count in visibility_rows:
            if visibility in by_visibility:
                by_visibility[visibility] = count

        return {
            "by_visibility": by_visibility,
            "top_facts": [
                {"key": k, "value": v, "category": c, "evidence_count": e}
                for k, v, c, e in top_rows
            ],
        }

    async def get_contacts_count(self) -> int:
        async with aiosqlite.connect(self.db_path) as conn:
            cursor = await conn.execute("SELECT COUNT(*) FROM twin_contacts")
            row = await cursor.fetchone()
            return row[0] if row else 0

    async def get_all_contacts(self, limit: int = 20) -> list[dict]:
        async with aiosqlite.connect(self.db_path) as conn:
            conn.row_factory = aiosqlite.Row
            cursor = await conn.execute(
                "SELECT * FROM twin_contacts ORDER BY interaction_count DESC LIMIT ?",
                (limit,),
            )
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]

    async def upsert_contact_seen(
        self, user_id: int, display_name: str | None
    ) -> None:
        async with aiosqlite.connect(self.db_path) as conn:
            await conn.execute(
                """
                INSERT INTO twin_contacts
                    (user_id, display_name, interaction_count, first_seen, last_interaction)
                VALUES (?, ?, 1, ?, ?)
                ON CONFLICT(user_id) DO UPDATE SET
                    display_name = excluded.display_name,
                    interaction_count = twin_contacts.interaction_count + 1,
                    last_interaction = excluded.last_interaction
                """,
                (user_id, display_name, self._now(), self._now()),
            )
            await conn.commit()

    async def set_contact_relationship(
        self,
        user_id: int,
        display_name: str | None,
        relationship_type: str,
        closeness: float,
    ) -> None:
        async with aiosqlite.connect(self.db_path) as conn:
            await conn.execute(
                """
                INSERT INTO twin_contacts
                    (user_id, display_name, relationship_type, closeness,
                     interaction_count, first_seen, last_interaction)
                VALUES (?, ?, ?, ?, 1, ?, ?)
                ON CONFLICT(user_id) DO UPDATE SET
                    display_name = excluded.display_name,
                    relationship_type = excluded.relationship_type,
                    closeness = excluded.closeness,
                    last_interaction = excluded.last_interaction
                """,
                (user_id, display_name, relationship_type, closeness, self._now(), self._now()),
            )
            await conn.commit()

    async def get_contact(self, user_id: int) -> dict | None:
        async with aiosqlite.connect(self.db_path) as conn:
            conn.row_factory = aiosqlite.Row
            cursor = await conn.execute(
                "SELECT * FROM twin_contacts WHERE user_id = ?", (user_id,)
            )
            row = await cursor.fetchone()
            return dict(row) if row else None

    async def set_knowledge_visibility(self, key: str, visibility: str) -> bool:
        async with aiosqlite.connect(self.db_path) as conn:
            cursor = await conn.execute(
                "UPDATE twin_knowledge SET visibility = ? WHERE key = ?",
                (visibility, key),
            )
            await conn.commit()
            return cursor.rowcount > 0

    async def get_access_level(self, user_id: int, is_owner: bool) -> str:
        if is_owner:
            return "private"
        if not user_id:
            return "public"
        contact = await self.get_contact(user_id)
        closeness = contact["closeness"] if contact else DEFAULT_CONTACT_CLOSENESS
        return "friends" if closeness >= FRIEND_CLOSENESS_THRESHOLD else "public"

    async def log_feedback_candidate(
        self, user_id: int, user_prompt: str, generated_answer: str
    ) -> int:
        async with aiosqlite.connect(self.db_path) as conn:
            cursor = await conn.execute(
                """
                INSERT INTO twin_feedback (user_id, user_prompt, generated_answer, rating, created_at)
                VALUES (?, ?, ?, NULL, ?)
                """,
                (user_id, user_prompt, generated_answer, self._now()),
            )
            await conn.commit()
            return cursor.lastrowid

    async def set_feedback_rating(self, feedback_id: int, rating: str) -> bool:
        async with aiosqlite.connect(self.db_path) as conn:
            cursor = await conn.execute(
                "UPDATE twin_feedback SET rating = ? WHERE id = ?",
                (rating, feedback_id),
            )
            await conn.commit()
            return cursor.rowcount > 0

    async def get_feedback_stats(self) -> dict:
        async with aiosqlite.connect(self.db_path) as conn:
            cursor = await conn.execute(
                "SELECT rating, COUNT(*) FROM twin_feedback "
                "WHERE rating IS NOT NULL GROUP BY rating"
            )
            rows = await cursor.fetchall()
            cursor2 = await conn.execute(
                "SELECT COUNT(*) FROM twin_feedback WHERE rating IS NULL"
            )
            pending_row = await cursor2.fetchone()

        stats = {"good": 0, "maybe": 0, "bad": 0}
        for rating, count in rows:
            if rating in stats:
                stats[rating] = count
        stats["pending"] = pending_row[0] if pending_row else 0
        return stats


twin_db = TwinDatabase()

import os
import re
import difflib
import logging
from datetime import datetime, timezone
import aiosqlite

logger = logging.getLogger(__name__)

DB_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "twin.db"
)


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
                    created_at TEXT NOT NULL
                )
                """)
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
                    updated_at TEXT NOT NULL
                )
                """)
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS twin_meta (
                    key TEXT PRIMARY KEY,
                    value TEXT
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
            cursor = await conn.execute("SELECT COUNT(*) FROM twin_raw_pool")
            row = await cursor.fetchone()
            return row[0] if row else 0

    async def get_all_raw_samples(self) -> list[dict]:
        async with aiosqlite.connect(self.db_path) as conn:
            conn.row_factory = aiosqlite.Row
            cursor = await conn.execute(
                "SELECT text, reply_context, reply_author, tag, created_at "
                "FROM twin_raw_pool ORDER BY id ASC"
            )
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]

    async def clear_pool(self) -> None:
        async with aiosqlite.connect(self.db_path) as conn:
            await conn.execute("DELETE FROM twin_raw_pool")
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
                    SELECT id FROM twin_raw_pool ORDER BY id ASC LIMIT ?
                )
                """,
                (to_delete,),
            )
            await conn.commit()
        logger.warning(
            "🧬 Twin pool превысил лимит (%s), удалено %s старых сэмплов",
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

    async def upsert_prompt_block(self, block_name: str, content: str) -> None:
        async with aiosqlite.connect(self.db_path) as conn:
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

    async def upsert_knowledge(
        self, key: str, value: str, category: str | None = None
    ) -> None:
        async with aiosqlite.connect(self.db_path) as conn:
            await conn.execute(
                """
                INSERT INTO twin_knowledge (key, value, category, updated_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(key) DO UPDATE SET
                    value = excluded.value,
                    category = excluded.category,
                    updated_at = excluded.updated_at
                """,
                (key, value, category, self._now()),
            )
            await conn.commit()

    async def list_knowledge_keys(self) -> list[str]:
        async with aiosqlite.connect(self.db_path) as conn:
            cursor = await conn.execute(
                "SELECT key, category FROM twin_knowledge ORDER BY key ASC"
            )
            rows = await cursor.fetchall()
            return [f"{key} ({cat})" if cat else key for key, cat in rows]

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
        limit: int = 8,
        threshold: float = 0.4,
    ) -> list[str]:
        if not ai_response or ai_response.strip().upper().startswith("NONE"):
            return []

        raw_tokens = re.split(r"[,\n;]+", ai_response)
        tokens = [_normalize(t) for t in raw_tokens if _normalize(t)]
        if not tokens:
            return []

        async with aiosqlite.connect(self.db_path) as conn:
            cursor = await conn.execute(
                "SELECT key, value, category FROM twin_knowledge"
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


twin_db = TwinDatabase()

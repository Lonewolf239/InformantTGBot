import aiosqlite
import os
from datetime import datetime
from typing import Dict, List, Optional, Any
import logging

logger = logging.getLogger(__name__)

DB_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "bot_stats.db"
)


class Database:
    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path

    async def init_db(self):
        async with aiosqlite.connect(self.db_path) as conn:
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS stats (
                    id INTEGER PRIMARY KEY CHECK (id = 1),
                    total_messages INTEGER DEFAULT 0,
                    auto_replies_sent INTEGER DEFAULT 0,
                    rp_actions_used INTEGER DEFAULT 0,
                    jokes_sent INTEGER DEFAULT 0,
                    memes_sent INTEGER DEFAULT 0,
                    commands_used INTEGER DEFAULT 0,
                    away_mode_toggled INTEGER DEFAULT 0,
                    start_time TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """)

            await conn.execute("""
                CREATE TABLE IF NOT EXISTS user_stats (
                    user_id INTEGER PRIMARY KEY,
                    username TEXT,
                    user_link TEXT,
                    first_seen TEXT NOT NULL,
                    last_message TEXT NOT NULL,
                    messages_count INTEGER DEFAULT 0,
                    received_auto_reply INTEGER DEFAULT 0,
                    last_auto_reply TEXT
                )
            """)

            await conn.execute("""
                CREATE TABLE IF NOT EXISTS command_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    command TEXT NOT NULL,
                    user_id INTEGER NOT NULL,
                    executed_at TEXT NOT NULL
                )
            """)

            await conn.execute("""
                CREATE TABLE IF NOT EXISTS auto_reply_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    reply_text TEXT NOT NULL,
                    sent_at TEXT NOT NULL
                )
            """)

            await conn.execute("""
                CREATE TABLE IF NOT EXISTS rp_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    target_id INTEGER NOT NULL,
                    action TEXT NOT NULL,
                    custom_text TEXT,
                    executed_at TEXT NOT NULL
                )
            """)

            async with conn.execute("SELECT id FROM stats WHERE id = 1") as cursor:
                if not await cursor.fetchone():
                    await conn.execute(
                        """
                        INSERT INTO stats (id, start_time, updated_at)
                        VALUES (1, ?, ?)
                    """,
                        (datetime.now().isoformat(), datetime.now().isoformat()),
                    )

            await conn.commit()

    async def get_total_messages(self) -> int:
        async with aiosqlite.connect(self.db_path) as conn:
            async with conn.execute(
                "SELECT total_messages FROM stats WHERE id = 1"
            ) as cursor:
                result = await cursor.fetchone()
                return result[0] if result else 0

    async def increment_total_messages(self):
        async with aiosqlite.connect(self.db_path) as conn:
            await conn.execute(
                """
                UPDATE stats
                SET total_messages = total_messages + 1,
                    updated_at = ?
                WHERE id = 1
            """,
                (datetime.now().isoformat(),),
            )
            await conn.commit()

    async def increment_auto_replies(self):
        async with aiosqlite.connect(self.db_path) as conn:
            await conn.execute(
                """
                UPDATE stats
                SET auto_replies_sent = auto_replies_sent + 1,
                    updated_at = ?
                WHERE id = 1
            """,
                (datetime.now().isoformat(),),
            )
            await conn.commit()

    async def increment_rp_actions(self):
        async with aiosqlite.connect(self.db_path) as conn:
            await conn.execute(
                """
                UPDATE stats
                SET rp_actions_used = rp_actions_used + 1,
                    updated_at = ?
                WHERE id = 1
            """,
                (datetime.now().isoformat(),),
            )
            await conn.commit()

    async def increment_jokes(self):
        async with aiosqlite.connect(self.db_path) as conn:
            await conn.execute(
                """
                UPDATE stats
                SET jokes_sent = jokes_sent + 1,
                    updated_at = ?
                WHERE id = 1
            """,
                (datetime.now().isoformat(),),
            )
            await conn.commit()

    async def increment_memes(self):
        async with aiosqlite.connect(self.db_path) as conn:
            await conn.execute(
                """
                UPDATE stats
                SET memes_sent = memes_sent + 1,
                    updated_at = ?
                WHERE id = 1
            """,
                (datetime.now().isoformat(),),
            )
            await conn.commit()

    async def increment_commands(self):
        async with aiosqlite.connect(self.db_path) as conn:
            await conn.execute(
                """
                UPDATE stats
                SET commands_used = commands_used + 1,
                    updated_at = ?
                WHERE id = 1
            """,
                (datetime.now().isoformat(),),
            )
            await conn.commit()

    async def increment_away_toggled(self):
        async with aiosqlite.connect(self.db_path) as conn:
            await conn.execute(
                """
                UPDATE stats
                SET away_mode_toggled = away_mode_toggled + 1,
                    updated_at = ?
                WHERE id = 1
            """,
                (datetime.now().isoformat(),),
            )
            await conn.commit()

    async def get_stats(self) -> Dict[str, Any]:
        async with aiosqlite.connect(self.db_path) as conn:
            conn.row_factory = aiosqlite.Row
            async with conn.execute("SELECT * FROM stats WHERE id = 1") as cursor:
                row = await cursor.fetchone()
                return dict(row) if row else {}

    async def get_uptime_seconds(self) -> float:
        async with aiosqlite.connect(self.db_path) as conn:
            async with conn.execute(
                "SELECT start_time FROM stats WHERE id = 1"
            ) as cursor:
                result = await cursor.fetchone()
                if result:
                    start = datetime.fromisoformat(result[0])
                    return (datetime.now() - start).total_seconds()
                return 0

    async def update_user_message(
        self, user_id: int, username: str = None, user_link: str = None
    ):
        now = datetime.now().isoformat()
        async with aiosqlite.connect(self.db_path) as conn:
            await conn.execute(
                """
                INSERT INTO user_stats (user_id, username, user_link, first_seen, last_message, messages_count)
                VALUES (?, ?, ?, ?, ?, 1)
                ON CONFLICT(user_id) DO UPDATE SET
                    username = COALESCE(?, username),
                    user_link = COALESCE(?, user_link),
                    last_message = ?,
                    messages_count = messages_count + 1
            """,
                (user_id, username, user_link, now, now, username, user_link, now),
            )
            await conn.commit()

    async def mark_auto_reply_sent(self, user_id: int, reply_text: str):
        now = datetime.now().isoformat()
        async with aiosqlite.connect(self.db_path) as conn:
            await conn.execute(
                """
                UPDATE user_stats
                SET received_auto_reply = received_auto_reply + 1,
                    last_auto_reply = ?
                WHERE user_id = ?
            """,
                (now, user_id),
            )

            await conn.execute(
                """
                INSERT INTO auto_reply_history (user_id, reply_text, sent_at)
                VALUES (?, ?, ?)
            """,
                (user_id, reply_text, now),
            )
            await conn.commit()

    async def get_user_stats(self, user_id: int) -> Optional[Dict]:
        async with aiosqlite.connect(self.db_path) as conn:
            conn.row_factory = aiosqlite.Row
            async with conn.execute(
                "SELECT * FROM user_stats WHERE user_id = ?", (user_id,)
            ) as cursor:
                row = await cursor.fetchone()
                return dict(row) if row else None

    async def get_users_count(self) -> int:
        async with aiosqlite.connect(self.db_path) as conn:
            async with conn.execute("SELECT COUNT(*) FROM user_stats") as cursor:
                result = await cursor.fetchone()
                return result[0] if result else 0

    async def get_top_users(self, limit: int = 10) -> List[Dict]:
        async with aiosqlite.connect(self.db_path) as conn:
            async with conn.execute(
                """
                SELECT user_id, username, user_link, messages_count, received_auto_reply
                FROM user_stats
                ORDER BY messages_count DESC
                LIMIT ?
            """,
                (limit,),
            ) as cursor:
                rows = await cursor.fetchall()
                return [
                    {
                        "user_id": row[0],
                        "username": row[1] or f"user_{row[0]}",
                        "user_link": row[2] or f"tg://user?id={row[0]}",
                        "messages": row[3],
                        "auto_replies": row[4],
                    }
                    for row in rows
                ]

    async def log_command(self, command: str, user_id: int):
        async with aiosqlite.connect(self.db_path) as conn:
            await conn.execute(
                """
                INSERT INTO command_history (command, user_id, executed_at)
                VALUES (?, ?, ?)
            """,
                (command, user_id, datetime.now().isoformat()),
            )
            await conn.commit()

    async def get_command_stats(self, limit: int = 20) -> List[Dict]:
        async with aiosqlite.connect(self.db_path) as conn:
            async with conn.execute(
                """
                SELECT command, COUNT(*) as count
                FROM command_history
                GROUP BY command
                ORDER BY count DESC
                LIMIT ?
            """,
                (limit,),
            ) as cursor:
                rows = await cursor.fetchall()
                return [{"command": row[0], "count": row[1]} for row in rows]

    async def get_recent_commands(self, limit: int = 10) -> List[Dict]:
        async with aiosqlite.connect(self.db_path) as conn:
            async with conn.execute(
                """
                SELECT command, user_id, executed_at
                FROM command_history
                ORDER BY executed_at DESC
                LIMIT ?
            """,
                (limit,),
            ) as cursor:
                rows = await cursor.fetchall()
                return [
                    {"command": row[0], "user_id": row[1], "time": row[2]}
                    for row in rows
                ]

    async def log_rp_action(
        self, user_id: int, target_id: int, action: str, custom_text: str = None
    ):
        async with aiosqlite.connect(self.db_path) as conn:
            await conn.execute(
                """
                INSERT INTO rp_history (user_id, target_id, action, custom_text, executed_at)
                VALUES (?, ?, ?, ?, ?)
            """,
                (user_id, target_id, action, custom_text, datetime.now().isoformat()),
            )
            await conn.commit()

    async def get_rp_stats(self, limit: int = 10) -> List[Dict]:
        async with aiosqlite.connect(self.db_path) as conn:
            async with conn.execute(
                """
                SELECT action, COUNT(*) as count
                FROM rp_history
                GROUP BY action
                ORDER BY count DESC
                LIMIT ?
            """,
                (limit,),
            ) as cursor:
                rows = await cursor.fetchall()
                return [{"action": row[0], "count": row[1]} for row in rows]

    async def get_auto_reply_stats(self, limit: int = 20) -> List[Dict]:
        async with aiosqlite.connect(self.db_path) as conn:
            async with conn.execute(
                """
                SELECT user_id, reply_text, sent_at
                FROM auto_reply_history
                ORDER BY sent_at DESC
                LIMIT ?
            """,
                (limit,),
            ) as cursor:
                rows = await cursor.fetchall()
                return [
                    {"user_id": row[0], "reply": row[1][:50], "time": row[2]}
                    for row in rows
                ]

    async def reset_all_stats(self):
        async with aiosqlite.connect(self.db_path) as conn:
            await conn.execute(
                """
                UPDATE stats SET
                    total_messages = 0,
                    auto_replies_sent = 0,
                    rp_actions_used = 0,
                    jokes_sent = 0,
                    memes_sent = 0,
                    commands_used = 0,
                    away_mode_toggled = 0,
                    start_time = ?,
                    updated_at = ?
                WHERE id = 1
            """,
                (datetime.now().isoformat(), datetime.now().isoformat()),
            )

            await conn.execute("DELETE FROM user_stats")
            await conn.execute("DELETE FROM command_history")
            await conn.execute("DELETE FROM auto_reply_history")
            await conn.execute("DELETE FROM rp_history")
            await conn.commit()

    async def clear_old_history(self, days: int = 30):
        from datetime import timedelta

        cutoff = (datetime.now() - timedelta(days=days)).isoformat()

        async with aiosqlite.connect(self.db_path) as conn:
            await conn.execute(
                "DELETE FROM command_history WHERE executed_at < ?", (cutoff,)
            )
            await conn.execute(
                "DELETE FROM auto_reply_history WHERE sent_at < ?", (cutoff,)
            )
            await conn.execute(
                "DELETE FROM rp_history WHERE executed_at < ?", (cutoff,)
            )
            await conn.commit()

    async def get_full_stats(self) -> Dict[str, Any]:
        stats = await self.get_stats()
        stats["uptime_seconds"] = await self.get_uptime_seconds()
        stats["users_count"] = await self.get_users_count()
        stats["top_users"] = await self.get_top_users(5)
        stats["top_commands"] = await self.get_command_stats(5)
        stats["top_rp_actions"] = await self.get_rp_stats(5)
        return stats


db = Database()

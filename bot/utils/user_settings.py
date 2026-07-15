import aiosqlite
import os
from config import NSFW_ENABLED_BY_DEFAULT
from typing import Dict

DB_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "user_settings.db"
)


class UserSettingsDB:
    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path

    async def init_db(self):
        async with aiosqlite.connect(self.db_path) as conn:
            await conn.execute(f"""
                CREATE TABLE IF NOT EXISTS user_nsfw_settings (
                    user_id INTEGER PRIMARY KEY,
                    nsfw_enabled INTEGER DEFAULT {NSFW_ENABLED_BY_DEFAULT},
                    updated_at TEXT NOT NULL
                )
            """)
            await conn.commit()

    async def get_nsfw_setting(self, user_id: int) -> bool:
        async with aiosqlite.connect(self.db_path) as conn:
            async with conn.execute(
                "SELECT nsfw_enabled FROM user_nsfw_settings WHERE user_id = ?",
                (user_id,),
            ) as cursor:
                result = await cursor.fetchone()
                if result:
                    return bool(result[0])
                return False

    async def set_nsfw_setting(self, user_id: int, enabled: bool) -> None:
        from datetime import datetime

        async with aiosqlite.connect(self.db_path) as conn:
            now = datetime.now().isoformat()
            await conn.execute(
                """
                INSERT INTO user_nsfw_settings (user_id, nsfw_enabled, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(user_id) DO UPDATE SET
                    nsfw_enabled = ?,
                    updated_at = ?
            """,
                (user_id, int(enabled), now, int(enabled), now),
            )
            await conn.commit()

    async def get_stats(self) -> Dict:
        async with aiosqlite.connect(self.db_path) as conn:
            async with conn.execute(
                "SELECT COUNT(*) FROM user_nsfw_settings"
            ) as cursor:
                total_row = await cursor.fetchone()
                total = total_row[0] if total_row else 0

            async with conn.execute(
                "SELECT COUNT(*) FROM user_nsfw_settings WHERE nsfw_enabled = 1"
            ) as cursor:
                enabled_row = await cursor.fetchone()
                enabled = enabled_row[0] if enabled_row else 0

            return {
                "total_users": total,
                "nsfw_enabled": enabled,
                "nsfw_disabled": total - enabled,
            }


user_settings_db = UserSettingsDB()

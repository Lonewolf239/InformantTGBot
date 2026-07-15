import aiosqlite
import logging
import os

logger = logging.getLogger(__name__)

DB_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "owner_settings.db"
)


class OwnerSettingsDB:
    def __init__(self):
        self.db_path = DB_PATH
        self.default_settings = {
            "payments_enabled": 1,
            "auto_reply_enabled": 1,
            "reply_to_owner": 0,
        }

    async def init_db(self):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS owner_settings (
                    setting_key TEXT PRIMARY KEY,
                    setting_value INTEGER
                )
            """)
            for key, val in self.default_settings.items():
                await db.execute(
                    "INSERT OR IGNORE INTO owner_settings (setting_key, setting_value) VALUES (?, ?)",
                    (key, val),
                )
            await db.commit()
        logger.info("⚙️ База данных настроек владельца инициализирована.")

    async def get_setting(self, key: str) -> bool:
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(
                "SELECT setting_value FROM owner_settings WHERE setting_key = ?", (key,)
            ) as cursor:
                row = await cursor.fetchone()
                if row:
                    return bool(row[0])
                return bool(self.default_settings.get(key, 0))

    async def toggle_setting(self, key: str) -> bool:
        current_val = await self.get_setting(key)
        new_val = 0 if current_val else 1
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "UPDATE owner_settings SET setting_value = ? WHERE setting_key = ?",
                (new_val, key),
            )
            await db.commit()
        return bool(new_val)

    async def get_all_settings(self) -> dict:
        settings = {}
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(
                "SELECT setting_key, setting_value FROM owner_settings"
            ) as cursor:
                rows = await cursor.fetchall()
                for row in rows:
                    settings[row[0]] = bool(row[1])
        return settings


owner_settings_db = OwnerSettingsDB()

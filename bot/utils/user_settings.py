import sqlite3
import os
from config import NSFW_ENABLED_BY_DEFAULT
from typing import Dict, Optional

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'user_settings.db')

class UserSettingsDB:
    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        self._init_db()

    def _get_connection(self):
        return sqlite3.connect(self.db_path)

    def _init_db(self):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(f'''
                CREATE TABLE IF NOT EXISTS user_nsfw_settings (
                    user_id INTEGER PRIMARY KEY,
                    nsfw_enabled INTEGER DEFAULT {NSFW_ENABLED_BY_DEFAULT},
                    updated_at TEXT NOT NULL
                )
            ''')
            conn.commit()

    def get_nsfw_setting(self, user_id: int) -> bool:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT nsfw_enabled FROM user_nsfw_settings WHERE user_id = ?",
                (user_id,)
            )
            result = cursor.fetchone()
            if result:
                return bool(result[0])
            return False

    def set_nsfw_setting(self, user_id: int, enabled: bool) -> None:
        from datetime import datetime
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO user_nsfw_settings (user_id, nsfw_enabled, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(user_id) DO UPDATE SET
                    nsfw_enabled = ?,
                    updated_at = ?
            ''', (user_id, int(enabled), datetime.now().isoformat(), int(enabled), datetime.now().isoformat()))
            conn.commit()

    def get_stats(self) -> Dict:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM user_nsfw_settings")
            total = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(*) FROM user_nsfw_settings WHERE nsfw_enabled = 1")
            enabled = cursor.fetchone()[0]
            return {
                "total_users": total,
                "nsfw_enabled": enabled,
                "nsfw_disabled": total - enabled
            }


user_settings_db = UserSettingsDB()

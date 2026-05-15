import sqlite3
import os
import json
from datetime import datetime
from typing import Dict, List, Optional, Any
import logging

logger = logging.getLogger(__name__)

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'bot_stats.db')

class Database:
    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        self._init_db()

    def _get_connection(self):
        return sqlite3.connect(self.db_path)

    def _init_db(self):
        with self._get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute('''
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
            ''')

            cursor.execute('''
                CREATE TABLE IF NOT EXISTS user_stats (
                    user_id INTEGER PRIMARY KEY,
                    first_seen TEXT NOT NULL,
                    last_message TEXT NOT NULL,
                    messages_count INTEGER DEFAULT 0,
                    received_auto_reply INTEGER DEFAULT 0,
                    last_auto_reply TEXT
                )
            ''')

            cursor.execute('''
                CREATE TABLE IF NOT EXISTS command_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    command TEXT NOT NULL,
                    user_id INTEGER NOT NULL,
                    executed_at TEXT NOT NULL
                )
            ''')

            cursor.execute('''
                CREATE TABLE IF NOT EXISTS auto_reply_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    reply_text TEXT NOT NULL,
                    sent_at TEXT NOT NULL
                )
            ''')

            cursor.execute('''
                CREATE TABLE IF NOT EXISTS rp_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    target_id INTEGER NOT NULL,
                    action TEXT NOT NULL,
                    custom_text TEXT,
                    executed_at TEXT NOT NULL
                )
            ''')

            cursor.execute("SELECT id FROM stats WHERE id = 1")
            if not cursor.fetchone():
                cursor.execute('''
                    INSERT INTO stats (id, start_time, updated_at)
                    VALUES (1, ?, ?)
                ''', (datetime.now().isoformat(), datetime.now().isoformat()))

            conn.commit()

    def get_total_messages(self) -> int:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT total_messages FROM stats WHERE id = 1")
            result = cursor.fetchone()
            return result[0] if result else 0

    def increment_total_messages(self):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE stats 
                SET total_messages = total_messages + 1,
                    updated_at = ?
                WHERE id = 1
            ''', (datetime.now().isoformat(),))
            conn.commit()

    def increment_auto_replies(self):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE stats 
                SET auto_replies_sent = auto_replies_sent + 1,
                    updated_at = ?
                WHERE id = 1
            ''', (datetime.now().isoformat(),))
            conn.commit()

    def increment_rp_actions(self):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE stats 
                SET rp_actions_used = rp_actions_used + 1,
                    updated_at = ?
                WHERE id = 1
            ''', (datetime.now().isoformat(),))
            conn.commit()

    def increment_jokes(self):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE stats 
                SET jokes_sent = jokes_sent + 1,
                    updated_at = ?
                WHERE id = 1
            ''', (datetime.now().isoformat(),))
            conn.commit()

    def increment_memes(self):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE stats 
                SET memes_sent = memes_sent + 1,
                    updated_at = ?
                WHERE id = 1
            ''', (datetime.now().isoformat(),))
            conn.commit()

    def increment_commands(self):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE stats 
                SET commands_used = commands_used + 1,
                    updated_at = ?
                WHERE id = 1
            ''', (datetime.now().isoformat(),))
            conn.commit()

    def increment_away_toggled(self):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE stats 
                SET away_mode_toggled = away_mode_toggled + 1,
                    updated_at = ?
                WHERE id = 1
            ''', (datetime.now().isoformat(),))
            conn.commit()

    def get_stats(self) -> Dict[str, Any]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM stats WHERE id = 1")
            row = cursor.fetchone()
            if row:
                columns = [description[0] for description in cursor.description]
                return dict(zip(columns, row))
            return {}

    def get_uptime_seconds(self) -> float:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT start_time FROM stats WHERE id = 1")
            result = cursor.fetchone()
            if result:
                start = datetime.fromisoformat(result[0])
                return (datetime.now() - start).total_seconds()
            return 0

    def update_user_message(self, user_id: int):
        now = datetime.now().isoformat()
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO user_stats (user_id, first_seen, last_message, messages_count)
                VALUES (?, ?, ?, 1)
                ON CONFLICT(user_id) DO UPDATE SET
                    last_message = ?,
                    messages_count = messages_count + 1
            ''', (user_id, now, now, now))
            conn.commit()
    
    def mark_auto_reply_sent(self, user_id: int, reply_text: str):
        now = datetime.now().isoformat()
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE user_stats 
                SET received_auto_reply = received_auto_reply + 1,
                    last_auto_reply = ?
                WHERE user_id = ?
            ''', (now, user_id))

            cursor.execute('''
                INSERT INTO auto_reply_history (user_id, reply_text, sent_at)
                VALUES (?, ?, ?)
            ''', (user_id, reply_text, now))
            conn.commit()

    def get_user_stats(self, user_id: int) -> Optional[Dict]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM user_stats WHERE user_id = ?", (user_id,))
            row = cursor.fetchone()
            if row:
                columns = [description[0] for description in cursor.description]
                return dict(zip(columns, row))
            return None

    def get_users_count(self) -> int:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM user_stats")
            result = cursor.fetchone()
            return result[0] if result else 0

    def get_top_users(self, limit: int = 10) -> List[Dict]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT user_id, messages_count, received_auto_reply
                FROM user_stats
                ORDER BY messages_count DESC
                LIMIT ?
            ''', (limit,))
            rows = cursor.fetchall()
            return [{"user_id": row[0], "messages": row[1], "auto_replies": row[2]} for row in rows]

    def log_command(self, command: str, user_id: int):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO command_history (command, user_id, executed_at)
                VALUES (?, ?, ?)
            ''', (command, user_id, datetime.now().isoformat()))
            conn.commit()

    def get_command_stats(self, limit: int = 20) -> List[Dict]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT command, COUNT(*) as count
                FROM command_history
                GROUP BY command
                ORDER BY count DESC
                LIMIT ?
            ''', (limit,))
            rows = cursor.fetchall()
            return [{"command": row[0], "count": row[1]} for row in rows]

    def get_recent_commands(self, limit: int = 10) -> List[Dict]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT command, user_id, executed_at
                FROM command_history
                ORDER BY executed_at DESC
                LIMIT ?
            ''', (limit,))
            rows = cursor.fetchall()
            return [{"command": row[0], "user_id": row[1], "time": row[2]} for row in rows]

    def log_rp_action(self, user_id: int, target_id: int, action: str, custom_text: str = None):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO rp_history (user_id, target_id, action, custom_text, executed_at)
                VALUES (?, ?, ?, ?, ?)
            ''', (user_id, target_id, action, custom_text, datetime.now().isoformat()))
            conn.commit()

    def get_rp_stats(self, limit: int = 10) -> List[Dict]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT action, COUNT(*) as count
                FROM rp_history
                GROUP BY action
                ORDER BY count DESC
                LIMIT ?
            ''', (limit,))
            rows = cursor.fetchall()
            return [{"action": row[0], "count": row[1]} for row in rows]

    def get_auto_reply_stats(self, limit: int = 20) -> List[Dict]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT user_id, reply_text, sent_at
                FROM auto_reply_history
                ORDER BY sent_at DESC
                LIMIT ?
            ''', (limit,))
            rows = cursor.fetchall()
            return [{"user_id": row[0], "reply": row[1][:50], "time": row[2]} for row in rows]

    def reset_all_stats(self):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
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
            ''', (datetime.now().isoformat(), datetime.now().isoformat()))

            cursor.execute("DELETE FROM user_stats")
            cursor.execute("DELETE FROM command_history")
            cursor.execute("DELETE FROM auto_reply_history")
            cursor.execute("DELETE FROM rp_history")
            conn.commit()

    def clear_old_history(self, days: int = 30):
        from datetime import timedelta
        cutoff = (datetime.now() - timedelta(days=days)).isoformat()

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM command_history WHERE executed_at < ?", (cutoff,))
            cursor.execute("DELETE FROM auto_reply_history WHERE sent_at < ?", (cutoff,))
            cursor.execute("DELETE FROM rp_history WHERE executed_at < ?", (cutoff,))
            conn.commit()

    def get_full_stats(self) -> Dict[str, Any]:
        stats = self.get_stats()
        stats["uptime_seconds"] = self.get_uptime_seconds()
        stats["users_count"] = self.get_users_count()
        stats["top_users"] = self.get_top_users(5)
        stats["top_commands"] = self.get_command_stats(5)
        stats["top_rp_actions"] = self.get_rp_stats(5)
        return stats


db = Database()

import aiosqlite
import datetime
import logging
import os
from config import DEFAULT_DAILY_TOKENS

logger = logging.getLogger(__name__)

DB_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "bot_tokens.db"
)


class TokensDB:
    def __init__(self, default_daily_tokens=100):
        self.default_tokens = default_daily_tokens

    async def init_db(self):
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("PRAGMA journal_mode=WAL;")
            await db.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    tokens INTEGER,
                    last_reset_date TEXT
                )
            """)
            await db.commit()

    def _get_today_str(self):
        return datetime.date.today().isoformat()

    async def get_balance(self, user_id: int) -> int:
        today = self._get_today_str()

        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute(
                "SELECT tokens, last_reset_date FROM users WHERE user_id = ?",
                (user_id,),
            ) as cursor:
                row = await cursor.fetchone()

            if not row:
                await db.execute(
                    "INSERT INTO users (user_id, tokens, last_reset_date) VALUES (?, ?, ?)",
                    (user_id, self.default_tokens, today),
                )
                await db.commit()
                return self.default_tokens

            tokens, last_reset = row

            if last_reset != today:
                new_balance = max(tokens, self.default_tokens)
                await db.execute(
                    "UPDATE users SET tokens = ?, last_reset_date = ? WHERE user_id = ?",
                    (new_balance, today, user_id),
                )
                await db.commit()
                return new_balance

            return tokens

    async def spend_tokens(self, user_id: int, amount: int) -> bool:
        if amount <= 0:
            return True

        await self.get_balance(user_id)

        async with aiosqlite.connect(DB_PATH) as db:
            cursor = await db.execute(
                "UPDATE users SET tokens = tokens - ? WHERE user_id = ? AND tokens >= ?",
                (amount, user_id, amount),
            )
            await db.commit()

            return cursor.rowcount > 0

    async def has_enough_tokens(self, user_id: int, amount: int) -> bool:
        balance = await self.get_balance(user_id)
        return balance >= amount

    async def add_tokens(self, user_id: int, amount: int):
        await self.get_balance(user_id)
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                "UPDATE users SET tokens = tokens + ? WHERE user_id = ?",
                (amount, user_id),
            )
            await db.commit()

    async def penalize_user(self, user_id: int, penalty_amount: int = 10) -> str:
        balance = await self.get_balance(user_id)

        if balance >= penalty_amount:
            async with aiosqlite.connect(DB_PATH) as db:
                await db.execute(
                    "UPDATE users SET tokens = tokens - ? WHERE user_id = ?",
                    (penalty_amount, user_id),
                )
                await db.commit()
            return f"Штраф! Списано {penalty_amount} токенов."
        else:
            tomorrow = (datetime.date.today() + datetime.timedelta(days=1)).isoformat()

            async with aiosqlite.connect(DB_PATH) as db:
                await db.execute(
                    "UPDATE users SET tokens = 0, last_reset_date = ? WHERE user_id = ?",
                    (tomorrow, user_id),
                )
                await db.commit()
            return (
                "Штраф! Баланс обнулен, а ежедневное пополнение заморожено на 24 часа."
            )


tokens_db = TokensDB(default_daily_tokens=DEFAULT_DAILY_TOKENS)

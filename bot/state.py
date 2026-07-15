from datetime import datetime
from typing import Dict, List, Optional, Set
import asyncio


class BotState:
    def __init__(self):
        self._is_away_mode = False
        self._users_received_auto_reply: Set[int] = set()
        self._awaiting_users: Dict[int, dict] = {}
        self._lock = asyncio.Lock()

    @property
    async def is_away_mode(self):
        async with self._lock:
            return self._is_away_mode

    async def set_away_mode(self, value: bool):
        async with self._lock:
            self._is_away_mode = value
            if value:
                pass
            else:
                self._users_received_auto_reply.clear()
                self._awaiting_users.clear()

    async def add_awaiting_user(
        self, user_id: int, first_name: str, username: Optional[str] = None
    ):
        async with self._lock:
            if user_id not in self._awaiting_users:
                self._awaiting_users[user_id] = {
                    "user_id": user_id,
                    "name": first_name,
                    "username": username,
                    "first_msg_time": datetime.now(),
                }

    async def remove_awaiting_user(self, user_id: int):
        async with self._lock:
            self._awaiting_users.pop(user_id, None)

    async def get_awaiting_users(self) -> List[dict]:
        async with self._lock:
            return list(self._awaiting_users.values())

    async def get_awaiting_users_count(self) -> int:
        async with self._lock:
            return len(self._awaiting_users)

    async def should_send_auto_reply(self, user_id: int) -> bool:
        async with self._lock:
            if not self._is_away_mode:
                return False

            if user_id in self._users_received_auto_reply:
                return False

            self._users_received_auto_reply.add(user_id)
            return True

    async def mark_auto_reply_sent(self, user_id: int):
        async with self._lock:
            self._users_received_auto_reply.add(user_id)

    async def clear_user_status(self, user_id: int):
        async with self._lock:
            self._users_received_auto_reply.discard(user_id)
            self._awaiting_users.pop(user_id, None)

    async def reset_session(self):
        async with self._lock:
            self._users_received_auto_reply.clear()
            self._awaiting_users.clear()

    async def get_stats(self):
        async with self._lock:
            return {
                "is_away": self._is_away_mode,
                "auto_replied_count": len(self._users_received_auto_reply),
                "awaiting_count": len(self._awaiting_users),
            }


state = BotState()

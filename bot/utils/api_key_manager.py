import time
from typing import List
from config import GROQ_API_KEYS


class GroqKeyManager:
    def __init__(self, api_keys: List[str]):
        self.max_tokens_per_day = 100000
        self.ban_duration = 86400
        self.keys_state = {
            key: {
                "banned_until": 0.0,
                "tokens_used": 0,
                "reset_at": 0.0,
            }
            for key in api_keys
        }

    def get_available_keys(self) -> List[str]:
        now = time.time()
        available = []

        for key, state in self.keys_state.items():
            if state["reset_at"] == 0.0:
                pass
            elif now > state["reset_at"]:
                state["tokens_used"] = 0
                state["reset_at"] = 0.0

            if (
                now > state["banned_until"]
                and state["tokens_used"] < self.max_tokens_per_day
            ):
                available.append(key)

        return sorted(available, key=lambda k: self.keys_state[k]["tokens_used"])

    def ban_key(self, key: str):
        self.keys_state[key]["banned_until"] = time.time() + self.ban_duration

    def add_usage(self, key: str, tokens: int):
        now = time.time()
        state = self.keys_state[key]

        if state["reset_at"] == 0.0 or now > state["reset_at"]:
            state["tokens_used"] = 0
            state["reset_at"] = now + self.ban_duration

        state["tokens_used"] += tokens


key_manager = GroqKeyManager(GROQ_API_KEYS)

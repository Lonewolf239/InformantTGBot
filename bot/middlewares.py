from typing import Callable, Dict, Any, Awaitable
from aiogram import BaseMiddleware
from aiogram.types import Message
import logging
import time

logger = logging.getLogger(__name__)


class LoggingMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[Message, Dict[str, Any]], Awaitable[Any]],
        event: Message,
        data: Dict[str, Any],
    ) -> Any:
        user = event.from_user
        start_time = time.time()
        logger.info(f"📨 {user.id} ({user.first_name}): {event.text}")
        try:
            result = await handler(event, data)
            elapsed = (time.time() - start_time) * 1000
            logger.info(f"✅ Обработано за {elapsed:.2f}ms")
            return result
        except Exception as e:
            logger.error(f"❌ Ошибка: {e}", exc_info=True)
            raise

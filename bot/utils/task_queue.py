import asyncio
import logging
from typing import Callable, Any, Optional, Dict, Tuple
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class QueueTask:
    func: Callable
    args: tuple
    kwargs: dict
    future: asyncio.Future
    update_cb: Optional[Callable[[int], Any]] = None


class UniversalQueueManager:
    def __init__(self):
        self.queues: Dict[str, asyncio.Queue] = {}
        self.workers: Dict[str, list[asyncio.Task]] = {}

    def register_queue(self, queue_name: str, concurrency: int = 1):
        if queue_name not in self.queues:
            self.queues[queue_name] = asyncio.Queue()
            self.workers[queue_name] = [
                asyncio.create_task(self._worker(queue_name)) 
                for _ in range(concurrency)
            ]
            logger.info(f"✅ Очередь '{queue_name}' запущена (потоков: {concurrency})")

    async def add_task(self, queue_name: str, func: Callable, *args, update_cb=None, **kwargs) -> Tuple[asyncio.Future, int]:
        if queue_name not in self.queues:
            self.register_queue(queue_name)

        future = asyncio.get_event_loop().create_future()
        task = QueueTask(func=func, args=args, kwargs=kwargs, future=future, update_cb=update_cb)

        queue = self.queues[queue_name]
        queue.put_nowait(task)
        position = queue.qsize()

        return future, position

    async def _worker(self, queue_name: str):
        queue = self.queues[queue_name]
        while True:
            try:
                task: QueueTask = await queue.get()

                if task.update_cb:
                    asyncio.create_task(task.update_cb(0))

                await self._notify_positions(queue)

                try:
                    result = await task.func(*task.args, **task.kwargs)
                    if not task.future.done():
                        task.future.set_result(result)
                except Exception as e:
                    logger.exception(f"Ошибка при выполнении задачи в очереди {queue_name}")
                    if not task.future.done():
                        task.future.set_exception(e)

                queue.task_done()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.exception(f"Сбой воркера {queue_name}")
                await asyncio.sleep(1)

    async def _notify_positions(self, queue: asyncio.Queue):
        for i, queued_task in enumerate(list(queue._queue), start=1):
            if queued_task.update_cb:
                try: asyncio.create_task(queued_task.update_cb(i))
                except Exception: pass


queue_manager = UniversalQueueManager()

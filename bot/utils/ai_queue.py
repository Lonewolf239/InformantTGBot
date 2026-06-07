import asyncio
import logging
from typing import Optional, Tuple, Any, Callable, Awaitable
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class TaskType(Enum):
    AI = "ai"
    WHISPER = "whisper"


@dataclass
class QueueTask:
    task_type: TaskType
    data: Any
    future: asyncio.Future
    user_id: int
    update_cb: Optional[Callable[[int], Awaitable[None]]] = None


class NeuralNetworkQueue:
    def __init__(self):
        self.ai_queue: asyncio.Queue[QueueTask] = asyncio.Queue(maxsize=100)
        self.whisper_queue: asyncio.Queue[QueueTask] = asyncio.Queue(maxsize=50)
        self.worker_tasks = []
        self.is_running = False

    def start(self):
        if not self.is_running:
            self.is_running = True
            self.worker_tasks = [
                asyncio.create_task(self._worker(self.ai_queue, TaskType.AI)),
                asyncio.create_task(self._worker(self.whisper_queue, TaskType.WHISPER))
            ]
            logger.info("✅ Воркеры нейросетей запущены (раздельные очереди)")

    async def stop(self):
        self.is_running = False
        for task in self.worker_tasks:
            task.cancel()
        logger.info("🛑 Воркеры нейросетей остановлены")

    async def add_task(self, task_type: TaskType, data: Any, user_id: int, update_cb=None) -> Tuple[asyncio.Future, int]:
        future = asyncio.get_event_loop().create_future()
        task = QueueTask(
            task_type=task_type,
            data=data,
            future=future,
            user_id=user_id,
            update_cb=update_cb
        )

        target_queue = self.ai_queue if task_type == TaskType.AI else self.whisper_queue

        target_queue.put_nowait(task)
        position = target_queue.qsize() 

        return future, position

    async def _worker(self, queue: asyncio.Queue, worker_type: TaskType):
        while self.is_running:
            try:
                task = await queue.get()

                if task.update_cb:
                    asyncio.create_task(task.update_cb(0))

                await self._notify_positions(queue)

                await self._process_task(task)

                queue.task_done()
            except asyncio.CancelledError:
                logger.info(f"Воркер {worker_type.value} отменен")
                break
            except Exception as e:
                logger.exception(f"Критическая ошибка в главном цикле воркера {worker_type.value}")
                await asyncio.sleep(1)

    async def _notify_positions(self, queue: asyncio.Queue):
        for i, queued_task in enumerate(list(queue._queue), start=1):
            if queued_task.update_cb:
                try:
                    asyncio.create_task(queued_task.update_cb(i))
                except Exception:
                    pass

    async def _process_task(self, task: QueueTask):
        try:
            logger.info(f"🔄 Обработка задачи: {task.task_type.value} от user {task.user_id}")

            if task.task_type == TaskType.AI:
                from bot.utils.ai_api import ask_local_ai
                result = await ask_local_ai(task.data["prompt"], task.data.get("system_prompt"))
            elif task.task_type == TaskType.WHISPER:
                from bot.utils.whisper_stt import transcribe_audio
                result = await transcribe_audio(
                    task.data["file_path"],
                    task.data.get("language", "auto"),
                    task.data.get("task", "transcribe")
                )
            else:
                result = None

            if not task.future.done():
                task.future.set_result(result)

        except Exception as e:
            logger.exception(f"Ошибка при выполнении задачи {task.task_type.value}")
            if not task.future.done():
                task.future.set_exception(e)
        finally:
            logger.info(f"✅ Задача {task.task_type.value} завершена")


_neural_queue = NeuralNetworkQueue()


def get_queue() -> NeuralNetworkQueue:
    return _neural_queue


def ensure_queue_started():
    _neural_queue.start()

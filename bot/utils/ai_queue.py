import asyncio
import logging
from typing import Optional, Tuple, Any
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


class NeuralNetworkQueue:
    def __init__(self):
        self.queue: asyncio.Queue[QueueTask] = asyncio.Queue()
        self.ai_semaphore = asyncio.Semaphore(1)
        self.whisper_semaphore = asyncio.Semaphore(1)
        self.worker_task: Optional[asyncio.Task] = None
        self.is_running = False

    def start(self):
        if not self.is_running:
            self.is_running = True
            self.worker_task = asyncio.create_task(self._worker())
            logger.info("✅ Единый воркер нейросетей запущен")

    async def stop(self):
        self.is_running = False
        if self.worker_task:
            self.worker_task.cancel()
            try:
                await self.worker_task
            except asyncio.CancelledError:
                pass
            logger.info("🛑 Единый воркер нейросетей остановлен")

    async def add_task(self, task_type: TaskType, data: Any, user_id: int) -> Tuple[asyncio.Future, int]:
        future = asyncio.get_event_loop().create_future()
        task = QueueTask(
            task_type=task_type,
            data=data,
            future=future,
            user_id=user_id
        )
        await self.queue.put(task)

        position = self.queue.qsize() 

        return future, position

    async def _worker(self):
        while self.is_running:
            try:
                task = await self.queue.get()
                asyncio.create_task(self._process_task(task))
            except asyncio.CancelledError:
                logger.info("Воркер очереди отменен")
                break
            except Exception as e:
                logger.exception("Критическая ошибка в главном цикле воркера")
                await asyncio.sleep(1)

    async def _process_task(self, task: QueueTask):
        try:
            logger.info(f"🔄 Обработка задачи: {task.task_type.value} от user {task.user_id}")

            if task.task_type == TaskType.AI:
                async with self.ai_semaphore:
                    from bot.utils.ai_api import ask_local_ai
                    result = await ask_local_ai(task.data["prompt"], task.data.get("system_prompt"))

            elif task.task_type == TaskType.WHISPER:
                async with self.whisper_semaphore:
                    from bot.utils.whisper_stt import transcribe_audio
                    result = await transcribe_audio(
                        task.data["file_path"],
                        task.data.get("language", "auto"),
                        task.data.get("task", "transcribe")
                    )
            else:
                result = None
                logger.error(f"Неизвестный тип задачи: {task.task_type}")

            if not task.future.done():
                task.future.set_result(result)

        except Exception as e:
            logger.exception(f"Ошибка при выполнении задачи {task.task_type.value}")
            if not task.future.done():
                task.future.set_exception(e)
        finally:
            self.queue.task_done()
            logger.info(f"✅ Задача {task.task_type.value} завершена")


_neural_queue = NeuralNetworkQueue()


def get_queue() -> NeuralNetworkQueue:
    return _neural_queue


def ensure_queue_started():
    _neural_queue.start()

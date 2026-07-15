import asyncio
import logging
from typing import Optional
import whisper
from config import WHISPER_MODEL, WHISPER_TIMEOUT

logger = logging.getLogger(__name__)

_model_instance = None
_model_lock = asyncio.Lock()


async def get_whisper_model():
    global _model_instance
    async with _model_lock:
        if _model_instance is None:
            logger.info(f"🔄 Загрузка модели Whisper: {WHISPER_MODEL}...")
            loop = asyncio.get_event_loop()
            _model_instance = await loop.run_in_executor(
                None, lambda: whisper.load_model(WHISPER_MODEL)
            )
            logger.info(f"✅ Модель Whisper ({WHISPER_MODEL}) загружена!")
        return _model_instance


async def transcribe_audio(
    file_path: str, language: str = "auto", task: str = "transcribe"
) -> Optional[str]:
    try:
        model = await get_whisper_model()
        options = {
            "language": language if language != "auto" else None,
            "task": task,
            "fp16": False,
            "verbose": False,
        }
        loop = asyncio.get_event_loop()

        result = await asyncio.wait_for(
            loop.run_in_executor(None, lambda: model.transcribe(file_path, **options)),
            timeout=WHISPER_TIMEOUT,
        )
        transcribed_text = result.get("text", "").strip()

        if transcribed_text:
            logger.info(f"✅ Распознано {len(transcribed_text)} символов")
            return transcribed_text
        else:
            logger.warning("⚠️ Распознавание не дало результатов")
            return None

    except asyncio.TimeoutError:
        logger.error("❌ Whisper завис и был остановлен по таймауту")
        return None
    except Exception as e:
        logger.error(f"❌ Ошибка при распознавании речи: {e}", exc_info=True)
        return None

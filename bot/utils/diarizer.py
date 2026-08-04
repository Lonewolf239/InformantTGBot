import asyncio
import logging
from typing import List, Dict, Any
from pyannote.audio import Pipeline

logger = logging.getLogger(__name__)

_diarization_pipeline = None
_diarization_lock = asyncio.Lock()


async def get_diarization_pipeline(hf_token: str):
    global _diarization_pipeline
    async with _diarization_lock:
        if _diarization_pipeline is None:
            logger.info("🔄 Загрузка модели Pyannote Diarization...")
            loop = asyncio.get_event_loop()
            try:
                _diarization_pipeline = await loop.run_in_executor(
                    None,
                    lambda: Pipeline.from_pretrained(
                        "pyannote/speaker-diarization-3.1", token=hf_token
                    ),
                )
                logger.info("✅ Модель Pyannote загружена!")
            except Exception as e:
                logger.error(f"❌ Ошибка загрузки Pyannote: {e}")
                raise
        return _diarization_pipeline


def format_time(seconds: float) -> str:
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    if h > 0:
        return f"{h:02d}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"


def assign_speakers_to_segments(
    whisper_segments: List[Dict[str, Any]], diarization_result
) -> List[Dict[str, Any]]:
    for segment in whisper_segments:
        segment_start = segment["start"]
        segment_end = segment["end"]

        speaker_durations = {}

        annotation = getattr(
            diarization_result, "speaker_diarization", diarization_result
        )

        for turn, _, speaker in annotation.itertracks(yield_label=True):
            overlap_start = max(segment_start, turn.start)
            overlap_end = min(segment_end, turn.end)
            overlap_duration = max(0, overlap_end - overlap_start)

            if overlap_duration > 0:
                speaker_durations[speaker] = (
                    speaker_durations.get(speaker, 0) + overlap_duration
                )

        if speaker_durations:
            best_speaker = max(speaker_durations, key=speaker_durations.get)
            segment["speaker"] = best_speaker.replace("SPEAKER_", "Спикер ")
        else:
            segment["speaker"] = "Неизвестный спикер"

    return whisper_segments


async def perform_diarization(
    file_path: str, hf_token: str, speakers_mode: str = "auto"
):
    pipeline = await get_diarization_pipeline(hf_token)
    loop = asyncio.get_event_loop()

    def run_pipeline():
        if speakers_mode == "1":
            return pipeline(file_path, num_speakers=1)
        elif speakers_mode == "2-4":
            return pipeline(file_path, min_speakers=2, max_speakers=4)
        elif speakers_mode == "4-8":
            return pipeline(file_path, min_speakers=4, max_speakers=8)
        else:
            return pipeline(file_path)

    logger.info(f"🔄 Запуск диаризации (режим: {speakers_mode})...")
    diarization_result = await loop.run_in_executor(None, run_pipeline)
    logger.info("✅ Диаризация завершена!")
    return diarization_result

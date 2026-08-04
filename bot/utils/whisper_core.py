import asyncio
import logging
from typing import Optional
import whisper
import torch
import subprocess
import os

from config import WHISPER_MODEL, WHISPER_TIMEOUT, HF_TOKEN

from bot.utils.diarizer import (
    format_time,
    assign_speakers_to_segments,
    perform_diarization,
)

logger = logging.getLogger(__name__)

_model_instance = None
_model_lock = asyncio.Lock()


async def clean_audio_ffmpeg(file_path: str) -> str:
    cleaned_path = f"{file_path}_cleaned.wav"
    cmd = [
        "ffmpeg",
        "-y",
        "-i",
        file_path,
        "-af",
        "afftdn=nf=-25,silenceremove=stop_periods=-1:stop_duration=1:stop_threshold=-35dB",
        "-ac",
        "1",
        "-ar",
        "16000",
        cleaned_path,
    ]

    loop = asyncio.get_event_loop()
    try:
        logger.info("🔄 Очистка аудио от шумов (FFmpeg)...")
        await loop.run_in_executor(
            None,
            lambda: subprocess.run(
                cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True
            ),
        )
        logger.info("✅ Аудио успешно очищено!")
        return cleaned_path
    except subprocess.CalledProcessError as e:
        logger.error(f"❌ Ошибка FFmpeg при очистке: {e}")
        return file_path


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
    file_path: str,
    language: str = "auto",
    task: str = "transcribe",
    timestamps: bool = False,
    diarization: bool = False,
    speakers_mode: str = "auto",
) -> Optional[str]:
    processed_file_path = await clean_audio_ffmpeg(file_path)

    try:
        model = await get_whisper_model()
        options = {
            "language": language if language != "auto" else None,
            "task": task,
            "fp16": torch.cuda.is_available(),
            "verbose": False,
            "condition_on_previous_text": False,
            "no_speech_threshold": 0.6,
            "temperature": 0.0,
            "beam_size": 5,
            "compression_ratio_threshold": 2.4,
        }
        loop = asyncio.get_event_loop()

        logger.info("🔄 Запуск распознавания Whisper на очищенном аудио...")
        result = await asyncio.wait_for(
            loop.run_in_executor(
                None, lambda: model.transcribe(processed_file_path, **options)
            ),
            timeout=WHISPER_TIMEOUT,
        )

        if diarization and "segments" in result:
            diarization_result = await perform_diarization(
                processed_file_path, HF_TOKEN, speakers_mode
            )
            result["segments"] = assign_speakers_to_segments(
                result["segments"], diarization_result
            )
            timestamps = True

        if timestamps and "segments" in result:
            lines = []
            for segment in result["segments"]:
                start_str = format_time(segment["start"])
                end_str = format_time(segment["end"])
                text = segment["text"].strip()

                if diarization and "speaker" in segment:
                    speaker_prefix = f"[{segment['speaker']}] "
                else:
                    speaker_prefix = ""

                lines.append(f"[{start_str} - {end_str}] {speaker_prefix}{text}")
            transcribed_text = "\n".join(lines)
        else:
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
    finally:
        if processed_file_path != file_path and os.path.exists(processed_file_path):
            try:
                os.remove(processed_file_path)
            except Exception as e:
                logger.error(f"Ошибка при удалении очищенного файла: {e}")

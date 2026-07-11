import os
import logging
from aiogram import types
from aiogram.types import FSInputFile, BufferedInputFile
import mutagen
import random
from mutagen.id3 import ID3

logger = logging.getLogger(__name__)

ASSETS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "assets")


def extract_audio_metadata(file_path: str) -> dict:
    metadata = {
        "title": None,
        "artist": None,
        "duration": None,
        "cover_bytes": None
    }

    try:
        audio = mutagen.File(file_path)
        if audio is not None and audio.info:
            metadata["duration"] = int(audio.info.length)

        if file_path.lower().endswith('.mp3'):
            tags = ID3(file_path)

            if "TIT2" in tags:
                metadata["title"] = tags.get("TIT2").text[0]

            if "TPE1" in tags:
                metadata["artist"] = tags.get("TPE1").text[0]

            apic_tags = tags.getall("APIC")
            if apic_tags:
                metadata["cover_bytes"] = apic_tags[0].data

    except Exception as e:
        logger.error(f"Ошибка при чтении метаданных файла {file_path}: {e}")

    return metadata


async def send_track(message: types.Message, file_name: str, title: str, performer: str):
    file_path = os.path.join(ASSETS_DIR, file_name)

    if not os.path.exists(file_path):
        logger.error(f"Файл не найден: {file_path}")
        return False

    metadata = extract_audio_metadata(file_path)

    audio_file = FSInputFile(file_path)

    thumbnail = None
    if metadata.get("cover_bytes"):
        thumbnail = BufferedInputFile(metadata["cover_bytes"], filename="cover.jpg")

    audio_title = metadata.get("title") or title
    audio_performer = metadata.get("artist") or performer
    duration = metadata.get("duration") or 0

    await message.answer_audio(
        audio=audio_file,
        title=audio_title,
        performer=audio_performer,
        thumbnail=thumbnail,
        duration=duration
    )
    return True


async def send_party_track(message: types.Message):
    return await send_track(message, "red_sun.mp3", "Red Sun in the Sky", "Mao Ze Dong")


async def send_cool_ringtone(message: types.Message):
    return await send_track(message, "cool_ringtone.mp3", "Cool Ringtone", "Unknown")


async def send_social_credit_plus(message: types.Message):
    images = [
        "sc_plus_15.png",
        "sc_plus_30m.jpg",
        "sc_plus_cena.jpg",
        "sc_plus_100m.jpg",
        "sc_plus_1b.jpg",
        "sc_plus_69420.jpg",
        "sc_plus_infinity.jpg",
        "sc_plus_rice.webp",
        "sc_plus_rice2.jpg"
    ]
    filename = random.choice(images)
    file_path = os.path.join(ASSETS_DIR, filename)

    if not os.path.exists(file_path):
        logger.error(f"Файл не найден: {file_path}")
        return False

    photo = FSInputFile(file_path)
    await message.answer_photo(photo)
    return True


async def send_social_credit_minus(message: types.Message):
    images = [
        "sc_minus_15.jpg", 
        "sc_minus_death.jpg",
        "sc_minus_1.jpg",
        "sc_minus_16m.jpg",
        "sc_minus_50.jpg",
        "sc_minus_420m.jpg"
    ]
    filename = random.choice(images)
    file_path = os.path.join(ASSETS_DIR, filename)

    if not os.path.exists(file_path):
        logger.error(f"Файл не найден: {file_path}")
        return False

    photo = FSInputFile(file_path)
    await message.answer_photo(photo)
    return True

KEYWORD_COMMANDS_REGISTRY = {
    "send_party_track": send_party_track,
    "send_social_credit_plus": send_social_credit_plus,
    "send_social_credit_minus": send_social_credit_minus,
    "send_cool_ringtone": send_cool_ringtone,
}

import asyncio
import logging
from functools import lru_cache
from deep_translator import GoogleTranslator
import edge_tts

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def get_supported_langs():
    return GoogleTranslator().get_supported_languages(as_dict=True)


def resolve_lang_code(user_input: str) -> str:
    user_input = user_input.strip().lower()
    langs_dict = get_supported_langs()

    if user_input in langs_dict.values():
        return user_input

    try:
        translated_name = (
            GoogleTranslator(source="auto", target="en").translate(user_input).lower()
        )
        if translated_name in langs_dict:
            return langs_dict[translated_name]
        for lang_name, lang_code in langs_dict.items():
            if translated_name in lang_name:
                return lang_code
    except Exception as e:
        logger.warning(f"Не удалось распознать язык: {user_input}. Ошибка: {e}")

    return "ru"


async def translate_text(text: str, target_lang: str = "ru") -> str:
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(
        None,
        lambda: GoogleTranslator(source="auto", target=target_lang).translate(text),
    )


async def text_to_speech(text: str, output_path: str, lang_code: str = "ru") -> bool:
    if not text or not text.strip():
        logger.warning("⚠️ Попытка озвучить пустой текст")
        return False

    safe_lang_code = lang_code.lower()
    voices = {
        "ru": "ru-RU-DmitryNeural",
        "en": "en-US-ChristopherNeural",
        "zh": "zh-CN-YunxiNeural",
        "zh-cn": "zh-CN-YunxiNeural",
        "zh-tw": "zh-CN-YunxiNeural",
        "de": "de-DE-KillianNeural",
        "fr": "fr-FR-HenriNeural",
        "es": "es-ES-AlvaroNeural",
        "ja": "ja-JP-KeitaNeural",
        "uk": "uk-UA-OstapNeural",
        "it": "it-IT-DiegoNeural",
    }
    selected_voice = voices.get(
        safe_lang_code,
        "en-US-ChristopherNeural" if safe_lang_code != "ru" else "ru-RU-DmitryNeural",
    )

    try:
        communicate = edge_tts.Communicate(text.strip(), selected_voice)
        await communicate.save(output_path)
        return True
    except edge_tts.exceptions.NoAudioReceived:
        logger.error("❌ edge_tts не вернул аудио (NoAudioReceived).")
        return False
    except Exception as e:
        logger.error(f"❌ Ошибка генерации озвучки: {e}")
        return False

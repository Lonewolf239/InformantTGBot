import aiohttp
import os
import json
import uuid
from urllib.parse import urlparse
from aiogram import types
from aiogram.types import InlineKeyboardButton
from config import (
    MEME_API_KEY,
    MEME_API_URL,
    MEME_MAX_AGE_DAYS,
    MEME_MIN_RATING,
    COMMAND_METADATA,
)
from bot.utils.database import db
from bot.utils.helpers import (
    format_styled_message,
    create_user_keyboard,
    freeze_tokens,
    refund_tokens,
    get_raw_text,
)
import logging

API_ICON = COMMAND_METADATA["!мем"]["icon"]
API_NAME = COMMAND_METADATA["!мем"]["name"]

logger = logging.getLogger(__name__)
FAVORITES_FILE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "favorite_memes.json"
)
DISLIKED_FILE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "disliked_memes.json"
)

url_cache = {}


def load_favorites():
    if os.path.exists(FAVORITES_FILE):
        try:
            with open(FAVORITES_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []
    return []


def save_favorites(favorites):
    with open(FAVORITES_FILE, "w", encoding="utf-8") as f:
        json.dump(favorites, f, ensure_ascii=False, indent=2)


def add_to_favorites(meme_data):
    favorites = load_favorites()
    if not any(meme.get("url") == meme_data.get("url") for meme in favorites):
        favorites.append(meme_data)
        save_favorites(favorites)
        return True
    return False


def load_disliked():
    if os.path.exists(DISLIKED_FILE):
        try:
            with open(DISLIKED_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []
    return []


def save_disliked(disliked):
    with open(DISLIKED_FILE, "w", encoding="utf-8") as f:
        json.dump(disliked, f, ensure_ascii=False, indent=2)


def add_to_disliked(meme_url):
    disliked = load_disliked()
    if meme_url not in disliked:
        disliked.append(meme_url)
        save_disliked(disliked)
        return True
    return False


def is_meme_favorite(meme_url):
    favorites = load_favorites()
    return any(meme.get("url") == meme_url for meme in favorites)


def get_random_favorite_meme():
    favorites = load_favorites()
    if favorites:
        import random

        return random.choice(favorites)
    return None


async def get_random_meme_filtered():
    disliked = load_disliked()
    for _ in range(5):
        meme = await get_random_meme()
        if meme and meme["url"] not in disliked:
            return meme
    return None


async def get_random_meme():
    params = {
        "api-key": MEME_API_KEY,
        "max-age-days": MEME_MAX_AGE_DAYS,
        "min-rating": MEME_MIN_RATING,
    }
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(MEME_API_URL, params=params) as response:
                if response.status == 200:
                    meme_data = await response.json()
                    return {
                        "description": meme_data.get("description", "Без описания"),
                        "url": meme_data.get("url"),
                    }
                return None
        except Exception as e:
            logger.error(f"Ошибка в get_random_meme: {e}")
            return None


def get_media_type(url: str) -> str:
    path = urlparse(url).path
    ext = os.path.splitext(path)[1].lower()
    if ext in [".mp4", ".webm", ".mov"]:
        return "video"
    elif ext in [".gif"]:
        return "gif"
    return "photo"


def get_meme_keyboard(meme_url, user_id: int, is_rated=False):
    buttons = []

    if not is_rated:
        meme_id = uuid.uuid4().hex[:8]
        url_cache[meme_id] = meme_url
        buttons.append(
            InlineKeyboardButton(text="❤️", callback_data=f"fav_meme|{meme_id}")
        )

    buttons.append(InlineKeyboardButton(text="🎭 Ещё мем", callback_data="more_meme"))

    if not is_rated:
        buttons.append(
            InlineKeyboardButton(text="👎", callback_data=f"dislike_meme|{meme_id}")
        )

    return create_user_keyboard([buttons], user_id)


async def send_meme(
    target, is_callback=False, use_fallback=False, force_favorite=False
):
    meme_data = None
    if force_favorite or use_fallback:
        meme_data = get_random_favorite_meme()
    elif not use_fallback:
        meme_data = await get_random_meme_filtered()

    if not meme_data or not meme_data.get("url"):
        meme_data = get_random_favorite_meme()
        if not meme_data:
            error_text = format_styled_message(
                emoji="😔",
                title="Ошибка мемов",
                message="Не удалось загрузить мем.\nИзбранное пусто!\nДобавь первый мем через <code>!мем</code> и нажми ❤️",
            )
            if is_callback:
                await target.message.answer(error_text)
            else:
                await target.reply(error_text)
            return False

    url = meme_data["url"]
    description = meme_data.get("description", "Без описания")
    if len(description) > 200:
        description = description[:197] + "..."

    media_type = get_media_type(url)
    message_caption = format_styled_message(
        emoji=API_ICON, title=API_NAME, message=description
    )
    is_fav = is_meme_favorite(url)
    reply_markup = get_meme_keyboard(url, target.from_user.id, is_rated=is_fav)

    send_methods = {
        "video": (
            target.reply_video if not is_callback else target.message.reply_video
        ),
        "gif": (
            target.reply_animation
            if not is_callback
            else target.message.reply_animation
        ),
        "photo": (
            target.reply_photo if not is_callback else target.message.reply_photo
        ),
    }

    method = send_methods.get(media_type, send_methods["photo"])
    kwargs = {"caption": message_caption, "reply_markup": reply_markup}

    if media_type == "video":
        kwargs["video"] = url
    elif media_type == "gif":
        kwargs["animation"] = url
    else:
        kwargs["photo"] = url

    try:
        await method(**kwargs)
        await db.increment_memes()
        await db.increment_commands()
        await db.log_command("!мем", target.from_user.id)
        return True

    except Exception as e:
        logger.error(f"Ошибка при отправке медиа: {e}")
        return False


async def cmd_meme(message: types.Message):
    user_id = message.from_user.id
    if not await freeze_tokens(message, user_id, "!мем"):
        return

    raw_text = get_raw_text(message) or ""
    force_favorite = "избранное" in raw_text

    success = await send_meme(
        message, is_callback=False, use_fallback=False, force_favorite=force_favorite
    )

    if not success and not force_favorite:
        success = await send_meme(message, is_callback=False, use_fallback=True)

    if not success:
        await refund_tokens(user_id, "!мем")
        error_msg = format_styled_message(
            emoji="😔",
            title="Ошибка мемов",
            message=(
                "В избранном пока нет мемов!"
                if force_favorite
                else "API недоступен и избранное пусто.\nПопробуй позже!"
            ),
        )
        await message.reply(error_msg)


async def more_meme_callback(callback_query: types.CallbackQuery):
    user_id = callback_query.from_user.id
    if not await freeze_tokens(callback_query.message, user_id, "!мем"):
        await callback_query.answer()
        return

    await callback_query.answer("🔄 Загружаю новый мем...")
    success = await send_meme(callback_query, is_callback=True, use_fallback=False)

    if not success:
        await refund_tokens(user_id, "!мем")


async def add_favorite_callback(callback_query: types.CallbackQuery):
    data = callback_query.data
    meme_id = data.split("|", 1)[1] if "|" in data else None

    meme_url = url_cache.pop(meme_id, None)

    if not meme_url:
        await callback_query.answer(
            "❌ Ошибка: не удалось определить мем", show_alert=True
        )
        return

    meme_to_save = {"url": meme_url, "description": "Избранный мем"}
    try:
        if callback_query.message and callback_query.message.caption:
            caption = callback_query.message.caption
            if "└─ " in caption:
                meme_to_save["description"] = caption.split("└─ ")[1]
    except Exception:
        pass

    if add_to_favorites(meme_to_save):
        await callback_query.answer("❤️ Мем добавлен в избранное!", show_alert=False)
        try:
            new_keyboard = get_meme_keyboard(
                meme_url, callback_query.from_user.id, is_rated=True
            )
            await callback_query.message.edit_reply_markup(reply_markup=new_keyboard)
        except Exception as e:
            logger.error(f"Ошибка при скрытии кнопок: {e}")
    else:
        await callback_query.answer("⚠️ Этот мем уже в избранном", show_alert=False)


async def dislike_meme_callback(callback_query: types.CallbackQuery):
    data = callback_query.data
    meme_id = data.split("|", 1)[1] if "|" in data else None

    meme_url = url_cache.pop(meme_id, None)

    if not meme_url:
        await callback_query.answer(
            "❌ Ошибка: не удалось определить мем", show_alert=True
        )
        return

    add_to_disliked(meme_url)

    new_caption = format_styled_message(
        emoji="👎",
        title="Мем скрыт",
        message="Этот мем добавлен в черный список и больше не попадется.",
    )

    new_keyboard = get_meme_keyboard(
        meme_url, callback_query.from_user.id, is_rated=True
    )

    try:
        await callback_query.message.edit_caption(
            caption=new_caption, reply_markup=new_keyboard
        )
    except Exception as e:
        logger.error(f"Ошибка при редактировании сообщения дизлайка: {e}")

import aiohttp
import os
import json
from urllib.parse import urlparse
from aiogram import types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from config import MEME_API_KEY
from bot.utils.database import db
import logging

logger = logging.getLogger(__name__)

FAVORITES_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'favorite_memes.json')

def load_favorites():
    if os.path.exists(FAVORITES_FILE):
        try:
            with open(FAVORITES_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return []
    return []

def save_favorites(favorites):
    with open(FAVORITES_FILE, 'w', encoding='utf-8') as f:
        json.dump(favorites, f, ensure_ascii=False, indent=2)

def add_to_favorites(meme_data):
    favorites = load_favorites()
    if not any(meme.get('url') == meme_data.get('url') for meme in favorites):
        favorites.append(meme_data)
        save_favorites(favorites)
        return True
    return False

def is_meme_favorite(meme_url):
    favorites = load_favorites()
    return any(meme.get('url') == meme_url for meme in favorites)

def get_random_favorite_meme():
    favorites = load_favorites()
    if favorites:
        import random
        return random.choice(favorites)
    return None

async def get_random_meme():
    url = "https://api.apileague.com/retrieve-random-meme"
    params = {
        "api-key": MEME_API_KEY,
        "max-age-days": 67,
        "min-rating": 0.9
    }
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(url, params=params) as response:
                if response.status == 200:
                    meme_data = await response.json()
                    return {
                        "description": meme_data.get("description", "Без описания"),
                        "url": meme_data.get("url")
                    }
                else:
                    logger.error(f"Ошибка API мемов: {response.status}")
                    return None
        except aiohttp.ClientError as e:
            logger.error(f"Сетевая ошибка при запросе мема: {e}")
            return None
        except Exception as e:
            logger.error(f"Неожиданная ошибка в get_random_meme: {e}")
            return None

def get_media_type(url: str) -> str:
    path = urlparse(url).path
    ext = os.path.splitext(path)[1].lower()
    if ext in ['.mp4', '.webm', '.mov']:
        return 'video'
    elif ext in ['.gif']:
        return 'gif'
    elif ext in ['.jpg', '.jpeg', '.png', '.webp']:
        return 'photo'
    else:
        return 'photo'

def get_meme_keyboard(meme_url, is_favorite=False):
    buttons = []

    if not is_favorite:
        buttons.append(InlineKeyboardButton(text="❤️", callback_data=f"fav_meme|{meme_url}"))

    buttons.append(InlineKeyboardButton(text="🎭 Ещё мем", callback_data="more_meme"))

    return InlineKeyboardMarkup(inline_keyboard=[buttons])

async def send_meme(target, is_callback=False, use_fallback=False):
    meme_data = None

    if not use_fallback:
        meme_data = await get_random_meme()

    if not meme_data or not meme_data.get("url"):
        meme_data = get_random_favorite_meme()

        if not meme_data:
            error_text = (
                "<b>┌─ 😔 Ошибка</b>\n"
                "├─ Не удалось загрузить мем.\n"
                "├─ Избранное пусто!\n"
                "└─ Добавь первый мем через <code>!мем</code> и нажми ❤️"
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
    message_caption = f"<b>┌─ 🎭 Мем</b>\n└─ {description}"

    is_fav = is_meme_favorite(url)

    reply_markup = get_meme_keyboard(url, is_fav)
    send_methods = {
        'video': (target.reply_video if not is_callback else target.message.reply_video),
        'gif': (target.reply_animation if not is_callback else target.message.reply_animation),
        'photo': (target.reply_photo if not is_callback else target.message.reply_photo)
    }

    method = send_methods.get(media_type, send_methods['photo'])

    kwargs = {
        'caption': message_caption,
        'reply_markup': reply_markup
    }

    if media_type == 'video':
        kwargs['video'] = url
    elif media_type == 'gif':
        kwargs['animation'] = url
    else:
        kwargs['photo'] = url

    try:
        await method(**kwargs)
        db.increment_memes()
        return True
    except Exception as e:
        logger.error(f"Ошибка при отправке медиа: {e}")
        return False

async def cmd_meme(message: types.Message):
    try:
        success = await send_meme(message, is_callback=False, use_fallback=False)

        if not success:
            success = await send_meme(message, is_callback=False, use_fallback=True)

        if not success:
            await message.reply(
                "<b>┌─ 😔 Ошибка</b>\n"
                "├─ Не удалось загрузить мем.\n"
                "├─ API недоступен и избранное пусто.\n"
                "└─ Добавь первый мем позже!"
            )
        return True
    except Exception as e:
        logger.error(f"Ошибка в !мем: {e}")
        await message.reply(
            "<b>┌─ 😔 Ошибка</b>\n"
            "├─ Не удалось отправить мем.\n"
            "└─ Попробуй позже или попроси анекдот: <code>!анекдот</code>"
        )
        return True

async def more_meme_callback(callback_query: types.CallbackQuery):
    await callback_query.answer("🔄 Загружаю новый мем...")
    await send_meme(callback_query, is_callback=True, use_fallback=False)

async def add_favorite_callback(callback_query: types.CallbackQuery):
    data = callback_query.data
    meme_url = data.split("|", 1)[1] if "|" in data else None

    if not meme_url:
        await callback_query.answer("❌ Ошибка: не удалось определить мем", show_alert=True)
        return

    meme_to_save = {
        "url": meme_url,
        "description": "Избранный мем"
    }

    try:
        if callback_query.message and callback_query.message.caption:
            caption = callback_query.message.caption
            if "└─ " in caption:
                description = caption.split("└─ ")[1]
                meme_to_save["description"] = description
    except:
        pass

    if add_to_favorites(meme_to_save):
        await callback_query.answer("❤️ Мем добавлен в избранное!", show_alert=False)

        new_keyboard = get_meme_keyboard(meme_url, is_favorite=True)
        try:
            await callback_query.message.edit_reply_markup(reply_markup=new_keyboard)
        except:
            pass
    else:
        await callback_query.answer("⚠️ Этот мем уже в избранном", show_alert=False)

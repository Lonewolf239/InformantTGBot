import aiohttp
import logging
import asyncio
from datetime import datetime
from aiogram import types
from config import OPENWEATHER_API_KEY, WEATHER_GEO_URL, WEATHER_API_URL, WEATHER_FORECAST_URL, TRANSLATE_API_URL
from bot.utils.database import db

logger = logging.getLogger(__name__)


async def translate_to_english(text: str) -> str:
    params = {"client": "gtx", "sl": "ru", "tl": "en", "dt": "t", "q": text}
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(TRANSLATE_API_URL, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    if data and data[0]: return data[0][0][0]
                return text
        except Exception: return text


async def get_coordinates(city_name: str):
    params = {"q": city_name, "limit": 1, "appid": OPENWEATHER_API_KEY}
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(WEATHER_GEO_URL, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    if data:
                        return {"lat": data[0]["lat"], "lon": data[0]["lon"], "name": data[0]["name"], "country": data[0].get("country", "")}

            translated = await translate_to_english(city_name)
            if translated != city_name:
                params["q"] = translated
                async with session.get(WEATHER_GEO_URL, params=params) as response2:
                    if response2.status == 200:
                        data2 = await response2.json()
                        if data2:
                            return {"lat": data2[0]["lat"], "lon": data2[0]["lon"], "name": data2[0]["name"], "country": data2[0].get("country", "")}
            return None
        except Exception: return None


async def get_weather_by_coords(lat: float, lon: float):
    params = {"lat": lat, "lon": lon, "units": "metric", "lang": "ru", "appid": OPENWEATHER_API_KEY}
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(WEATHER_API_URL, params=params) as response:
                if response.status == 200: return await response.json()
                return None
        except Exception: return None


def get_weather_emoji(weather_id: int):
    if 200 <= weather_id < 300: return "⛈️"
    elif 300 <= weather_id < 400 or 500 <= weather_id < 600: return "🌧️"
    elif 600 <= weather_id < 700: return "❄️"
    elif 700 <= weather_id < 800: return "🌫️"
    elif weather_id == 800: return "☀️"
    elif 801 <= weather_id < 803: return "🌤️"
    elif 803 <= weather_id < 900: return "☁️"
    return "🌡️"


def get_wind_direction(degrees: int):
    directions = ["северный", "северо-восточный", "восточный", "юго-восточный", "южный", "юго-западный", "западный", "северо-западный"]
    return directions[round(degrees / 45) % 8]


def format_weather_message(weather_data: dict, city_name: str, country: str):
    main_data, wind_data, sys_data, clouds_data = weather_data.get("main", {}), weather_data.get("wind", {}), weather_data.get("sys", {}), weather_data.get("clouds", {})
    weather_info = weather_data.get("weather", [{}])[0]

    emoji = get_weather_emoji(weather_info.get("id", 800))
    sunrise = datetime.fromtimestamp(sys_data.get("sunrise", 0)).strftime("%H:%M") if sys_data.get("sunrise") else "Н/Д"
    sunset = datetime.fromtimestamp(sys_data.get("sunset", 0)).strftime("%H:%M") if sys_data.get("sunset") else "Н/Д"

    return (
        f"<b>┌─ {emoji} ПОГОДА В {city_name.upper()}, {country}</b>\n"
        f"<b>├─ 🌡️ Сейчас:</b> {round(main_data.get('temp', 0))}°C (ощущается как {round(main_data.get('feels_like', 0))}°C)\n"
        f"<b>├─ 📝 Описание:</b> {weather_info.get('description', '').capitalize()}\n"
        f"<b>├─ 💧 Влажность:</b> {main_data.get('humidity', 0)}%\n"
        f"<b>├─ 🌬️ Ветер:</b> {wind_data.get('speed', 0)} м/с, {get_wind_direction(wind_data.get('deg', 0))}\n"
        f"<b>├─ 📊 Давление:</b> {round(main_data.get('pressure', 0) * 0.750064)} мм рт. ст.\n"
        f"<b>├─ ☁️ Облачность:</b> {clouds_data.get('all', 0)}%\n"
        f"<b>├─ 🌅 Рассвет:</b> {sunrise} | <b>🌇 Закат:</b> {sunset}\n"
        f"<b>└─ 🏙️ Хорошего дня!</b>"
    )


async def cmd_weather(message: types.Message):
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.reply("<b>┌─ 🌤️ ПОГОДА</b>\n├─ ❌ Не указан город!\n└─ 📝 Использование: <code>!погода [город]</code>")
        return True

    city_name = args[1].strip()
    try: await message.bot.send_chat_action(chat_id=message.chat.id, action="typing")
    except: pass

    try:
        searching_msg = await asyncio.wait_for(
            message.reply(f"<b>┌─ 🔍 ПОИСК ПОГОДЫ</b>\n└─ Ищу погоду в городе <b>{city_name}</b>... 🌍"),
            timeout=30.0
        )
    except asyncio.TimeoutError:
        searching_msg = None

    try:
        location = await asyncio.wait_for(get_coordinates(city_name), timeout=20.0)
        if not location:
            reply = f"<b>┌─ ❌ ГОРОД НЕ НАЙДЕН</b>\n└─ Город <b>{city_name}</b> не найден!"
            if searching_msg: await searching_msg.edit_text(reply)
            else: await message.reply(reply)
            return True

        weather_data = await asyncio.wait_for(get_weather_by_coords(location["lat"], location["lon"]), timeout=15.0)
        if not weather_data:
            reply = f"<b>┌─ ❌ ОШИБКА API</b>\n└─ Не удалось получить данные о погоде для {location['name']}"
            if searching_msg: await searching_msg.edit_text(reply)
            else: await message.reply(reply)
            return True

        weather_text = format_weather_message(weather_data, location["name"], location["country"])
        if searching_msg: await searching_msg.edit_text(weather_text)
        else: await message.reply(weather_text)

        db.increment_commands()
        db.log_command("!погода", message.from_user.id)
        return True

    except Exception:
        error_msg = "<b>┌─ ❌ ОШИБКА</b>\n└─ Не удалось получить погоду. Попробуйте позже!"
        if searching_msg: await searching_msg.edit_text(error_msg)
        else: await message.reply(error_msg)
        return True

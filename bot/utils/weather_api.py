import aiohttp
import logging
import asyncio
from datetime import datetime
from aiogram import types
from config import OPENWEATHER_API_KEY
from bot.utils.database import db

logger = logging.getLogger(__name__)

async def translate_to_english(text: str) -> str:
    url = "https://translate.googleapis.com/translate_a/single"
    params = {
        "client": "gtx",
        "sl": "ru",
        "tl": "en",
        "dt": "t",
        "q": text
    }

    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    if data and data[0]:
                        return data[0][0][0]
                return text
        except Exception as e:
            logger.error(f"Ошибка при переводе: {e}")
            return text

async def get_coordinates(city_name: str):
    url = "http://api.openweathermap.org/geo/1.0/direct"
    params = {
        "q": city_name,
        "limit": 1,
        "appid": OPENWEATHER_API_KEY
    }

    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    if data:
                        return {
                            "lat": data[0]["lat"],
                            "lon": data[0]["lon"],
                            "name": data[0]["name"],
                            "country": data[0].get("country", "")
                        }

            translated = await translate_to_english(city_name)
            if translated != city_name:
                params["q"] = translated
                async with session.get(url, params=params) as response2:
                    if response2.status == 200:
                        data2 = await response2.json()
                        if data2:
                            return {
                                "lat": data2[0]["lat"],
                                "lon": data2[0]["lon"],
                                "name": data2[0]["name"],
                                "country": data2[0].get("country", "")
                            }
            return None

        except Exception as e:
            logger.error(f"Ошибка при получении координат: {e}")
            return None

async def get_weather_by_coords(lat: float, lon: float):
    url = "https://api.openweathermap.org/data/2.5/weather"
    params = {
        "lat": lat,
        "lon": lon,
        "units": "metric",
        "lang": "ru",
        "appid": OPENWEATHER_API_KEY
    }

    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(url, params=params) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    logger.error(f"Ошибка API погоды: {response.status} - {await response.text()}")
                    return None
        except Exception as e:
            logger.error(f"Ошибка при получении погоды: {e}")
            return None

async def get_forecast_by_coords(lat: float, lon: float):
    url = "https://api.openweathermap.org/data/2.5/forecast"
    params = {
        "lat": lat,
        "lon": lon,
        "units": "metric",
        "lang": "ru",
        "appid": OPENWEATHER_API_KEY,
        "cnt": 8
    }

    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(url, params=params) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    logger.error(f"Ошибка API прогноза: {response.status}")
                    return None
        except Exception as e:
            logger.error(f"Ошибка при получении прогноза: {e}")
            return None

def get_weather_emoji(weather_id: int):
    if 200 <= weather_id < 300:
        return "⛈️"
    elif 300 <= weather_id < 400:
        return "🌧️"
    elif 500 <= weather_id < 600:
        return "🌧️"
    elif 600 <= weather_id < 700:
        return "❄️"
    elif 700 <= weather_id < 800:
        return "🌫️"
    elif weather_id == 800:
        return "☀️"
    elif 801 <= weather_id < 803:
        return "🌤️"
    elif 803 <= weather_id < 900:
        return "☁️"
    else:
        return "🌡️"

def get_wind_direction(degrees: int):
    directions = ["северный", "северо-восточный", "восточный", "юго-восточный", 
                  "южный", "юго-западный", "западный", "северо-западный"]
    idx = round(degrees / 45) % 8
    return directions[idx]

def format_weather_message(weather_data: dict, city_name: str, country: str):
    main_data = weather_data.get("main", {})
    wind_data = weather_data.get("wind", {})
    weather_info = weather_data.get("weather", [{}])[0]
    sys_data = weather_data.get("sys", {})
    clouds_data = weather_data.get("clouds", {})

    weather_id = weather_info.get("id", 800)
    weather_emoji = get_weather_emoji(weather_id)
    weather_desc = weather_info.get("description", "").capitalize()

    temp = round(main_data.get("temp", 0))
    feels_like = round(main_data.get("feels_like", 0))

    humidity = main_data.get("humidity", 0)
    wind_speed = wind_data.get("speed", 0)
    wind_deg = wind_data.get("deg", 0)
    wind_dir = get_wind_direction(wind_deg)

    pressure = round(main_data.get("pressure", 0) * 0.750064)

    sunrise = datetime.fromtimestamp(sys_data.get("sunrise", 0)).strftime("%H:%M") if sys_data.get("sunrise") else "Н/Д"
    sunset = datetime.fromtimestamp(sys_data.get("sunset", 0)).strftime("%H:%M") if sys_data.get("sunset") else "Н/Д"

    clouds = clouds_data.get("all", 0)

    message = (
        f"<b>┌─ {weather_emoji} ПОГОДА В {city_name.upper()}, {country}</b>\n"
        f"<b>├─ 🌡️ Сейчас:</b> {temp}°C (ощущается как {feels_like}°C)\n"
        f"<b>├─ 📝 Описание:</b> {weather_desc}\n"
        f"<b>├─ 💧 Влажность:</b> {humidity}%\n"
        f"<b>├─ 🌬️ Ветер:</b> {wind_speed} м/с, {wind_dir}\n"
        f"<b>├─ 📊 Давление:</b> {pressure} мм рт. ст.\n"
        f"<b>├─ ☁️ Облачность:</b> {clouds}%\n"
        f"<b>├─ 🌅 Рассвет:</b> {sunrise}\n"
        f"<b>├─ 🌇 Закат:</b> {sunset}\n"
        f"<b>│</b>\n"
        f"<b>└─ 🏙️ Хорошего дня!</b>"
    )

    return message

async def cmd_weather(message: types.Message):
    args = message.text.split(maxsplit=1)

    if len(args) < 2:
        await message.reply(
            "<b>┌─ 🌤️ ПОГОДА</b>\n"
            "├─ ❌ Не указан город!\n"
            "└─ 📝 Использование: <code>!погода</code> [город]"
        )
        return True

    city_name = args[1].strip()

    try:
        await message.bot.send_chat_action(chat_id=message.chat.id, action="typing")
    except:
        pass

    try:
        searching_msg = await asyncio.wait_for(
            message.reply(
                f"<b>┌─ 🔍 ПОИСК ПОГОДЫ</b>\n"
                f"└─ Ищу погоду в городе <b>{city_name}</b>... 🌍"
            ),
            timeout=30.0
        )
    except asyncio.TimeoutError:
        searching_msg = None
        await message.answer("🔍 Ищу погоду... (это может занять время)")

    try:
        location = await asyncio.wait_for(
            get_coordinates(city_name),
            timeout=20.0
        )

        if not location:
            reply = (f"<b>┌─ ❌ ГОРОД НЕ НАЙДЕН</b>\n"
                    f"└─ Город <b>{city_name}</b> не найден!")
            if searching_msg:
                try:
                    await searching_msg.edit_text(reply)
                except:
                    await message.reply(reply)
            else:
                await message.reply(reply)
            return True

        weather_data = await asyncio.wait_for(
            get_weather_by_coords(location["lat"], location["lon"]),
            timeout=15.0
        )

        if not weather_data:
            reply = (f"<b>┌─ ❌ ОШИБКА API</b>\n"
                    f"└─ Не удалось получить данные о погоде для {location['name']}")
            if searching_msg:
                try:
                    await searching_msg.edit_text(reply)
                except:
                    await message.reply(reply)
            else:
                await message.reply(reply)
            return True

        weather_text = format_weather_message(
            weather_data,
            location["name"],
            location["country"]
        )

        if searching_msg:
            try:
                await searching_msg.edit_text(weather_text)
            except:
                await message.reply(weather_text)
        else:
            await message.reply(weather_text)

        db.increment_commands()
        db.log_command("!погода", message.from_user.id)
        return True

    except asyncio.TimeoutError:
        error_msg = "<b>┌─ ⏰ ОШИБКА</b>\n└─ Превышено время ожидания ответа от сервера погоды"
        if searching_msg:
            try:
                await searching_msg.edit_text(error_msg)
            except:
                await message.reply(error_msg)
        else:
            await message.reply(error_msg)
        return True

    except Exception as e:
        logger.error(f"Ошибка в !погода: {e}")
        error_msg = "<b>┌─ ❌ ОШИБКА</b>\n└─ Не удалось получить погоду. Попробуйте позже!"
        if searching_msg:
            try:
                await searching_msg.edit_text(error_msg)
            except:
                await message.reply(error_msg)
        else:
            await message.reply(error_msg)
        return True


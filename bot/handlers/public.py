from aiogram import types
from config import (
    COMMAND_COSTS, VIP_IDS, PAYMENTS_ENABLED,
    WELCOME_TEXT, KEYWORD_REACTIONS, SIMPLE_ANSWERS,
    SFW_RP_ACTIONS, NSFW_RP_ACTIONS, PAYMENTS_ENABLED,
    AUTO_REPLY_ENABLED, REPLY_TO_OWNER, DEFAULT_DAILY_TOKENS
)
from bot.utils.keyword_handlers import KEYWORD_COMMANDS_REGISTRY
from bot.utils.user_settings import user_settings_db
from bot.state import state
from bot.utils.helpers import its_me
from bot.utils.joke_api import cmd_joke
from bot.utils.meme_api import cmd_meme
from bot.utils.weather_api import cmd_weather
from bot.utils.ai_api import cmd_ai, cmd_ai_ham
from bot.utils.database import db
from bot.handlers.nsfw_settings import cmd_nsfw_settings
from bot.utils.whisper_stt import cmd_transcribe, cmd_translate
from bot.utils.youtube_api import cmd_download_yt
from bot.utils.tokens_database import tokens_db
from bot.handlers.payments import cmd_balance
from bot.utils.currency_api import cmd_currency
from bot.utils.music_api import cmd_music
from functools import lru_cache
import logging

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def get_public_help_text(is_away_mode: bool = False):
    status_emoji = "🚶‍♂️" if is_away_mode else "🟢"
    status_text = "режим ОТОШЁЛ активен" if is_away_mode else "режим ОНЛАЙН"

    commands = [
        "<b>┌─ 🤖 ДОСТУПНЫЕ КОМАНДЫ</b>",
        "<b>├─ 🎭</b> <code>!анекдот</code> — случайная шутка",
        "<b>├─ 🖼️</b> <code>!мем</code> — случайный мем",
        "<b>├─ 🌤️</b> <code>!погода</code> [город] — текущая погода",
        "<b>├─ 🧠</b> <code>!ии</code> [текст] — запрос к локальной нейросети",
        "<b>├─ 🎙️</b> <code>!расшифровка</code> — текст из аудио/видео",
        "<b>├─ 🌐</b> <code>!перевести</code> — перевод и озвучка",
        "<b>├─ 🎬</b> <code>!скачать</code> [ссылка] — загрузка с YouTube",
        "<b>├─ 🎭</b> <code>!рп</code> — список RP-команд",
        "<b>├─ 🎵</b> <code>!трек</code> [название] — поиск и скачивание музыки",
        "<b>├─ 💱</b> <code>!курс</code> [сумма] [валюты] — конвертер валют",
    ]

    if PAYMENTS_ENABLED:
        commands.append("<b>├─ 💰</b> <code>!прайс</code> — стоимость команд")
        commands.append("<b>├─ 💳</b> <code>!баланс</code> — кошелёк и покупка токенов")

    commands.extend([
        "<b>├─ ⚙️</b> <code>!настройки</code> — настройки бота (NSFW и др.)",
        "<b>├─ 🤖</b> <code>!о_боте</code> — техническая информация",
        "<b>├─ 🍩</b> <code>!donut</code> — поддержать автора",
        "<b>├─ ℹ️</b> <code>!помощь</code> — это меню",
        "<b>│</b>",
        "<b>├─ 🔗 <i>Авто-сохранение ссылок</i></b>",
        "<b>├─   Отправь ссылку на музыку/видео, и она</b>",
        "<b>├─   появится у владельца в !ссылки</b>",
        "<b>│</b>",
        f"<b>├─ {status_emoji} Статус:</b> {status_text}",
        "<b>└─ 🤖 Автоответ:</b> Мгновенный при включённом режиме"
    ])

    return "\n".join(commands)


async def cmd_prices(message: types.Message):
    emoji_map = {
        "!перевести": "🌐",
        "!расшифровка": "🎙️",
        "!ии": "🧠",
        "!нейрохам": "🤬",
        "!скачать": "🎬",
        "!музыка": "🎵",
        "!курс": "💱",
        "!погода": "🌤️",
        "!анекдот": "🎭",
        "!мем": "🖼️"
    }

    price_text = (
        "<b>┌─ 💰 ПРАЙС-ЛИСТ КОМАНД</b>\n"
        f"<b>├─ 🎁 Ежедневный лимит:</b> {DEFAULT_DAILY_TOKENS} токенов\n"
        "<b>│</b>\n"
    )

    for cmd, cost in sorted(COMMAND_COSTS.items(), key=lambda x: x[1], reverse=True):
        emoji = emoji_map.get(cmd, "🔹")

        if cost % 10 == 1 and cost % 100 != 11:
            token_word = "токен"
        elif 2 <= cost % 10 <= 4 and (cost % 100 < 10 or cost % 100 >= 20):
            token_word = "токена"
        else:
            token_word = "токенов"

        price_text += f"<b>├─ {emoji}</b> <code>{cmd}</code> — {cost} {token_word}\n"

    price_text += (
        "<b>│</b>\n"
        "<b>└─ 💳 Узнать свой баланс:</b> <code>!баланс</code>"
    )

    await message.reply(price_text)
    await db.increment_commands()
    await db.log_command("!прайс", message.from_user.id)
    return True


async def get_rp_commands(user_id: int = None):
    sfw_list = []
    for cmd, action in SFW_RP_ACTIONS.items():
        emoji = action[0] if action else "🎭"
        sfw_list.append(f"<b>├─ {emoji}</b> <code>{cmd}</code>")

    sfw_text = "\n".join(sfw_list)
    result = f"<b>┌─ 🎭 SFW RP КОМАНДЫ</b>\n{sfw_text}"

    if user_id and await user_settings_db.get_nsfw_setting(user_id):
        nsfw_list = []
        for cmd, action in NSFW_RP_ACTIONS.items():
            emoji = action[0] if action else "🎭"
            nsfw_list.append(f"<b>├─ {emoji}</b> <code>{cmd}</code>")
        nsfw_text = "\n".join(nsfw_list)
        result += f"\n<b>│</b>\n<b>├─ 🔞 NSFW RP КОМАНДЫ (18+)</b>\n{nsfw_text}"

    result += "\n<b>│</b>\n<b>└─</b> Ответь на сообщение и напиши: [команда] &lt;слова&gt;\n"
    return result


async def cmd_start(message: types.Message):
    await message.reply(WELCOME_TEXT)
    await db.increment_commands()
    await db.log_command("!старт", message.from_user.id)
    return True


async def cmd_help(message: types.Message):
    is_away = await state.is_away_mode
    help_text = get_public_help_text(is_away)
    await message.reply(help_text)
    await db.increment_commands()
    await db.log_command("!помощь", message.from_user.id)
    return True


async def cmd_rp_commands(message: types.Message):
    user_id = message.from_user.id
    await message.reply(await get_rp_commands(user_id))
    await db.increment_commands()
    await db.log_command("!рп", message.from_user.id)
    return True


async def cmd_about(message: types.Message):
    bot_user = await message.bot.get_me()
    bot_name = bot_user.full_name
    bot_username = bot_user.username

    about_text = (
        f"<b>┌─ 🤖 О БОТЕ</b>\n"
        f"<b>├─ 📝 Название:</b> <a href='https://t.me/{bot_username}'>{bot_name}</a> (<a href='https://github.com/Lonewolf239/InformantTGBot'>GitHub</a>)\n"
        "<b>├─ 🛠️ Функции:</b>\n"
        "<b>├─  •</b> Автоответчик при режиме «отошёл»\n"
        "<b>├─  •</b> RP команды (обнять, поцеловать и др.)\n"
        "<b>├─  •</b> Анекдоты из API и Мемы с описанием\n"
        "<b>├─  •</b> Погода в любом городе\n"
        "<b>├─  •</b> Локальный ИИ через Ollama\n"
        "<b>├─  •</b> Расшифровка и перевод медиа\n"
        "<b>├─  •</b> Скачивание с YouTube\n"
        "<b>├─ 💻 Разработчик:</b> <a href='https://t.me/an1onime'>Lonewolf239</a>\n"
        "<b>├─ 📊 Статистика:</b> <code>!статистика</code> (только для владельца)\n"
        "<b>└─ 🎭 Для RP команд:</b> ответь на сообщение и напиши <code>!обнять</code>"
    )
    await message.reply(about_text, disable_web_page_preview=True)
    await db.increment_commands()
    await db.log_command("!о_боте", message.from_user.id)
    return True


async def cmd_donut(message: types.Message):
    donut_text = (
        "<b>┌─ 🍩 ПОДДЕРЖАТЬ РАЗРАБОТЧИКА</b>\n"
        "<b>├─ 💖 Если тебе нравится бот и ты хочешь помочь\n├─ его развитию:</b>\n"
        "<b>│</b>\n"
        "<b>├─ 🔗 DonationAlerts:</b>\n"
        "<b>├─</b> https://www.donationalerts.com/r/lonewolf239\n"
        "<b>│</b>\n"
        "<b>├─ 🙏 Спасибо за поддержку! ❤️</b>\n"
        "<b>└─ 🍩 Даже маленькая сумма помогает боту жить!</b>"
    )
    await message.reply(donut_text, disable_web_page_preview=True)
    await db.increment_commands()
    await db.log_command("!donut", message.from_user.id)
    return True


async def handle_keywords(message: types.Message):
    text = message.text.strip().lower()
    import re
    words = re.findall(r'\b\w+\b', text)

    for keyword, reply in KEYWORD_REACTIONS.items():
        keyword_lower = keyword.lower()

        match_found = False

        if ' ' in keyword_lower:
            if keyword_lower in text:
                match_found = True
        else:
            if keyword_lower in words:
                match_found = True

        if match_found:
            if reply.startswith("cmd:"):
                method_name = reply.split("cmd:")[1]
                handler_func = KEYWORD_COMMANDS_REGISTRY.get(method_name)
                if handler_func:
                    await handler_func(message)
                    return True
                else:
                    logger.error(f"Метод {method_name} не найден в KEYWORD_COMMANDS_REGISTRY")
            else:
                await message.reply(reply)
                return True

    return False


async def handle_simple_answers(message: types.Message):
    text = message.text.strip().lower()
    text_normalized = text.rstrip('?').rstrip('!').rstrip('.').strip()

    if text_normalized in SIMPLE_ANSWERS:
        await message.reply(SIMPLE_ANSWERS[text_normalized])
        return True
    if text in SIMPLE_ANSWERS:
        await message.reply(SIMPLE_ANSWERS[text])
        return True
    return False


async def process_public_commands(message: types.Message):
    text = message.text.lower().strip()

    if PAYMENTS_ENABLED:
        user_id = message.from_user.id
        base_command = text.split()[0] if text else ""
        cost = COMMAND_COSTS.get(base_command, 0)

        if cost > 0 and user_id not in VIP_IDS:
            has_tokens = await tokens_db.has_enough_tokens(user_id, cost)
            if not has_tokens:
                balance = await tokens_db.get_balance(user_id)
                error_msg = (
                    "<b>┌─ ⛽ БАК ПУСТ</b>\n"
                    f"<b>├─</b> Эта команда стоит <b>{cost}</b> токенов.\n"
                    f"<b>├─</b> У тебя осталось: <b>{balance}</b>.\n"
                    "<b>└─</b> Баланс восполнится завтра, или ты можешь его пополнить."
                )
                await message.reply(error_msg)
                return True

        if text == "!баланс":
            return await cmd_balance(message)

    if text.startswith("!погода"):
        return await cmd_weather(message)

    if text.startswith("!ии"):
        return await cmd_ai(message)

    if text.startswith("!нейрохам"):
        return await cmd_ai_ham(message)

    if text.startswith("!скачать"):
        await cmd_download_yt(message)
        return True

    if text.startswith("!музыка") or text.startswith("!трек"):
        return await cmd_music(message)

    if text.startswith("!курс"):
        return await cmd_currency(message)

    commands = {
        "!старт": cmd_start,
        "!помощь": cmd_help,
        "!анекдот": cmd_joke,
        "!мем": cmd_meme,
        "!о_боте": cmd_about,
        "!donut": cmd_donut,
        "!рп": cmd_rp_commands,
        "!настройки": cmd_nsfw_settings,
        "!расшифровка": cmd_transcribe,
        "!перевести": cmd_translate,
        "!прайс": cmd_prices,
        "!цены": cmd_prices
    }

    if text in commands:
        return await commands[text](message)

    if AUTO_REPLY_ENABLED:
        if not its_me(message.from_user.id) or REPLY_TO_OWNER:
            if await handle_simple_answers(message):
                return True

            if await handle_keywords(message):
                return True

    return False

from aiogram import types
from config import KEYWORD_REACTIONS, SIMPLE_ANSWERS
from config import SFW_RP_ACTIONS, NSFW_RP_ACTIONS
from bot.utils.user_settings import user_settings_db
from bot.state import state
from bot.utils.helpers import its_me
from bot.utils.joke_api import cmd_joke
from bot.utils.meme_api import cmd_meme
from bot.utils.weather_api import cmd_weather
from bot.utils.ai_api import cmd_ai
from bot.utils.database import db
from bot.handlers.nsfw_settings import cmd_nsfw_settings
from functools import lru_cache
import logging

logger = logging.getLogger(__name__)

@lru_cache(maxsize=1)
def get_public_help_text(is_away_mode: bool = False):
    status_emoji = "🚶‍♂️" if is_away_mode else "🟢"
    status_text = "режим ОТОШЁЛ активен" if is_away_mode else "режим ОНЛАЙН"

    return (
        "<b>┌─ 🤖 ДОСТУПНЫЕ КОМАНДЫ</b>\n"
        "<b>├─ 🎭</b> <code>!анекдот</code>\n"
        "<b>├─ 🖼️</b> <code>!мем</code>\n"
        "<b>├─ 🌤️</b> <code>!погода</code> [город]\n"
        "<b>├─ 🧠</b> <code>!ии [текст]</code>\n"
        "<b>├─ ℹ️</b> <code>!помощь</code>\n"
        "<b>├─ 🎭</b> <code>!рп</code>\n"
        "<b>├─ ⚙️</b> <code>!настройки</code>\n"
        "<b>├─ 🤖</b> <code>!о_боте</code>\n"
        "<b>├─ 🍩</b> <code>!donut</code>\n"
        "<b>│</b>\n"
        "<b>├─ 🔗 <i>Отправь ссылку на музыку/видео</i></b>\n"
        "<b>├─   Она сохранится и появится у владельца в !ссылки</b>\n"
        "<b>│</b>\n"
        f"<b>├─ {status_emoji} Статус:</b> {status_text}\n"
        f"<b>└─ 🤖 Автоответ:</b> Мгновенный при включённом режиме"
    )

def get_rp_commands(user_id: int = None):
    sfw_list = []
    for cmd, action in SFW_RP_ACTIONS.items():
        emoji = action[0] if action else "🎭"
        sfw_list.append(f"<b>├─ {emoji}</b> <code>{cmd}</code>")

    sfw_text = "\n".join(sfw_list)
    result = f"<b>┌─ 🎭 SFW RP КОМАНДЫ</b>\n{sfw_text}"

    if user_id and user_settings_db.get_nsfw_setting(user_id):
        nsfw_list = []
        for cmd, action in NSFW_RP_ACTIONS.items():
            emoji = action[0] if action else "🎭"
            nsfw_list.append(f"<b>├─ {emoji}</b> <code>{cmd}</code>")

        nsfw_text = "\n".join(nsfw_list)
        result += f"\n<b>│</b>\n<b>├─ 🔞 NSFW RP КОМАНДЫ (18+)</b>\n{nsfw_text}"

    result += "\n<b>│</b>\n<b>└─</b> Ответь на сообщение и напиши: [команда] &lt;слова&gt;\n"
    return result

async def cmd_start(message: types.Message):
    await message.reply(
        "<b>┌─ 🤖 ДОБРО ПОЖАЛОВАТЬ</b>\n"
        "├─ Я многофункциональный бот для этого чата.\n"
        "├─ Доступно:\n"
        "├─ 🎭 Мемы: <code>!мем</code>\n"
        "├─ 🎭 Анекдоты: <code>!анекдот</code>\n"
        "├─ 🌤️ Погода: <code>!погода</code> [город]\n"
        "├─ 🧠 ИИ: <code>!ии</code> [запрос]\n"
        "├─ 🎮 RP-команды\n"
        "├─ 📎 Ссылки владельцу\n"
        "└─ 📘 Полный список: <code>!помощь</code>"
    )

    db.increment_commands()
    db.log_command("!старт", message.from_user.id)
    return True

async def cmd_help(message: types.Message):
    is_away = await state.is_away_mode
    help_text = get_public_help_text(is_away)

    await message.reply(help_text)
    db.increment_commands()
    db.log_command("!помощь", message.from_user.id)
    return True

async def cmd_rp_commands(message: types.Message):
    user_id = message.from_user.id
    await message.reply(get_rp_commands(user_id))
    db.increment_commands()
    db.log_command("!рп", message.from_user.id)
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
        "<b>├─  •</b> Анекдоты из API\n"
        "<b>├─  •</b> Мемы с описанием (API: <a href='https://apileague.com/'>API League</a>)\n"
        "<b>├─  •</b> Погода в любом городе\n"
        "<b>├─  •</b> Локальный ИИ через Ollama\n"
        "<b>├─  •</b> Простые ответы на вопросы\n"
        "<b>├─  •</b> Реакции на ключевые слова\n"
        "<b>├─ 💻 Разработчик:</b> <a href='https://t.me/an1onime'>Lonewolf239</a> (<a href='https://github.com/Lonewolf239'>GitHub</a>)\n"
        "<b>├─ 📊 Статистика:</b> <code>!статистика</code> (только для владельца)\n"
        "<b>└─ 🎭 Для RP команд:</b> ответь на сообщение и напиши <code>!обнять</code>"
    )
    await message.reply(about_text, disable_web_page_preview=True)
    db.increment_commands()
    db.log_command("!о_боте", message.from_user.id)
    return True

async def cmd_donut(message: types.Message):
    donut_text = (
        "<b>┌─ 🍩 ПОДДЕРЖАТЬ РАЗРАБОТЧИКА</b>\n"
        "<b>├─ 💖 Если тебе нравится бот и ты хочешь помочь\n├─ его развитию:</b>\n"
        "<b>│</b>\n"
        "<b>├─ 🔗 DonationAlerts:</b>\n"
        "<b>├─</b> https://www.donationalerts.com/r/lonewolf239\n"
        "<b>│</b>\n"
        "<b>├─ 💳 Также можно через СБП или карту по запросу</b>\n"
        "<b>│</b>\n"
        "<b>├─ 🙏 Спасибо за поддержку! ❤️</b>\n"
        "<b>└─ 🍩 Даже маленькая сумма помогает боту жить!</b>"
    )
    await message.reply(donut_text, disable_web_page_preview=True)
    db.increment_commands()
    db.log_command("!donut", message.from_user.id)
    return True

async def handle_keywords(message: types.Message):
    text = message.text.strip().lower()

    import string
    text_clean = text.translate(str.maketrans('', '', string.punctuation))

    for keyword, reply in KEYWORD_REACTIONS.items():
        if keyword in text or keyword in text_clean:
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
    if not message.text:
        return False

    text = message.text.strip()

    if text.startswith("!погода"):
        return await cmd_weather(message)

    if text.startswith("!ии"):
        return await cmd_ai(message)

    commands = {
        "!старт": cmd_start,
        "!помощь": cmd_help,
        "!анекдот": cmd_joke,
        "!мем": cmd_meme,
        "!о_боте": cmd_about,
        "!donut": cmd_donut,
        "!рп": cmd_rp_commands,
        "!настройки": cmd_nsfw_settings,
    }

    if text in commands:
        return await commands[text](message)

    if await handle_simple_answers(message):
        return True

    if not its_me(message.from_user.id):
        if await handle_keywords(message):
            return True

    return False

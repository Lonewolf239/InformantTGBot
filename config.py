import os
import json
from dotenv import load_dotenv

load_dotenv()

# ==========================================
# CONFIG LOADER
# ==========================================


def load_json_config(filename):
    path = os.path.join("config", filename)
    with open(path, "r", encoding="utf-8") as file:
        return json.load(file)


# ==========================================
# OWNER & ACCESS CONTROL
# ==========================================

BOT_TOKEN = os.getenv("BOT_TOKEN")
OWNER_ID = int(os.getenv("OWNER_ID", "0"))

if OWNER_ID == 0:
    raise ValueError("OWNER_ID не задан в .env!")

vip_str = os.getenv("VIP_IDS", "")
VIP_IDS = set(map(int, filter(None, vip_str.split(",")))) if vip_str else set()
VIP_IDS.add(OWNER_ID)

BOT_LINK = "https://t.me/Lonewolf239_informantBOT"

# ==========================================
# PAYMENTS & TOKEN ECONOMY
# ==========================================

YOOKASSA_SHOP_ID = os.getenv("YOOKASSA_SHOP_ID", "")
YOOKASSA_SECRET_KEY = os.getenv("YOOKASSA_SECRET_KEY", "")

USE_WEBHOOKS = False

DEFAULT_DAILY_TOKENS = 50
TOKEN_PRICE_RUB = 2
MIN_TOKENS_BUY = 50
MAX_TOKENS_BUY = 5000
TOKEN_PACKAGES = [50, 100, 250, 500, 1000, 5000]

# ==========================================
# UNIFIED COMMAND REGISTRY (Icons, Names, Prices, Arguments, Description)
# ==========================================

HELP_GROUPS = {
    "ai": "🧠 Нейросети и Персоны",
    "media": "🎬 Медиа и Загрузки",
    "fun": "🎭 Развлечения и Игры",
    "tools": "🛠 Полезные утилиты",
}

# ⚙️ INSTRUCTIONS FOR DISABLING API/COMMANDS:
# To completely disable any command (for example, if an API is temporarily unavailable),
# add the "disabled": True parameter to its settings.
# A disabled command will automatically disappear from the !помощь and !прайс menus,
# and if a user tries to call it, the bot will notify them that it is temporarily unavailable.
#
# Example of disabling:
# !анекдот": {"icon": "🎭", "name": "Анекдот", "cost": 1, "desc": "случайный анекдот", "disabled": True, "disabled_reason": "неоплаченное API"},
# ==========================================
COMMAND_METADATA = load_json_config("commands.json")
COMMAND_ALIASES = load_json_config("aliases.json")
OWNER_COMMAND_METADATA = load_json_config("owner_commands.json")

COMMAND_COSTS = {
    cmd: data["cost"] for cmd, data in COMMAND_METADATA.items() if data["cost"] > 0
}

# ==========================================
# THIRD-PARTY API SETTINGS
# ==========================================

# Jokes
USER_PROFILE = {
    "http_method": "POST",
    "pid": os.getenv("API_PID"),
    "key": os.getenv("API_KEY"),
}
API_SETTINGS = {"lang": 1, "note": 1, "censor": 0, "markup": 0}

# Memes
MEME_API_KEY = os.getenv("MEME_API_KEY")
MEME_API_URL = "https://api.apileague.com/retrieve-random-meme"
MEME_MAX_AGE_DAYS = 67
MEME_MIN_RATING = 0.9

# Weather
OPENWEATHER_API_KEY = os.getenv("OPENWEATHER_API_KEY")
WEATHER_GEO_URL = "http://api.openweathermap.org/geo/1.0/direct"
WEATHER_API_URL = "https://api.openweathermap.org/data/2.5/weather"
WEATHER_FORECAST_URL = "https://api.openweathermap.org/data/2.5/forecast"
TRANSLATE_API_URL = "https://translate.googleapis.com/translate_a/single"

# ==========================================
# AI SETTINGS (Ollama & Groq)
# ==========================================

AI_PROVIDER = "groq"  # "groq" / "local"

OLLAMA_BASE_URL = "http://127.0.0.1:11434"
OLLAMA_MODEL = "qwen2.5:3b"
OLLAMA_VISION_MODEL = "qwen2.5vl:3b"

groq_keys_str = os.getenv("GROQ_API_KEYS", "")
GROQ_API_KEYS = [k.strip() for k in groq_keys_str.split(",") if k.strip()]
GROQ_MODEL = "llama-3.3-70b-versatile"
GROQ_VISION_MODEL = "qwen/qwen3.6-27b"

AI_MAX_REPLY_LEN = 3800
AI_REQUEST_TIMEOUT = 300
AI_AUDIO_EXTRA_COST = 3
AI_VISION_EXTRA_COST = 5

AI_PERSONAS = load_json_config("personas.json")

# ==========================================
# SPEECH RECOGNITION (Whisper)
# ==========================================

WHISPER_MODEL = "base"
WHISPER_MAX_DURATION_SECONDS = 360
WHISPER_MAX_FILE_SIZE_MB = 20
WHISPER_TIMEOUT = 3000.0
HF_TOKEN = os.getenv("HF_TOKEN", "")
WHISPER_DIARIZATION_EXTRA_COST = 10

# ==========================================
# DOWNLOAD SETTINGS (YouTube)
# ==========================================

YT_DOWNLOAD_DIR = "downloads"
YT_MAX_FILE_SIZE_MB = 50
COOKIES_FILE = "cookies.txt"

# ==========================================
# EXTERNAL API KEYS
# ==========================================

# Kinopoisk Api Unofficial
KINOPOISK_API_KEY = os.getenv("KINOPOISK_API_KEY", "")

# pollinations.ai
POLLINATIONS_API_KEY = os.getenv("POLLINATIONS_API_KEY", "")

# NewsAPI.org
NEWS_API_KEY = os.getenv("NEWS_API_KEY", "")

# Unsplash Developers
UNSPLASH_API_KEY = os.getenv("UNSPLASH_API_KEY", "")

# Ticketmaster Developer Portal
TICKETMASTER_API_KEY = os.getenv("TICKETMASTER_API_KEY", "")

# ==========================================
# TEXTS AND DICTIONARIES
# ==========================================

WELCOME_TEXT = (
    "<b>┌─ 🤖 ДОБРО ПОЖАЛОВАТЬ</b>\n"
    "├─ Я многофункциональный бот этого чата.\n"
    "├─ Доступно:\n"
    "├─ 🎭 Мемы: <code>!мем</code>\n"
    "├─ 🎭 Анекдоты: <code>!анекдот</code>\n"
    "├─ 🌤️ Погода: <code>!погода</code> [город]\n"
    "├─ 🧠 ИИ: <code>!ии</code> [запрос]\n"
    "├─ 🎙️ Расшифровка речи: <code>!расшифровка</code>\n"
    "├─ 🌐 Перевод видео: <code>!перевести</code>\n"
    "├─ 🎮 RP-команды: <code>!рп</code>\n"
    "├─ ⚙️ Настройки: <code>!настройки</code>\n"
    "└─ 📘 Полный список: <code>!помощь</code>"
)

AWAY_MESSAGES = load_json_config("away_messages.json")
KEYWORD_REACTIONS = load_json_config("keyword_reactions.json")
SFW_RP_ACTIONS = load_json_config("sfw_rp_actions.json")
NSFW_RP_ACTIONS = load_json_config("nsfw_rp_actions.json")
SIMPLE_ANSWERS = load_json_config("simple_answers.json")
BACKUP_JOKES = load_json_config("backup_jokes.json")

NSFW_ENABLED_BY_DEFAULT = 0

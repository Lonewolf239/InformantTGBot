[![Python](https://img.shields.io/badge/Python-3.10+-2D2D2D?style=for-the-badge&logo=python)](https://python.org)
[![Aiogram](https://img.shields.io/badge/Aiogram-3.x-2D2D2D?style=for-the-badge&logo=telegram)](https://docs.aiogram.dev)
[![Ollama](https://img.shields.io/badge/Ollama-Local%20AI-2D2D2D?style=for-the-badge)](https://ollama.ai)

### Languages

[![EN](https://img.shields.io/badge/README-EN-2D2D2D?style=for-the-badge&logo=github&logoColor=FFFFFF)](./README.md)
[![RU](https://img.shields.io/badge/README-RU-2D2D2D?style=for-the-badge&logo=google-translate&logoColor=FFFFFF)](./README-RU.md)

# InformantTGBot — Telegram Business Assistant

**⚠️ This bot is Russian‑only. All commands, responses, and interface are in Russian.**  
Asynchronous Telegram bot with local AI (Ollama), speech recognition (Whisper), video/audio download, memes, RP actions, away mode, link saving, **token economy** and **paid commands** (optional).

```bash
git clone https://github.com/Lonewolf239/InformantTGBot.git
cd InformantTGBot
pip install -r requirements.txt
cp dotenv_template .env
python main.py
```

---

## Features

<!-- FEATURES_TABLE_START -->
| | Feature | Description |
|---|---------|-------------|
| 🌐 | **Переводчик** | `!перевести` — Translates text with voiceover integration |
| 👾 | **Шакализатор** | `!шакал -начало` — Generates a glitch for two videos using a bot |
| 🎧 | **Замена звука** | `!звук` — Replaces the sound in a video with an audio file |
| 🎙️ | **Расшифровка речи** | `!расшифровка` — Decrypts text from audio/video |
| 🧠 | **ИИ-помощник** | `!ии [текст]` — Generates answers to questions using a local neural network |
| 🤬 | **Нейрохам** | `!нейрохам [текст]` — Generates aggressive responses to requests |
| 🛋 | **ИИ-Психолог** | `!психолог [текст]` — Finds suitable empathetic conversation |
| 📝 | **Краткий пересказ** | `!пересказ [текст]` — Retells long texts into short versions |
| 🤓 | **ИИ-Душнила** | `!душнила [текст]` — Responds stuffily and meticulously to requests |
| 💻 | **Senior ИИ** | `!синьор [текст]` — Bot answers requests from burnt out programmers |
| 🧢 | **ИИ-Гопник** | `!гопник [текст]` — Answers queries in the format !Gopnik in terms of concepts |
| 🤡 | **ИИ-Шутник** | `!шутник [тема]` — AI Joker generates summer jokes |
| 🧚 | **ИИ-Сказочник** | `!сказка [тема]` — AI Storyteller composes fairy tales and stories |
| 👵 | **ИИ-Бабка** | `!бабка [тема]` — AI Grandma grumbles like an old neighbor from the entrance |
| 🥴 | **ИИ-Алкаш** | `!алкаш [тема]` — AI Drunk broadcasts from a state of deep drinking |
| 🔊 | **Озвучка текста** | `!озвучка` — Generates an audio recording with spoken text |
| 🔊 | **Мемные звуки** | `!инстант [запрос]` — Downloads meme sounds from social networks |
| 🎬 | **Загрузчик медиа** | `!скачать [ссылка]` — Loads media from social networks and YouTube |
| 🎵 | **Поиск музыки** | `!трек [название]` — Finds and downloads songs on request |
| 🎤 | **Поиск по тексту** | `!по_тексту [слова из песни]` — Finds songs by passage in the text |
| 📚 | **Википедия** | `!вики [запрос]` — Finds articles on Wikipedia |
| 🎬 | **Кино-Поиск** | `!кино [название]` — Shows a movie card from Kinopoisk |
| 🪙 | **Курс Криптовалют** | `!курс_крипты` — Finds and shows rates of top cryptocurrencies |
| 🔍 | **Поиск картинок** | `!картинка [запрос]` — Finds images by request on social networks |
| 🌤️ | **Погода** | `!погода [город]` — Finds and shows current weather |
| 🖼️ | **Мем** | `!мем [избранное]` — Finds and shows random memes |
| 🐱 | **Котёнок** | `!кот` — Finds and shows a random cat |
| 📖 | **Факт** | `!факт` — Finds and displays a random fact from Wikipedia |
| 🔎 | **Поиск в сети** | `!поиск [запрос]` — Finds information on the Internet upon request |
| 🔮 | **Прогноз** | `!прогноз` — Finds a random forecast in the specified city |
| 💭 | **Цитата** | `!цитата` — Finds and shows a wise thought |
| 📱 | **QR-код** | `!qr [текст]` — Generates QR codes quickly |
| 🎰 | **Рулетка** | `!рулетка [ставка]` — Generates gambling with tokens |
| ⚔️ | **Дуэль** | `!дуэль [ставка]` — Challenges you to a duel for tokens |
| 🎭 | **RP Команды** | `!рп` — Shows a list of RP commands |
| 💱 | **Курс Валют** | `!курс [сумма] [валюты]` — Converts currency from specified rates |
| 🔀 | **Алиасы** | `!алиасы` — Shows a list of all command synonyms |
| 💳 | **Баланс кошелька** | `!баланс` — Finds balance in wallet and token value |
| 💰 | **Прайс-лист** | `!прайс` — Finds the price of a query in the specified command |
| ⚙️ | **Настройки** | `!настройки` — Configures bot settings (NSFW, etc.) |
| 🤖 | **О боте** | `!о_боте` — Finds technical information about the bot |
| 🍩 | **Донат** | `!donut` — Supports the bot via donation |
| ℹ️ | **Помощь** | `!помощь` — Finds the help tab in the menu |
| 🚀 | **Старт** | `!старт` — Sends a welcome message |
| 📰 | **Новости** | `!новости` — Shows top news |
| 🎟 | **Афиша** | `!афиша` — Finds event information for today |
| 🖼 | **Обои** | `!обои` — Generates juicy 4K wallpapers |
| 🚫 | **Отключенные команды** | `!отключенные` — Disables broken commands and shows reasons |
| 👑 | **Owner Commands** | `---` |
| 🚶‍♂️ | **Отошёл** | `!отошёл` — Finds and turns on auto answer mode |
| 🏠 | **Вернулся** | `!вернулся` — Turns off auto-reply mode when the bot returns |
| 📊 | **Статус** | `!статус` — Shows the current status of the bot |
| 📈 | **Статистика** | `!статистика` — Shows full bot statistics |
| ⏱ | **Сброс таймеров** | `!сброс_таймеров` — Deletes current session data |
| 🧹 | **Очистить статус** | `!очистить_статус [id]` — Deletes a user status |
| 🔗 | **Ссылки** | `!ссылки` — Manages bot links |
| 📊 | **Статистика ссылок** | `!линкстат` — Shows link click statistics |
| ⏳ | **Ждущие** | `!ждущие` — Shows a list of waiting messages |
| 🔞 | **NSFW** | `!nsfw` — Shows statistics of NSFW settings |
| ⚙️ | **Система** | `!система` — Finds system settings and shows them to the user |
<!-- FEATURES_TABLE_END -->

---

## Commands (all commands are in Russian)

<!-- COMMANDS_SECTION_START -->
### Owner (`!ownerhelp`)
- `!отошёл` – Enable auto answer mode
- `!вернулся` – Turn off auto answer mode
- `!статус` – Current status of the bot
- `!статистика` – Full bot statistics
- `!сброс_таймеров` – Reset current session
- `!очистить_статус [id]` – Clear user status
- `!ссылки` – Bot link management
- `!линкстат` – Link click statistics
- `!ждущие` – Waiting List
- `!nsfw` – NSFW Settings Statistics
- `!система` – System Settings

### Public (`!помощь`)
- `!перевести` – translation and voice acting
- `!шакал -начало` – merges 2 videos (answer the 1st video with a command from the 2nd)
- `!звук` – replaces sound in video (reply to video with audio file)
- `!расшифровка` – text from audio/video
- `!ии [текст]` – request to local neural network
- `!нейрохам [текст]` – aggressive AI response
- `!психолог [текст]` – empathetic AI that will listen and support
- `!пересказ [текст]` – squeezing out the main points from a large text
- `!душнила [текст]` – stuffy and picky answer
- `!синьор [текст]` – response from a burned out programmer
- `!гопник [текст]` – answer by concept
- `!шутник [тема]` – makes up jokes on the fly
- `!сказка [тема]` – writes fairy tales and stories
- `!бабка [тема]` – grumbles like a grandma at the entrance
- `!алкаш [тема]` – broadcasts from a state of deep drinking
- `!озвучка` – text to voice translation
- `!инстант [запрос]` – search and download meme sounds
- `!скачать [ссылка]` – download from YouTube, TikTok, etc.
- `!трек [название]` – search and download music
- `!по_тексту [слова из песни]` – find a song by text passage
- `!вики [запрос]` – search on Wikipedia
- `!кино [название]` – movie card from Kinopoisk
- `!курс_крипты` – top coin rates in $
- `!картинка [запрос]` – search for images on the web
- `!погода [город]` – current weather
- `!мем [избранное]` – random meme or from favorites
- `!кот` – random cat
- `!факт` – random fact from Wikipedia
- `!поиск [запрос]` – search for information on the Internet (6 results)
- `!прогноз` – random forecast for the day
- `!цитата` – wise thought
- `!qr [текст]` – quickly generate a QR code
- `!рулетка [ставка]` – gambling with tokens
- `!дуэль [ставка]` – challenge to a duel for tokens
- `!рп` – list of RP commands
- `!курс [сумма] [валюты]` – currency converter
- `!алиасы` – list of all command synonyms
- `!баланс` – wallet and token purchase
- `!прайс` – cost of commands
- `!настройки` – bot settings (NSFW, etc.)
- `!о_боте` – technical information
- `!donut` – support the author
- `!помощь` – this is the menu
- `!старт` – welcome message
- `!новости` – main news
- `!афиша` – where to go today
- `!обои` – juicy pictures 4k
- `!отключенные` – list of broken commands and reasons

**RP commands** (reply to a message):
SFW: `!обнять`, `!поцеловать`, `!ударить`, `!шлепнуть`, `!укусить`, `!погладить`, `!пнуть`, `!толкнуть`, `!ущипнуть`, `!прижать_к_стене`, `!ткнуть_по_носику`, `!лизнуть`, `!задушить`.
When NSFW enabled: `!отсосать`, `!выебать`, `!трахнуть`, `!кончить`, `!раздеть`, `!оттрахать`, `!поставить_на_колени`, `!схватить_за_член`, `!схватить_за_жопу`, `!отлизать`.
<!-- COMMANDS_SECTION_END -->

---

## Configuration (`.env`)

```ini
BOT_TOKEN=xxx
OWNER_ID=123456789
API_PID=xxx          # for jokes
API_KEY=xxx          # for jokes
MEME_API_KEY=xxx
OPENWEATHER_API_KEY=xxx
KINOPOISK_API_KEY=xxx

# Optional payments (YooKassa)
YOOKASSA_SHOP_ID=xxx
YOOKASSA_SECRET_KEY=xxx

# VIP users (comma‑separated IDs, bypass token costs)
VIP_IDS=123456,789012

# Optional image generation (pollinations.ai)
POLLINATIONS_API_KEY=xxx
```

### Additional Requirements (outside Python dependencies)

- **Ollama** – install from [ollama.ai](https://ollama.ai), pull model: `ollama pull qwen2.5:3b` (adjust in `config.py` if needed).
- **Whisper** – automatically downloads the `base` model on first use (~1GB RAM).
- **FFmpeg** – needed for audio/video processing (dubbing, track replacement).
- **Edge‑TTS** – used for voice synthesis; works without additional keys.
- **cookies.txt** – place a Netscape‑format cookies file in the root folder to bypass YouTube restrictions (403, age‑restricted content).

---

## Databases

- `bot_stats.db` – global stats, user stats, command history
- `bot_links.db` – saved URLs (type, sender, viewed)
- `user_settings.db` – NSFW preferences
- `bot_tokens.db` – user token balances

---

## Notes

- Daily token limit is replenished every midnight (`DEFAULT_DAILY_TOKENS = 50`).
- Commands cost tokens (see `!прайс`). VIP users (including owner) pay nothing.
- Payments via YooKassa are optional; set `PAYMENTS_ENABLED = True` in `config.py` (default is `True` if credentials provided).
- The bot can run with long polling (default) or webhooks (set `USE_WEBHOOKS = True` for YooKassa callbacks).
- For business accounts, the bot handles `business_message` and `business_connection` events.

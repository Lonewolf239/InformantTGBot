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
| 🌐 | **Переводчик** | `!перевести` — Translates text |
| 👾 | **Шакализатор** | `!шакал -начало` — Merges videos |
| 🎧 | **Замена звука** | `!звук` — Replaces sound |
| 🎙️ | **Расшифровка речи** | `!расшифровка` — Transcribes speech |
| 🧠 | **ИИ-помощник** | `!ии [текст]` — Helps AI |
| 🤬 | **Нейрохам** | `!нейрохам [текст]` — Responds rudely |
| 🛋 | **ИИ-Психолог** | `!психолог [текст]` — Listens to problems |
| 📝 | **Краткий пересказ** | `!пересказ [текст]` — Retells text |
| 🤓 | **ИИ-Душнила** | `!душнила [текст]` — Suffocates with questions |
| 💻 | **Senior ИИ** | `!синьор [текст]` — Responds like a senior |
| 🧢 | **ИИ-Гопник** | `!гопник [текст]` — Answers based on concepts |
| 🤡 | **ИИ-Шутник** | `!шутник [тема]` — Makes up jokes |
| 🧚 | **ИИ-Сказочник** | `!сказка [тема]` — Tells stories |
| 👵 | **ИИ-Бабка** | `!бабка [тема]` — Grumbles like a grandma |
| 🥴 | **ИИ-Алкаш** | `!алкаш [тема]` — Talks drunk |
| 💸 | **ИИ-Коуч** | `!коуч [текст]` — Sells success |
| 📱 | **ИИ-Зумер** | `!зумер [текст]` — Speaks slang |
| 🛸 | **Конспиролог** | `!шапочка [текст]` — Sees conspiracies |
| 🛒 | **AliExpress** | `!алиэкспрес [текст]` — Sells through aliexpress |
| 🔊 | **Озвучка текста** | `!озвучка` — Voices text |
| 🔊 | **Мемные звуки** | `!инстант [запрос]` — Searches for meme sounds |
| 🎬 | **Загрузчик медиа** | `!скачать [ссылка]` — Downloads media |
| 📝 | **Текст из YouTube** | `!ютуб_текст [ссылка]` — Translates video |
| 🎵 | **Поиск музыки** | `!трек [название]` — Finds music |
| 🎤 | **Поиск по тексту** | `!по_тексту [слова из песни]` — Finds a song |
| 📚 | **Википедия** | `!вики [запрос]` — Searches Wikipedia |
| 🎬 | **Кино-Поиск** | `!кино [название]` — Shows a movie |
| 🪙 | **Курс Криптовалют** | `!курс_крипты` — Shows rates |
| 🔍 | **Поиск картинок** | `!картинка [запрос]` — Finds images |
| 🌤️ | **Погода** | `!погода [город]` — Shows weather |
| 🖼️ | **Мем** | `!мем [избранное]` — Displays meme |
| 🐱 | **Котёнок** | `!кот` — Displays kitty |
| 📖 | **Факт** | `!факт` — Displays fact |
| 🔎 | **Поиск в сети** | `!поиск [запрос]` — Searches for information |
| 🔮 | **Прогноз** | `!прогноз` — Displays forecast |
| 💭 | **Цитата** | `!цитата` — Displays quote |
| 📱 | **QR-код** | `!qr [текст]` — Generates qr |
| 🎰 | **Рулетка** | `!рулетка [ставка]` — Plays roulette |
| ⚔️ | **Дуэль** | `!дуэль [ставка]` — Challenges to a duel |
| 🎭 | **RP Команды** | `!рп` — Displays rp |
| 💱 | **Курс Валют** | `!курс [сумма] [валюты]` — Shows exchange rate |
| 🔀 | **Алиасы** | `!алиасы` — Outputs all aliases |
| 💳 | **Баланс кошелька** | `!баланс` — Shows balance |
| 💰 | **Прайс-лист** | `!прайс` — Displays pricing |
| ⚙️ | **Настройки** | `!настройки` — Changes settings |
| 🤖 | **О боте** | `!о_боте` — Shows information |
| 🍩 | **Донат** | `!donut` — Supports the author |
| ℹ️ | **Помощь** | `!помощь` — Shows help |
| 🚀 | **Старт** | `!старт` — Launches the bot |
| 📰 | **Новости** | `!новости` — Shows news |
| 🎟 | **Афиша** | `!афиша` — Shows the poster |
| 🖼 | **Обои** | `!обои` — Shows wallpapers |
| 🚫 | **Отключенные команды** | `!отключенные` — Shows disabled |
| 💬 | **ИИ-ЧАТ** | `!ии_чат` — Launches chat |
| 👑 | **Owner Commands** | `---` |
| 🚶‍♂️ | **Отошёл** | `!отошёл` — Turns on autoresponse |
| 🏠 | **Вернулся** | `!вернулся` — Turns off autoresponse |
| 📊 | **Статус** | `!статус` — Shows status |
| 📈 | **Статистика** | `!статистика` — Shows statistics |
| ⏱ | **Сброс таймеров** | `!сброс_таймеров` — Resets timers |
| 🧹 | **Очистить статус** | `!очистить_статус [id]` — Clears status |
| 🔗 | **Ссылки** | `!ссылки` — Manages links |
| 📊 | **Статистика ссылок** | `!линкстат` — Shows statistics |
| ⏳ | **Ждущие** | `!ждущие` — Displays the list |
| 🔞 | **NSFW** | `!nsfw` — Checks settings |
| ⚙️ | **Система** | `!система` — Configures the system |
<!-- FEATURES_TABLE_END -->

---

## Commands (all commands are in Russian)

<!-- COMMANDS_SECTION_START -->
### Owner (`!ownerhelp`)
- `!отошёл` – Turn on autoresponse mode
- `!вернулся` – Turn off autoresponse mode
- `!статус` – Current bot operation status
- `!статистика` – Full bot statistics
- `!сброс_таймеров` – Reset current session
- `!очистить_статус [id]` – Clear user status
- `!ссылки` – Bot link management
- `!линкстат` – Link click statistics
- `!ждущие` – Waiting for response list
- `!nsfw` – NSFW settings statistics
- `!система` – System settings

### Public (`!помощь`)
- `!перевести` – translation and voiceover
- `!шакал -начало` – merges 2 videos (respond to the 1st video with the 2nd)
- `!звук` – replaces sound in video (respond to video with an audio file)
- `!расшифровка` – text from audio/video
- `!ии [текст]` – request to local neural network
- `!нейрохам [текст]` – aggressive AI response
- `!психолог [текст]` – empathic AI that listens and supports
- `!пересказ [текст]` – extracting the main point from a large text
- `!душнила [текст]` – suffocating and nitpicky response
- `!синьор [текст]` – response from a burned-out programmer
- `!гопник [текст]` – answers based on concepts
- `!шутник [тема]` – makes up jokes on the fly
- `!сказка [тема]` – makes up tales and stories
- `!бабка [тема]` – grumbles like a grandma by the entrance
- `!алкаш [тема]` – speaks from a state of deep intoxication
- `!коуч [текст]` – successful success, crypto and fictional courses
- `!зумер [текст]` – victim of TikTok, communicates in slang
- `!шапочка [текст]` – sees a conspiracy of reptiloids and 5G everywhere
- `!алиэкспрес [текст]` – answers with curved machine translation of SEO goods
- `!озвучка` – translates text into voice
- `!инстант [запрос]` – searching and downloading meme sounds
- `!скачать [ссылка]` – uploading from YouTube, TikTok, etc.
- `!ютуб_текст [ссылка]` – download video and translate to text
- `!трек [название]` – searching and downloading music
- `!по_тексту [слова из песни]` – find a song by text snippet
- `!вики [запрос]` – searching Wikipedia
- `!кино [название]` – movie card from KinoPoisk
- `!курс_крипты` – top coin rates in $
- `!картинка [запрос]` – searching for images on the web
- `!погода [город]` – current weather
- `!мем [избранное]` – random meme or favorite
- `!кот` – random kitty
- `!факт` – random fact from Wikipedia
- `!поиск [запрос]` – searching for info on the internet (6 results)
- `!прогноз` – random forecast for the day
- `!цитата` – wise thought
- `!qr [текст]` – quickly generate QR code
- `!рулетка [ставка]` – token-based games
- `!дуэль [ставка]` – challenge to a duel for tokens
- `!рп` – list of RP commands
- `!курс [сумма] [валюты]` – currency converter
- `!алиасы` – list of all command synonyms
- `!баланс` – wallet and token purchase
- `!прайс` – command cost
- `!настройки` – bot settings (NSFW etc.)
- `!о_боте` – technical information
- `!donut` – support the author
- `!помощь` – this menu
- `!старт` – welcome message
- `!новости` – main news
- `!афиша` – where to go today
- `!обои` – juicy 4k pictures
- `!отключенные` – list of non-working commands and reasons
- `!ии_чат` – interactive dialogue with personas

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

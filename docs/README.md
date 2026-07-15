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
| 🌐 | **Translator** | `!перевести` — Generates translation and voiceover |
| 👾 | **Jackalizer** | `!шакал -начало` — Generates a mixed video from two requests |
| 🎧 | **Sound replacement** | `!звук` — Generates audio files for videos |
| 🎙️ | **Speech transcript** | `!расшифровка` — Generates text from audio/video |
| 🧠 | **AI assistant** | `!ии [текст]` — Generates a response from a local neural network |
| 🤬 | **Нейрохам** | `!нейрохам [текст]` — Генерирует агрессивные ответы |
| 🛋 | **ИИ-Психолог** | `!психолог [текст]` — Отвечает эмпатичным советом пользователю |
| 📝 | **Краткий пересказ** | `!пересказ [текст]` — Генерирует краткий пересказ текста |
| 🤓 | **ИИ-Душнила** | `!душнила [текст]` — Отвечает идioticнами шутками |
| 💻 | **Senior ИИ** | `!синьор [текст]` — Отвечает в стиле выгоревшего программиста |
| 🧢 | **AI Gopnik** | `!гопник [текст]` — AI Gopnik answers by concepts |
| 🤡 | **AI Joker** | `!шутник [тема]` — Generates a joke by an AI joker |
| 🧚 | **AI Storyteller** | `!сказка [тема]` — Generates a fairy tale |
| 👵 | **AI Grandma** | `!бабка [тема]` — Gives off an unattractive grunt |
| 🥴 | **AI-Drunk** | `!алкаш [тема]` — Gives out phrases from a state of deep drinking |
| 🔊 | **Voice over text** | `!озвучка` — Generates voice reading of text |
| 🔊 | **Meme sounds** | `!инстант [запрос]` — Generates meme sounds |
| 🎬 | **Media Loader** | `!скачать [ссылка]` — Generates a video from a request |
| 🎵 | **Search music** | `!трек [название]` — Generates requests in music services |
| 🎤 | **Search by text** | `!по_тексту [слова из песни]` — Generates a request in charmpodka |
| 📚 | **Wikipedia** | `!вики [запрос]` — Generates a query to Wikipedia |
| 🎬 | **Kino-Poisk** | `!кино [название]` — Gives out a movie card from Kinopoisk |
| 🪙 | **Cryptocurrency rate** | `!курс_крипты` — Gives rates for top crypto coins in rubles |
| 🔍 | **Image search** | `!картинка [запрос]` — Generates a random picture |
| 🌤️ | **Weather** | `!погода [город]` — Generates the current weather in a message |
| 🖼️ | **Meme** | `!мем [избранное]` — Generates a random meme or from favorites |
| 🐱 | **Kitty** | `!кот` — Generates a random cat |
| 📖 | **Fact** | `!факт` — Generates a random fact from Wikipedia |
| 🔎 | **Search the web** | `!поиск [запрос]` — Generates Internet search results |
| 🔮 | **Forecast** | `!прогноз` — Generates a random forecast for the day |
| 💭 | **Quote** | `!цитата` — Generates a wise thought |
| 📱 | **QR code** | `!qr [текст]` — Generates a QR code! |
| 🎰 | **Roulette** | `!рулетка [ставка]` — Generates random game results |
| ⚔️ | **Duel** | `!дуэль [ставка]` — Generates a random opponent for a duel |
| 🎭 | **RP Teams** | `!рп` — Returns a list of RP commands |
| 💱 | **Currency rates** | `!курс [сумма] [валюты]` — Converts currencies with a bot |
| 🔀 | **Aliases** | `!алиасы` — Gives a list of all command synonyms! |
| 💳 | **Wallet balance** | `!баланс` — Corresponds with the status of the balance in the wallet |
| 💰 | **Price list** | `!прайс` — Generates a price list |
| ⚙️ | **Settings** | `!настройки` — Generates a list of bot settings |
| 🤖 | **About the bot** | `!о_боте` — Generates bot technical information |
| 🍩 | **Donat** | `!donut` — Generates a payment request |
| ℹ️ | **Help** | `!помощь` — Bot responds with available Telegram commands |
| 🚀 | **Start** | `!старт` — Displays a welcome message |
| 📰 | **News** | `!новости` — Generates a list of top news |
| 🎟 | **Афиша** | `!афиша` — Генерирует события для сегоднящнего д afteroon |
| 🖼 | **Обои** | `!обои` — Генерирует сочные картинки 4k |
| 🚫 | **Отключенные команды** | `!отключенные` — Выдает список отключенных команд |
| 👑 | **Owner Commands** | `---` |
| 🚶‍♂️ | **Отошёл** | `!отошёл` — Генерирует автоответ "Отошёл |
| 🏠 | **Вернулся** | `!вернулся` — Отключает автоответ бота |
| 📊 | **Статус** | `!статус` — Отвечает текущий статус работы бота |
| 📈 | **Статистика** | `!статистика` — Генерирует полную статистику бота |
| ⏱ | **Сброс таймеров** | `!сброс_таймеров` — Генерирует новую сессию |
| 🧹 | **Очистить статус** | `!очистить_статус [id]` — Генерирует удаление статуса пользователя |
| 🔗 | **Ссылки** | `!ссылки` — Генерирует список всех активированных ссылок |
| 📊 | **Статистика ссылок** | `!линкстат` — Генерирует статистику переходов по ссылкам |
| ⏳ | **Ждущие** | `!ждущие` — Генерирует список ждущих сообщений |
| 🔞 | **NSFW** | `!nsfw` — Выдает статистику NSFW настроек |
| ⚙️ | **Система** | `!система` — Генерирует доступ к системным настройкам |
<!-- FEATURES_TABLE_END -->

---

## Commands (all commands are in Russian)

<!-- COMMANDS_SECTION_START -->
### Owner (`!ownerhelp`)
- `!отошёл` – Включить режим автоответа
- `!вернулся` – Выключить режим автоответа
- `!статус` – Текущий статус работы бота
- `!статистика` – Полная статистика бота
- `!сброс_таймеров` – Сбросить текущую сессию
- `!очистить_статус [id]` – Очистить статус пользователя
- `!ссылки` – Управление ссылками бота
- `!линкстат` – Статистика переходов по ссылкам
- `!ждущие` – Список ожидающих ответа
- `!nsfw` – Статистика NSFW настроек
- `!система` – Системные настройки

### Public (`!помощь`)
- `!перевести` – translation and voice acting
- `!шакал -начало` – merges 2 videos (answer the 1st video with a command from the 2nd)
- `!звук` – replaces sound in video (reply to video with audio file)
- `!расшифровка` – text from audio/video
- `!ии [текст]` – request to local neural network
- `!нейрохам [текст]` – агрессивный ИИ-ответ
- `!психолог [текст]` – эмпатичный ИИ, который выслушает и поддержит
- `!пересказ [текст]` – выжимка главного из большого текста
- `!душнила [текст]` – душный и придирчивый ответ
- `!синьор [текст]` – ответ от выгоревшего программиста
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
- `!афиша` – куда сходить сегодня
- `!обои` – сочные картинки 4k
- `!отключенные` – список неработающих команд и причины

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

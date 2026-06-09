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

| | Feature | Description (commands are in Russian) |
|---|---------|----------------------------------------|
| 🤖 | **Away mode** | `!отошёл` / `!вернулся` – auto‑reply once per user (random messages) |
| 🎭 | **Jokes & Memes** | `!анекдот` / `!мем` – random jokes + favorite memes ❤️ |
| 🌤️ | **Weather** | `!погода [city]` – current conditions (city name in Russian or English) |
| 🧠 | **Local AI** | `!ии [question]` – offline Ollama (queue + message splitting) |
| 🤬 | **Rude AI** | `!нейрохам [question]` – toxic, insulting answers (experimental) |
| 🎙️ | **Speech‑to‑Text** | `!расшифровка` (reply) – extract text from voice/video/audio |
| 🌐 | **Translate & Dub** | `!перевести` (reply) – transcribe foreign speech, translate into Russian, send back with new dubbing (TTS) |
| 🎬 | **Media Download** | `!скачать [url] [options]` – supports YouTube, TikTok, Twitter/X, Instagram, VK, Reddit, playlists (options: random, range, count) |
| 🎵 | **Music Search** | `!музыка` / `!трек [query]` – search and download music (audio) |
| 💱 | **Currency Converter** | `!курс [amount] [from] [to]` – real‑time exchange rates |
| 💰 | **Token System** | Daily free tokens, command costs, optional top‑up via YooKassa |
| 🎮 | **RP commands** | Reply + `!обнять`, `!выебать` (NSFW requires opt‑in) |
| 🔗 | **Link saver** | Auto‑save music/video URLs → owner menu `!ссылки` |
| 👑 | **Owner panel** | Stats, waiting list, reset, link stats, NSFW stats, clear user status |
| 🔞 | **NSFW toggle** | `!настройки` – per‑user switch for NSFW RP actions |
| 📊 | **Statistics** | `!статистика` – messages, top users, commands, uptime |
| 🎲 | **Games** | `!рулетка [bet]`, `!дуэль [bet]` – gamble tokens with other users |
| 🐱 | **Cute animals** | `!кот` – random cat picture |
| 📚 | **Wikipedia** | `!вики [query]` – search Wikipedia |
| 🎬 | **Movie info** | `!кино [title]` – movie card from Kinopoisk |
| 🔍 | **Image search** | `!картинка [query]` – find images on the web |
| 📱 | **QR code** | `!qr [text]` – generate QR code instantly |
| 🔊 | **Text-to-Speech** | `!озвучка [text]` – convert text to voice (Edge‑TTS) |
| 🔮 | **Fortune** | `!прогноз` – random daily prediction |
| 💭 | **Quote** | `!цитата` – random wise saying |
| 🪙 | **Crypto rates** | `!курс_крипты` – top cryptocurrencies in USD |
| 🔀 | **Aliases** | `!алиасы` – list all command synonyms |

---

## Commands (all commands are in Russian)

### Owner (`!ownerhelp`)
- `!отошёл` – enable away mode
- `!вернулся` – disable away mode
- `!статус` – show current away mode state
- `!статистика` – detailed bot statistics
- `!ждущие` – list of users who messaged during away mode
- `!сброс_таймеров` – clear auto‑reply flags for all users
- `!очистить_статус <id>` – clear auto‑reply flag for a specific user
- `!ссылки` – view saved links (inline menu)
- `!линкстат` – statistics of saved links
- `!nsfw` – global NSFW settings stats

### Public (`!помощь`)
- `!помощь` – this menu 
- `!старт` – welcome message
- `!анекдот` – random joke
- `!мем` – random meme
- `!погода [city]` – weather forecast
- `!ии [question]` – ask local AI
- `!нейрохам [question]` – get a toxic, insulting answer (use with caution)
- `!расшифровка` (reply to voice/video/audio) – speech recognition
- `!перевести` (reply to foreign media) – translate & resend with new dubbing
- `!скачать [url] [options]` – download media (YouTube/TikTok/others)
- `!музыка` / `!трек [query]` – search and download music
- `!курс [amount] [from] [to]` – currency converter (e.g. `!курс 100 usd rub`)
- `!прайс` / `!цены` – show command costs in tokens
- `!баланс` – check token balance and top up (if payments enabled)
- `!рп` – list of RP commands
- `!настройки` – NSFW toggle
- `!о_боте` – bot info
- `!donut` – support the developer
- `!алиасы` – show command aliases
- `!рулетка [ставка]` – gamble tokens (roulette)
- `!дуэль [ставка]` – challenge another user to a duel
- `!кино [название]` – movie info from Kinopoisk
- `!qr [текст]` – generate QR code
- `!кот` – random cat picture
- `!факт` – random fact
- `!вики [запрос]` – Wikipedia search
- `!озвучка [текст]` – text‑to‑speech
- `!картинка [запрос]` – image search
- `!прогноз` – random daily forecast
- `!цитата` – random quote
- `!курс_крипты` – top crypto rates in USD

**RP commands** (reply to a message):
SFW: `!обнять`, `!поцеловать`, `!ударить`, `!шлепнуть`, `!укусить`, `!погладить`, `!пнуть`, `!толкнуть`, `!ущипнуть`, `!прижать_к_стене`, `!ткнуть_по_носику`, `!лизнуть`, `!задушить`.
When NSFW enabled: `!отсосать`, `!выебать`, `!трахнуть`, `!кончить`, `!раздеть`, `!оттрахать`, `!поставить_на_колени`, `!схватить_за_член`, `!схватить_за_жопу`, `!отлизать`.

**Download options for playlists (`!скачать`):**
- `-random` – random order (or just one random track if used alone)
- `-N` – download N tracks (e.g. `-5`)
- `-от_N` – start from track N
- `-до_N` – end at track N  
Combine examples: `!скачать -random -3` – three random tracks.

**Aliases** – many commands have synonyms (e.g. `!help` = `!помощь`, `!ai` = `!ии`). Use `!алиасы` to see all.

**Simple answers & keyword reactions** – bot replies to common phrases like “как дела” → “норм”, “пошёл нахуй” → “пошёл нахуй”, and special keywords trigger memes or social credit messages.

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

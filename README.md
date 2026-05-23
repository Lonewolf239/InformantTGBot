[![Python](https://img.shields.io/badge/Python-3.10+-2D2D2D?style=for-the-badge&logo=python)](https://python.org)
[![Aiogram](https://img.shields.io/badge/Aiogram-3.x-2D2D2D?style=for-the-badge&logo=telegram)](https://docs.aiogram.dev)
[![Ollama](https://img.shields.io/badge/Ollama-Local%20AI-2D2D2D?style=for-the-badge)](https://ollama.ai)

### Languages
[![EN](https://img.shields.io/badge/README-EN-2D2D2D?style=for-the-badge&logo=github&logoColor=FFFFFF)](./README.md)
[![RU](https://img.shields.io/badge/README-RU-2D2D2D?style=for-the-badge&logo=google-translate&logoColor=FFFFFF)](./README-RU.md)

# InformantTGBot — Telegram Business Assistant

**⚠️ This bot is Russian‑only. All commands, responses, and interface are in Russian.**  
Asynchronous Telegram bot with local AI (Ollama), speech recognition (Whisper), video/audio download, memes, RP actions, away mode, and link saving.

```bash
git clone https://github.com/Lonewolf239/InformantTGBot.git
pip install -r requirements.txt
cp dotenv_template .env
python main.py
```

---

## Features

| | Feature | Description (commands are in Russian) |
|---|---------|----------------------------------------|
| 🤖 | **Away mode** | `!отошёл` / `!вернулся` – auto‑reply once per user (random messages) |
| 🎭 | **Jokes & Memes** | `!анекдот` / `!мем` – random jokes + favourite memes ❤️ |
| 🌤️ | **Weather** | `!погода [city]` – current conditions (city name in Russian or English) |
| 🧠 | **Local AI** | `!ии [question]` – offline Ollama (queue + message splitting) |
| 🎙️ | **Speech‑to‑Text** | `!расшифровка` (reply) – extract text from voice/video/audio |
| 🌐 | **Translate & Dub** | `!перевести` (reply) – transcribe foreign speech, translate into Russian, send back with new dubbing (TTS) |
| 🎬 | **Media Download** | `!скачать [url]` – supports YouTube, TikTok, playlists (options: random, range, count) |
| 🎮 | **RP commands** | Reply + `!обнять`, `!выебать` (NSFW requires opt‑in) |
| 🔗 | **Link saver** | Auto‑save music/video URLs → owner menu `!ссылки` |
| 👑 | **Owner panel** | Stats, waiting list, reset, link stats, NSFW stats, clear user status |
| 🔞 | **NSFW toggle** | `!настройки` – per‑user switch for NSFW RP actions |
| 📊 | **Statistics** | `!статистика` – messages, top users, commands, uptime |

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
- `!расшифровка` (reply to voice/video/audio) – speech recognition
- `!перевести` (reply to foreign media) – translate & resend with new dubbing
- `!скачать [url] [options]` – download media (YouTube/TikTok)
- `!рп` – list of RP commands
- `!настройки` – NSFW toggle
- `!о_боте` – bot info
- `!donut` – support the developer

**RP commands** (reply to a message):
`!обнять`, `!поцеловать`, `!ударить`, `!шлепнуть`, `!укусить`, `!погладить`, `!пнуть`, `!толкнуть`, `!ущипнуть`, `!прижать_к_стене`, `!ткнуть_по_носику`, `!лизнуть`, `!задушить` (SFW)
When NSFW enabled: `!отсосать`, `!выебать`, `!трахнуть`, `!кончить`, `!раздеть`, `!оттрахать`, `!поставить_на_колени`, `!схватить_за_член`, `!схватить_за_жопу`, `!отлизать`.

**Download options for playlists (`!скачать`):**
- `-random` – random order (or just one random track if used alone)
- `-N` – download N tracks (e.g. `-5`)
- `-от_N` – start from track N
- `-до_N` – end at track N
Combine examples: `!скачать -random -3` – three random tracks.

---

## Configuration (`.env`)

```ini
BOT_TOKEN=xxx
OWNER_ID=123456789
API_PID=xxx          # for jokes
API_KEY=xxx          # for jokes
MEME_API_KEY=xxx
OPENWEATHER_API_KEY=xxx
```

### Additional Requirements (outside Python dependencies)
- **Ollama** – install from [ollama.ai](https://ollama.ai), pull model: `ollama pull qwen2.5:3b` (adjust in `config.py` if needed).
- **Whisper** – automatically downloads the `base` model on first use (~1GB RAM).
- **FFmpeg** – needed for audio/video processing (dubbing, track replacement).
- **Edge‑TTS** – used for voice synthesis; works without additional keys.

---

## Databases

- `bot_stats.db` – global stats, user stats, command history
- `bot_links.db` – saved URLs (type, sender, viewed)
- `user_settings.db` – NSFW preferences


[![Python](https://img.shields.io/badge/Python-3.10+-2D2D2D?style=for-the-badge&logo=python)](https://python.org)
[![Aiogram](https://img.shields.io/badge/Aiogram-3.x-2D2D2D?style=for-the-badge&logo=telegram)](https://docs.aiogram.dev)
[![Ollama](https://img.shields.io/badge/Ollama-Local%20AI-2D2D2D?style=for-the-badge)](https://ollama.ai)

# InformantTGBot — Telegram Business Assistant

Asynchronous Telegram bot with local AI, memes, RP actions, away mode, and link saving.

```bash
git clone https://github.com/Lonewolf239/InformantTGBot.git
pip install -r requirements.txt
cp dotenv_template .env
python main.py
```

---

## Features

| | Feature | Description |
|---|---------|-------------|
| 🤖 | **Away mode** | `!отошёл` / `!вернулся` — auto-reply once per user |
| 🎭 | **Jokes & Memes** | `!анекдот` / `!мем` — random + favorites ❤️ |
| 🌤️ | **Weather** | `!погода [city]` — current conditions |
| 🧠 | **Local AI** | `!ии [question]` — offline Ollama (queue + splitting) |
| 🎮 | **RP commands** | Reply + `!обнять`, `!выебать` (NSFW requires opt-in) |
| 🔗 | **Link saver** | Auto-save music/video URLs → owner menu `!ссылки` |
| 👑 | **Owner panel** | Stats, waiting list, reset, link stats |
| 🔞 | **NSFW toggle** | `!настройки` — per-user switch for NSFW RP |
| 📊 | **Statistics** | `!статистика` — messages, top users, commands, uptime |

---

## Commands

### Owner (`!ownerhelp`)
`!отошёл`, `!вернулся`, `!статус`, `!статистика`, `!ждущие`, `!ссылки`, `!линкстат`, `!сброс_таймеров`, `!очистить_статус <id>`

### Public (`!помощь`)
`!анекдот`, `!мем`, `!погода`, `!ии`, `!рп`, `!настройки`, `!о_боте`, `!donut`

---

## Configuration (`.env`)

```ini
BOT_TOKEN=xxx
OWNER_ID=123456789
API_PID=xxx
API_KEY=xxx
MEME_API_KEY=xxx
OPENWEATHER_API_KEY=xxx
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=qwen2.5:3b
```

---

## Database

- `bot_stats.db` — global stats, user stats, command history
- `bot_links.db` — saved URLs (type, sender, viewed)
- `user_settings.db` — NSFW preferences

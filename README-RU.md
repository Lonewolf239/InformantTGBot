[![Python](https://img.shields.io/badge/Python-3.10+-2D2D2D?style=for-the-badge&logo=python)](https://python.org)
[![Aiogram](https://img.shields.io/badge/Aiogram-3.x-2D2D2D?style=for-the-badge&logo=telegram)](https://docs.aiogram.dev)
[![Ollama](https://img.shields.io/badge/Ollama-Локальный%20ИИ-2D2D2D?style=for-the-badge)](https://ollama.ai)

### Languages
[![EN](https://img.shields.io/badge/README-EN-2D2D2D?style=for-the-badge&logo=github&logoColor=FFFFFF)](./README.md)
[![RU](https://img.shields.io/badge/README-RU-2D2D2D?style=for-the-badge&logo=google-translate&logoColor=FFFFFF)](./README-RU.md)

# InformantTGBot — Бизнес‑ассистент для Telegram

Асинхронный Telegram‑бот с локальным ИИ, мемами, RP действиями, режимом «отошёл» и сохранением ссылок.

```bash
git clone https://github.com/Lonewolf239/InformantTGBot.git
pip install -r requirements.txt
cp dotenv_template .env
python main.py
```

---

## Возможности

| | Функция | Описание |
|---|---------|----------|
| 🤖 | **Режим «отошёл»** | `!отошёл` / `!вернулся` — автоответ 1 раз на пользователя |
| 🎭 | **Анекдоты и мемы** | `!анекдот` / `!мем` — случайные + избранное ❤️ |
| 🌤️ | **Погода** | `!погода [город]` — текущие условия |
| 🧠 | **Локальный ИИ** | `!ии [вопрос]` — офлайн Ollama (очередь + нарезка) |
| 🎮 | **RP команды** | Ответ + `!обнять`, `!выебать` (NSFW требует включения) |
| 🔗 | **Сохранение ссылок** | Автосохранение URL → меню владельца `!ссылки` |
| 👑 | **Панель владельца** | Статистика, список ожидающих, сброс, статистика ссылок |
| 🔞 | **NSFW тумблер** | `!настройки` — per‑user переключатель NSFW RP |
| 📊 | **Статистика** | `!статистика` — сообщения, топ пользователей, команды, аптайм |

---

## Команды

### Владельца (`!ownerhelp`)
`!отошёл`, `!вернулся`, `!статус`, `!статистика`, `!ждущие`, `!ссылки`, `!линкстат`, `!сброс_таймеров`, `!очистить_статус <id>`

### Публичные (`!помощь`)
`!анекдот`, `!мем`, `!погода`, `!ии`, `!рп`, `!настройки`, `!о_боте`, `!donut`

---

## Конфигурация (`.env`)

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

## Базы данных

- `bot_stats.db` — глобальная статистика, пользователи, история команд
- `bot_links.db` — сохранённые URL (тип, отправитель, просмотрено)
- `user_settings.db` — NSFW настройки

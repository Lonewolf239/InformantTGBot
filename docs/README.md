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
python -m bot.main
```

---

## Commands (all commands are in Russian)

<!-- COMMANDS_SECTION_START -->
### 🧠 AI & Personas
| | Command | Description |
|---|---|---|
| 🧠 | `!ии [текст]` | запрос к локальной нейросети |
| 🤬 | `!нейрохам [текст]` | агрессивный ИИ-ответ |
| 🛋 | `!психолог [текст]` | эмпатичный ИИ, который выслушает и поддержит |
| 📝 | `!пересказ [текст]` | выжимка главного из большого текста |
| 🤓 | `!душнила [текст]` | душный и придирчивый ответ |
| 💻 | `!синьор [текст]` | ответ от выгоревшего программиста |
| 🧢 | `!гопник [текст]` | ответ по понятиям |
| 🤡 | `!шутник [тема]` | сочиняет анекдоты на лету |
| 🧚 | `!сказка [тема]` | сочиняет сказки и истории |
| 👵 | `!бабка [тема]` | ворчит как бабка у подъезда |
| 🥴 | `!алкаш [тема]` | вещает из состояния глубокого запоя |
| 💸 | `!коуч [текст]` | успешный успех, крипта и выдуманные курсы |
| 📱 | `!зумер [текст]` | жертва ТикТока, общается сленгом |
| 🛸 | `!шапочка [текст]` | везде видит заговор рептилоидов и 5G |
| 🛒 | `!алиэкспрес [текст]` | отвечает кривым машинным переводом SEO-товаров |
| 🔮 | `!гадалка [вопрос]` | предсказывает судьбу и раскидывает таро |
| 🗄 | `!бюрократ [текст]` | требует справки и гоняет по кабинетам |
| 🗿 | `!философ [вопрос]` | экзистенциальный кризис на любой вопрос |
| ⚔️ | `!рыцарь [текст]` | благородный воин, говорит высоким штилем |
| 🐈 | `!котик [текст]` | нейросеть с лапками (и завышенным ЧСВ) |
| 🏴‍☠️ | `!пират [текст]` | морской волк, ром и пиастры |
| 🚨 | `!паникер [текст]` | во всём видит конец света |
| ⛪️ | `!проповедник [текст]` | фанатичный гуру странного культа |
| 👩‍👧 | `!мамуля [текст]` | гиперопекающая виртуальная мать |
| 👽 | `!пришелец [текст]` | изучает жалких землян |
| 📎 | `!скрепка [текст]` | глючный ассистент из 90-х |
| 🕵️‍♂️ | `!детектив [текст]` | нуарный сыщик с депрессией |
| 🍳 | `!шеф [текст]` | орёт и критикует как Гордон Рамзи |
| 💪 | `!качок [текст]` | тупой качок, думает только о массе и протеине |
| 🎢 | `!биполяр [текст]` | эмоциональные качели от эйфории до глубокой депрессии |
| 👤 | `!я [текст]` | цифровой двойник Lonewolf239 |
| 💬 | `!ии_чат` | интерактивный диалог с персонами |

### 🎬 Media & Downloads
| | Command | Description |
|---|---|---|
| 🌐 | `!перевести` | перевод и озвучка |
| 👾 | `!шакал -начало` | склеивает 2 видео (ответь на 1-е видео командой со 2-м) |
| 🎧 | `!звук` | заменяет звук в видео (ответь на видео аудио-файлом) |
| 🎙️ | `!расшифровка` | текст из аудио/видео |
| 🔊 | `!озвучка` | перевод текста в голос |
| 🔊 | `!инстант [запрос]` | поиск и скачивание мемных звуков |
| 🎬 | `!скачать [ссылка]` | загрузка с YouTube, TikTok и т.п. |
| 📝 | `!ютуб_текст [ссылка]` | скачать видео и перевести в текст |
| 🎵 | `!трек [название]` | поиск и скачивание музыки |
| 🎤 | `!по_тексту [слова из песни]` | найти песню по отрывку текста |
| 🎬 | `!кино [название]` | карточка фильма из Кинопоиска |
| 🔍 | `!картинка [запрос]` | поиск картинок в сети |
| 🖼 | `!обои` | сочные картинки 4k |

### 🎭 Fun & Games
| | Command | Description |
|---|---|---|
| 🖼️ | `!мем [избранное]` | случайный мем или из избранного |
| 🐱 | `!кот` | случайный котик |
| 📖 | `!факт` | случайный факт из Википедии |
| 🔮 | `!прогноз` | случайный прогноз на день |
| 💭 | `!цитата` | мудрая мысль |
| 🎰 | `!рулетка [ставка]` | азартные игры на токены |
| ⚔️ | `!дуэль [ставка]` | вызвать на дуэль за токены |
| 🎭 | `!рп` | список RP-команд |

### 🛠 Utilities
| | Command | Description |
|---|---|---|
| 💻 | `!анализ [команда]` | ревью исходного кода команды |
| 📚 | `!вики [запрос]` | поиск по Википедии |
| 🪙 | `!курс_крипты` | курсы топ монет в $ |
| 🌤️ | `!погода [город]` | текущая погода |
| 🔎 | `!поиск [запрос]` | поиск инфы в интернете (6 результатов) |
| 📱 | `!qr [текст]` | быстро сгенерировать QR-код |
| 💱 | `!курс [сумма] [валюты]` | конвертер валют |
| 🔀 | `!алиасы` | список всех синонимов команд |
| 💳 | `!баланс` | кошелёк и покупка токенов |
| 💰 | `!прайс` | стоимость команд |
| ⚙️ | `!настройки` | настройки бота (NSFW и др.) |
| 🤖 | `!о_боте` | техническая информация |
| 🍩 | `!donut` | поддержать автора |
| ℹ️ | `!помощь` | это меню |
| 🚀 | `!старт` | приветственное сообщение |
| 📰 | `!новости` | главные новости |
| 🎟 | `!афиша` | куда сходить сегодня |
| 🚫 | `!отключенные` | список неработающих команд и причины |

### 👑 Owner Commands (`!ownerhelp`)
| | Command | Description |
|---|---|---|
| 🚶‍♂️ | `!отошёл` | Включить режим автоответа |
| 🏠 | `!вернулся` | Выключить режим автоответа |
| 📊 | `!статус` | Текущий статус работы бота |
| 📈 | `!статистика` | Полная статистика бота |
| ⏱ | `!сброс_таймеров` | Сбросить текущую сессию |
| 🧹 | `!очистить_статус [id]` | Очистить статус пользователя |
| 🔗 | `!ссылки` | Управление ссылками бота |
| 📊 | `!линкстат` | Статистика переходов по ссылкам |
| ⏳ | `!ждущие` | Список ожидающих ответа |
| 🔞 | `!nsfw` | Статистика NSFW настроек |
| ⚙️ | `!система` | Системные настройки |
| 🧬 | `!двойник_стиль (реплай на владельца)` | разобрать СТИЛЬ/МЫШЛЕНИЕ/ТЕМЫ-профиль из сообщения владельца и обновить личность двойника |
| 📚 | `!двойник_факты (реплай на владельца)` | извлечь факты о владельце из его сообщения в базу знаний двойника |
| 🧩 | `!двойник_блок identity_core|negative_rules (реплай)` | вручную задать неизменяемый блок личности двойника |
| 🔒 | `!двойник_видимость ключ public|friends|private` | задать уровень приватности факта в базе знаний двойника |
| 🕰 | `!двойник_версии identity_core|negative_rules|speech_style` | показать историю версий блока личности двойника |
| ⏪ | `!двойник_откат блок id` | откатить блок личности двойника к прошлой версии |
| 👥 | `!двойник_контакт (реплай) [близкий|приятель|знакомый|чужой]` | посмотреть или задать тип отношений с собеседником |
| 🧪 | `!двойник_тест` | прогнать контрольные сценарии и проверить, не деградировал ли двойник |
| ❓ | `!двойник_вопросы [кол-во]` | получить пачку вопросов для интервью двойника |
| ✍️ | `!двойник_ответы 1. ... 2. ...` | отправить ответы на вопросы интервью двойника пачкой |
| 🚫 | `!двойник_отмена` | отменить активную сессию вопросов двойника |
| 🗣 | `!двойник_подряд [кол-во]` | начать интервью двойника в последовательном режиме, по одному вопросу |
| ⏭ | `!двойник_пропустить` | пропустить текущий вопрос последовательного интервью |
| 📥 | `!двойник_импорт (файл result.json)` | импортировать историю переписки из экспорта Telegram |
| 🧬 | `!двойник_меню` | меню отслеживания и настройки цифрового двойника |

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
- `owner_settings.db` – owner-configurable toggles (payments, auto-reply, twin feedback, etc.)
- `twin.db` – digital twin data (knowledge base, dialogue examples, contacts, prompt history)

---

## Notes

- Daily token limit is replenished every midnight (`DEFAULT_DAILY_TOKENS = 50`).
- Commands cost tokens (see `!прайс`). VIP users (including owner) pay nothing.
- Payments via YooKassa are optional and toggled at runtime via owner settings (`!настройки` menu), not a config.py flag.
- The bot can run with long polling (default) or webhooks (set `USE_WEBHOOKS = True` for YooKassa callbacks).
- For business accounts, the bot handles `business_message` and `business_connection` events.

import os
import re
import sys
import json
import time
import argparse
import requests
import threading
import shutil
from deep_translator import GoogleTranslator
from dotenv import load_dotenv

# Настройка путей
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(SCRIPT_DIR)

env_path = os.path.join(ROOT_DIR, ".env")
if os.path.exists(env_path):
    load_dotenv(env_path)

sys.path.insert(0, ROOT_DIR)

CACHE_FILE = os.path.join(SCRIPT_DIR, "ai_descriptions_cache.json")
TRANSLATION_CACHE_FILE = os.path.join(SCRIPT_DIR, "translation_cache.json")
README_RU = os.path.join(ROOT_DIR, "docs", "README-RU.md")
README_EN = os.path.join(ROOT_DIR, "docs", "README.md")

# Фейковые переменные окружения для успешного импорта config, если они не заданы
os.environ.setdefault("OWNER_ID", "1")
os.environ.setdefault("BOT_TOKEN", "dummy")

try:
    import config
except Exception as e:
    print(f"\033[91m[ERROR] Ошибка импорта config.py: {e}\033[0m")
    exit(1)


class C:
    CYAN, GREEN, YELLOW, RED, MAGENTA, RESET, BOLD = (
        "\033[96m",
        "\033[92m",
        "\033[93m",
        "\033[91m",
        "\033[95m",
        "\033[0m",
        "\033[1m",
    )


class UILoggerProgressBar:
    def __init__(self, total_overall, max_log_lines=12):
        self.total_overall = total_overall
        self.current_overall = 0
        self.total_op = 1
        self.current_op = 0
        self.op_name = ""
        self.active = False
        self.lock = threading.Lock()

        self.logs = []
        self.max_log_lines = max_log_lines
        self.ui_height = self.max_log_lines + 2 + 4

        self.scroll_offset = 0
        self.last_text = ""
        self.listener_thread = None

    def _input_listener(self):
        try:
            import msvcrt

            while self.active:
                if msvcrt.kbhit():
                    key = msvcrt.getch()
                    if key in (b"\xe0", b"\x00"):
                        key = msvcrt.getch()
                        if key == b"H":
                            self._scroll(1)
                        elif key == b"P":
                            self._scroll(-1)
                time.sleep(0.05)
        except ImportError:
            import sys

            try:
                import tty, termios, select

                fd = sys.stdin.fileno()
                old_settings = termios.tcgetattr(fd)
                try:
                    tty.setcbreak(fd)
                    while self.active:
                        if select.select([sys.stdin], [], [], 0.05)[0]:
                            key = sys.stdin.read(1)
                            if key == "\x1b":
                                if sys.stdin.read(1) == "[":
                                    direction = sys.stdin.read(1)
                                    if direction == "A":
                                        self._scroll(1)
                                    elif direction == "B":
                                        self._scroll(-1)
                finally:
                    termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
            except Exception:
                pass

    def _scroll(self, direction):
        with self.lock:
            max_offset = max(0, len(self.logs) - self.max_log_lines)
            self.scroll_offset += direction
            if self.scroll_offset < 0:
                self.scroll_offset = 0
            elif self.scroll_offset > max_offset:
                self.scroll_offset = max_offset
            self._draw_no_lock()

    def add_log(self, message, level="INFO"):
        with self.lock:
            timestamp = time.strftime("%H:%M:%S")
            clean_msg = message.replace("\n", " ").strip()
            self.logs.append((timestamp, clean_msg, level))
            if self.active:
                self._draw_no_lock()

    def start(self, op_name, total_op):
        with self.lock:
            self.op_name = op_name
            self.total_op = max(1, total_op)
            self.current_op = 0
            self.scroll_offset = 0
            if not self.active:
                sys.stdout.write("\n" * self.ui_height)
                self.active = True
                self.listener_thread = threading.Thread(
                    target=self._input_listener, daemon=True
                )
                self.listener_thread.start()
            self._draw_no_lock()

    def update_op(self, step=1, text=""):
        with self.lock:
            self.current_op += step
            self.last_text = text if text else self.last_text
            self._draw_no_lock()

    def update_overall(self, step=1):
        with self.lock:
            self.current_overall += step
            self._draw_no_lock()

    def _draw_no_lock(self, text=None):
        if text is not None:
            self.last_text = text

        sys.stdout.write(f"\033[{self.ui_height}F")
        columns, _ = shutil.get_terminal_size()
        box_width = min(110, max(60, columns - 2))
        inner_width = box_width - 2

        total_logs = len(self.logs)
        max_offset = max(0, total_logs - self.max_log_lines)

        scroll_ind = (
            f" ▲▼ {int(((max_offset - self.scroll_offset) / max_offset) * 100) if max_offset > 0 else 100}% "
            if total_logs > self.max_log_lines
            else " "
        )
        header = f" ЛОГИ И СОСТОЯНИЕ{scroll_ind}"
        sys.stdout.write(
            f"\033[K{C.CYAN}┌{header.center(inner_width, '─')}┐{C.RESET}\n"
        )

        start_idx = max(0, total_logs - self.max_log_lines - self.scroll_offset)
        display_logs = self.logs[start_idx : start_idx + self.max_log_lines]
        LEVEL_COLORS = {"INFO": C.GREEN, "WARN": C.YELLOW, "ERROR": C.RED}

        for i in range(self.max_log_lines):
            if i < len(display_logs):
                timestamp, msg_text, level = display_logs[i]
                col = LEVEL_COLORS.get(level, C.RESET)
                log_line = f"[{timestamp}] [{level}] {msg_text}"
                max_log_len = inner_width - 2
                if len(log_line) > max_log_len:
                    log_line = log_line[: max_log_len - 3] + "..."
                sys.stdout.write(
                    f"\033[K{C.CYAN}│{C.RESET} {col}{log_line:<{inner_width - 2}}{C.RESET} {C.CYAN}│{C.RESET}\n"
                )
            else:
                sys.stdout.write(
                    f"\033[K{C.CYAN}│ {' ' * (inner_width - 2)} │{C.RESET}\n"
                )

        sys.stdout.write(f"\033[K{C.CYAN}└{'─' * inner_width}┘{C.RESET}\n")

        bar_len = min(40, max(20, int(inner_width * 0.5)))
        pct_ov = min(100, int(100 * self.current_overall / max(1, self.total_overall)))
        filled_ov = min(
            bar_len, int(bar_len * self.current_overall / max(1, self.total_overall))
        )
        pct_op = min(100, int(100 * self.current_op / max(1, self.total_op)))
        filled_op = min(bar_len, int(bar_len * self.current_op / max(1, self.total_op)))

        max_text_len = inner_width - bar_len - 25
        safe_text = (
            (self.last_text[: max_text_len - 2] + "..")
            if len(self.last_text) > max_text_len
            else self.last_text
        )

        sys.stdout.write(f"\033[K{'-' * box_width}\n")
        sys.stdout.write(
            f"\033[K {C.MAGENTA}Общий прогресс : [{'█' * filled_ov + '░' * (bar_len - filled_ov)}] {pct_ov:>3}%{C.RESET}\n"
        )
        sys.stdout.write(
            f"\033[K {C.CYAN}{self.op_name[:14]:<14} : [{'█' * filled_op + '░' * (bar_len - filled_op)}] {pct_op:>3}%  {safe_text}{C.RESET}\n"
        )
        sys.stdout.write(f"\033[K{'-' * box_width}\n")
        sys.stdout.flush()

    def finish(self):
        with self.lock:
            self.active = False
            self.current_overall = self.total_overall
            self.current_op = self.total_op
            self._draw_no_lock("Готово")
            print("\n")


def load_cache(filepath):
    if os.path.exists(filepath):
        with open(filepath, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_cache(cache, filepath):
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, indent=4)


translator = GoogleTranslator(source="ru", target="en")
translation_cache = load_cache(TRANSLATION_CACHE_FILE)


def t_en(text):
    if not text:
        return ""
    return translation_cache.get(text, text)


def clean_and_validate_desc(text):
    if not text:
        return None
    text = text.strip()
    text = re.sub(r'^["\'`*\-\s]+|["\'`*\-\s\.]+$', "", text)
    text = text.replace("\n", " ").strip()

    sentences = re.split(r"(?<=[.!?])\s+", text)
    if sentences:
        text = sentences[0].strip()
        text = re.sub(r"[.!?]+$", "", text)

    prefixes = [
        r"^вот описание команды[:\s]*",
        r"^описание команды[:\s]*",
        r"^команда делает[:\s]*",
        r"^команда[:\s]*",
        r"^функция[:\s]*",
        r"^это команда, которая[:\s]*",
        r"^эта команда[:\s]*",
        r"^данная команда[:\s]*",
        r"^бот[:\s]*",
        r"^смысл команды[:\s]*",
        r"^предназначена для того, чтобы[:\s]*",
    ]
    for pattern in prefixes:
        text = re.sub(pattern, "", text, flags=re.IGNORECASE).strip()

    if not text:
        return None
    words = text.split()
    if len(words) > 12 or len(words) < 2:
        return None
    if any("\u4e00" <= char <= "\u9fff" for char in text):
        return None

    mixed_word_pattern = re.compile(
        r"\b(?=[а-яА-ЯёЁ]*[a-zA-Z])(?=[a-zA-Z]*[а-яА-ЯёЁ])[а-яА-ЯёЁa-zA-Z]+\b"
    )
    if mixed_word_pattern.search(text):
        return None

    letters = [c for c in text if c.isalpha()]
    if letters:
        cyrillic_letters = sum(
            1 for c in letters if "а" <= c.lower() <= "я" or c.lower() == "ё"
        )
        if (cyrillic_letters / len(letters)) < 0.80 and re.search(r"\b[a-z]+\b", text):
            return None

    if len(text) > 0:
        text = text[0].upper() + text[1:]
    return text


def get_ai_description(
    cmd, name, short_desc, cache, pb, force=False, custom_model=None
):
    if not force and cmd in cache and cache[cmd].get("short_desc") == short_desc:
        ai_desc = cache[cmd]["ai_desc"]
        pb.add_log(f"Кэш: {cmd} -> '{ai_desc}'", "INFO")
        return ai_desc

    model = custom_model or config.GROQ_MODEL or "llama-3.3-70b-versatile"
    api_key = config.GROQ_API_KEY

    if not api_key:
        pb.add_log("GROQ_API_KEY не задан! Применяем базовое описание.", "WARN")
        return short_desc

    aliases = config.COMMAND_ALIASES.get(cmd, [])
    aliases_str = ", ".join(aliases) if aliases else "нет дополнительных синонимов"

    system = (
        "Ты — профессиональный технический писатель.\n"
        "Твоя задача: перевести суть команды Telegram-бота в одно лаконичное описание на русском языке.\n\n"
        "ПРАВИЛА:\n"
        "1. Пиши СТРОГО на русском языке.\n"
        "2. Напиши ровно ОДНО короткое предложение (не более 8-10 слов).\n"
        "3. Начинай описание строго с глагола действия в 3-м лице единственного числа (Находит, Скачивает, Показывает и т.д.).\n"
        "4. БЕЗ точки на конце, БЕЗ кавычек, БЕЗ вводных фраз."
    )

    prompt = (
        f"Контекст: Это команда Telegram-бота.\n"
        f"Команда: {cmd}\nНазвание: {name}\n"
        f"Суть от разработчика: {short_desc}\nСинонимы: {aliases_str}\n\n"
        f"Напиши 1 короткое описание:"
    )

    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.0,
        "top_p": 0.1,
        "max_tokens": 50,
    }

    for attempt in range(1, 4):
        try:
            response = requests.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers=headers,
                json=payload,
                timeout=30,
            )

            # Обработка Rate Limit
            if response.status_code == 429:
                sleep_time = attempt * 3
                pb.add_log(
                    f"Rate Limit (429) от Groq. Ждем {sleep_time} сек...", "WARN"
                )
                time.sleep(sleep_time)
                continue

            response.raise_for_status()

            raw_text = (
                response.json()
                .get("choices", [{}])[0]
                .get("message", {})
                .get("content", "")
                .strip()
            )
            cleaned_text = clean_and_validate_desc(raw_text)

            if cleaned_text:
                cache[cmd] = {"short_desc": short_desc, "ai_desc": cleaned_text}
                save_cache(cache, CACHE_FILE)
                pb.add_log(f"Groq: {cmd} -> '{cleaned_text}'", "INFO")
                return cleaned_text
            else:
                pb.add_log(
                    f"Попытка {attempt} для {cmd} отсеяна как галлюцинация: '{raw_text}'",
                    "WARN",
                )

        except Exception as e:
            pb.add_log(f"Сбой Groq API (Попытка {attempt}): {str(e)}", "ERROR")
            time.sleep(2)

    pb.add_log(f"Для {cmd} применено базовое описание разработчика.", "WARN")
    return short_desc


def generate_features_table(
    active_cmds, owner_cmds, cache, pb, lang="ru", force=False, custom_model=None
):
    lines = []
    if lang == "ru":
        lines.append("| | Функция | Описание |")
        lines.append("|---|---------|----------|")
        for cmd, data in active_cmds.items():
            ai_desc = get_ai_description(
                cmd, data["name"], data["desc"], cache, pb, force, custom_model
            )
            args = f" {data['args']}" if "args" in data else ""
            lines.append(
                f"| {data['icon']} | **{data['name']}** | `{cmd}{args}` — {ai_desc} |"
            )

        if owner_cmds:
            lines.append("| 👑 | **Команды владельца** | `---` |")
            for cmd, data in owner_cmds.items():
                ai_desc = get_ai_description(
                    cmd, data["name"], data["desc"], cache, pb, force, custom_model
                )
                args = f" {data['args']}" if "args" in data else ""
                lines.append(
                    f"| {data['icon']} | **{data['name']}** | `{cmd}{args}` — {ai_desc} |"
                )
    else:
        lines.append("| | Feature | Description |")
        lines.append("|---|---------|-------------|")
        for cmd, data in active_cmds.items():
            ai_desc = get_ai_description(
                cmd, data["name"], data["desc"], cache, pb, force, custom_model
            )
            ai_desc_en = t_en(ai_desc)
            args = f" {data['args']}" if "args" in data else ""
            lines.append(
                f"| {data['icon']} | **{data['name']}** | `{cmd}{args}` — {ai_desc_en} |"
            )

        if owner_cmds:
            lines.append("| 👑 | **Owner Commands** | `---` |")
            for cmd, data in owner_cmds.items():
                ai_desc = get_ai_description(
                    cmd, data["name"], data["desc"], cache, pb, force, custom_model
                )
                ai_desc_en = t_en(ai_desc)
                args = f" {data['args']}" if "args" in data else ""
                lines.append(
                    f"| {data['icon']} | **{data['name']}** | `{cmd}{args}` — {ai_desc_en} |"
                )

    return "\n".join(lines)


def generate_commands_section(active_cmds, owner_cmds, lang="ru"):
    if lang == "ru":
        content = "### Владельца (`!ownerhelp`)\n"
        for cmd, data in owner_cmds.items():
            args = f" {data['args']}" if "args" in data else ""
            content += f"- `{cmd}{args}` – {data['desc']}\n"
        content += "\n### Публичные (`!помощь`)\n"
        for cmd, data in active_cmds.items():
            args = f" {data['args']}" if "args" in data else ""
            content += f"- `{cmd}{args}` – {data['desc']}\n"
    else:
        content = "### Owner (`!ownerhelp`)\n"
        for cmd, data in owner_cmds.items():
            args = f" {data['args']}" if "args" in data else ""
            content += f"- `{cmd}{args}` – {t_en(data['desc'])}\n"
        content += "\n### Public (`!помощь`)\n"
        for cmd, data in active_cmds.items():
            args = f" {data['args']}" if "args" in data else ""
            content += f"- `{cmd}{args}` – {t_en(data['desc'])}\n"

    sfw_rp = "`!обнять`, `!поцеловать`, `!ударить`, `!шлепнуть`, `!укусить`, `!погладить`, `!пнуть`, `!толкнуть`, `!ущипнуть`, `!прижать_к_стене`, `!ткнуть_по_носику`, `!лизнуть`, `!задушить`"
    nsfw_rp = "`!отсосать`, `!выебать`, `!трахнуть`, `!кончить`, `!раздеть`, `!оттрахать`, `!поставить_на_колени`, `!схватить_за_член`, `!схватить_за_жопу`, `!отлизать`"

    if lang == "ru":
        content += f"\n**RP‑команды** (ответ на сообщение):\nSFW: {sfw_rp}.\nПри включённом NSFW добавляются: {nsfw_rp}."
    else:
        content += f"\n**RP commands** (reply to a message):\nSFW: {sfw_rp}.\nWhen NSFW enabled: {nsfw_rp}."

    return content


def update_readme(file_path, marker_name, new_content):
    if not os.path.exists(file_path):
        return (
            False,
            f"Файл {os.path.basename(file_path)} не найден (Ожидался путь: {file_path})",
        )

    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()

    pattern = rf"(<!--\s*{marker_name}_START\s*-->).*?(<!--\s*{marker_name}_END\s*-->)"

    if re.search(pattern, content, flags=re.DOTALL):
        updated = re.sub(pattern, rf"\1\n{new_content}\n\2", content, flags=re.DOTALL)
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(updated)
        return True, f"Обновлен блок {marker_name} в {os.path.basename(file_path)}"
    else:
        return (
            False,
            f"Маркеры {marker_name} не найдены в {os.path.basename(file_path)}",
        )


def main():
    parser = argparse.ArgumentParser(
        description="Утилита генерации README с использованием Groq ИИ"
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Игнорировать кэш и перегенерировать описания",
    )
    parser.add_argument(
        "--clear-cache", action="store_true", help="Очистить файлы кэша перед запуском"
    )
    parser.add_argument(
        "--model", type=str, help="Переопределить модель (напр. llama-3.1-8b-instant)"
    )
    args = parser.parse_args()

    if args.clear_cache:
        for f_path in [CACHE_FILE, TRANSLATION_CACHE_FILE]:
            if os.path.exists(f_path):
                os.remove(f_path)
        print(f"{C.YELLOW}[INFO] Кэш успешно очищен.{C.RESET}")

    print(f"{C.MAGENTA}{C.BOLD}[INFO] Запуск сборки README (Движок: Groq)...{C.RESET}")

    active_cmds = {
        k: v for k, v in config.COMMAND_METADATA.items() if not v.get("disabled", False)
    }
    owner_cmds = getattr(config, "OWNER_COMMAND_METADATA", {})
    active_owner_cmds = {
        k: v for k, v in owner_cmds.items() if not v.get("disabled", False)
    }
    all_cmds = {**active_cmds, **active_owner_cmds}

    cache = load_cache(CACHE_FILE)

    total_ai_steps = len(all_cmds)
    total_translate_steps = len(all_cmds)
    total_files_steps = 4
    total_overall = total_ai_steps + total_translate_steps + total_files_steps + 1

    pb = UILoggerProgressBar(total_overall, max_log_lines=6)

    # ЭТАП 1: ГЕНЕРАЦИЯ ИИ
    pb.start("Анализ ИИ (Groq)", total_ai_steps)
    for cmd, data in all_cmds.items():
        pb.update_op(1, f"Команда {cmd}")
        get_ai_description(
            cmd,
            data["name"],
            data["desc"],
            cache,
            pb,
            force=args.force,
            custom_model=args.model,
        )
        pb.update_overall(1)

    pb.start("Сборка (RU)", 1)
    cmds_ru = generate_commands_section(active_cmds, active_owner_cmds, "ru")
    features_ru = generate_features_table(
        active_cmds,
        active_owner_cmds,
        cache,
        pb,
        "ru",
        force=args.force,
        custom_model=args.model,
    )
    pb.update_op(1, "Таблицы сформированы")
    pb.update_overall(1)

    # ЭТАП 2: ПЕРЕВОД
    pb.start("Сбор строк", 1)
    texts_to_translate = []
    for cmd, data in all_cmds.items():
        ai_desc = get_ai_description(
            cmd,
            data["name"],
            data["desc"],
            cache,
            pb,
            force=args.force,
            custom_model=args.model,
        )
        for t in (data["desc"], ai_desc):
            if t and t not in translation_cache and t not in texts_to_translate:
                texts_to_translate.append(t)

    if texts_to_translate:
        chunk_size = 15
        chunks = [
            texts_to_translate[i : i + chunk_size]
            for i in range(0, len(texts_to_translate), chunk_size)
        ]

        pb.start("Перевод (EN)", len(chunks))
        for i, chunk in enumerate(chunks):
            pb.update_op(1, f"Пакет {i + 1}/{len(chunks)}")
            try:
                translated = translator.translate_batch(chunk)
                for orig, trans in zip(chunk, translated):
                    translation_cache[orig] = trans if trans else orig
                    pb.add_log(
                        f"Переведено: '{orig[:15]}...' -> '{trans[:15]}...'", "INFO"
                    )
            except Exception as e:
                pb.add_log(f"Ошибка перевода (пакет {i + 1}): {str(e)}", "ERROR")
                for orig in chunk:
                    translation_cache[orig] = orig

        save_cache(translation_cache, TRANSLATION_CACHE_FILE)
    else:
        pb.start("Перевод (EN)", 1)
        pb.update_op(1, "Всё взято из кэша")

    pb.update_overall(total_translate_steps)

    cmds_en = generate_commands_section(active_cmds, active_owner_cmds, "en")
    features_en = generate_features_table(
        active_cmds,
        active_owner_cmds,
        cache,
        pb,
        "en",
        force=args.force,
        custom_model=args.model,
    )

    # ЭТАП 3: СОХРАНЕНИЕ
    pb.start("Сохранение", total_files_steps)
    files_to_update = [
        (README_RU, "COMMANDS_SECTION", cmds_ru),
        (README_RU, "FEATURES_TABLE", features_ru),
        (README_EN, "COMMANDS_SECTION", cmds_en),
        (README_EN, "FEATURES_TABLE", features_en),
    ]

    results = []
    for file_path, marker, content in files_to_update:
        pb.update_op(1, f"Запись {marker}")
        success, msg = update_readme(file_path, marker, content)
        results.append((success, msg))
        pb.update_overall(1)

    pb.finish()

    warnings_list = [log for log in pb.logs if log[2] == "WARN"]
    errors_list = [log for log in pb.logs if log[2] == "ERROR"]

    if errors_list or warnings_list:
        print(
            f"{C.YELLOW}{C.BOLD}[INFO] Сводка предупреждений и ошибок генерации:{C.RESET}"
        )
        for timestamp, msg, lvl in pb.logs:
            if lvl == "ERROR":
                print(f"  {C.RED}• [{timestamp}] [ERROR] {msg}{C.RESET}")
            elif lvl == "WARN":
                print(f"  {C.YELLOW}• [{timestamp}] [WARN] {msg}{C.RESET}")
        print()
    else:
        print(f"{C.GREEN}{C.BOLD}✓ Все операции выполнены без ошибок.{C.RESET}\n")

    for success, msg in results:
        print(f"  [{'SUCCESS' if success else 'ERROR'}] {msg}")

    print(f"\n{C.GREEN}{C.BOLD}[INFO] Все README файлы успешно обновлены!{C.RESET}")


if __name__ == "__main__":
    main()

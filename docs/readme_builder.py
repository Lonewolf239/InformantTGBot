import os
import sys
import json
import time
import argparse
import asyncio
import threading
import shutil
import re
import logging
from dotenv import load_dotenv

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(SCRIPT_DIR)

env_path = os.path.join(ROOT_DIR, ".env")
if os.path.exists(env_path):
    load_dotenv(env_path)

sys.path.insert(0, ROOT_DIR)

logging.getLogger("bot.utils.ai_api").setLevel(logging.CRITICAL)

try:
    import config
    from bot.utils.ai_api import ask_groq_ai
except Exception as e:
    print(f"\033[91m[ERROR] Ошибка импорта базовых модулей: {e}\033[0m")
    exit(1)

CACHE_FILE = os.path.join(SCRIPT_DIR, "ai_descriptions_cache.json")
TRANSLATION_CACHE_FILE = os.path.join(SCRIPT_DIR, "translation_cache.json")
README_RU = os.path.join(ROOT_DIR, "docs", "README-RU.md")
README_EN = os.path.join(ROOT_DIR, "docs", "README.md")

os.environ.setdefault("OWNER_ID", "1")
os.environ.setdefault("BOT_TOKEN", "dummy")


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
                import tty
                import termios
                import select

                fd = sys.stdin.fileno()
                old_settings = termios.tcgetattr(fd)
                try:
                    tty.setcbreak(fd)
                    while self.active:
                        if select.select([sys.stdin], [], [], 0.05)[0]:
                            key = sys.stdin.read(1)
                            if key == "\x1b" and sys.stdin.read(1) == "[":
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
            self.scroll_offset = max(0, min(self.scroll_offset, max_offset))
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
            if text:
                self.last_text = text
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


class GUIHandler(logging.Handler):
    def __init__(self, pb):
        super().__init__()
        self.pb = pb

    def emit(self, record):
        try:
            msg = self.format(record)

            if (
                "Event loop is closed" in msg
                or "Task exception was never retrieved" in msg
            ):
                return

            level = "INFO"
            if record.levelno >= logging.ERROR:
                level = "ERROR"
            elif record.levelno >= logging.WARNING:
                level = "WARN"

            for line in msg.splitlines():
                if line.strip():
                    self.pb.add_log(line.strip(), level)
        except Exception:
            self.handleError(record)


class StderrRedirector:
    def __init__(self, pb):
        self.pb = pb

    def write(self, text):
        for line in text.splitlines():
            if line.strip():
                self.pb.add_log(line.strip(), "ERROR")

    def flush(self):
        pass


def load_cache(filepath):
    if os.path.exists(filepath):
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, ValueError):
            return {}
    return {}


def save_cache(cache, filepath):
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, indent=4)


translation_cache = load_cache(TRANSLATION_CACHE_FILE)


def t_en(text):
    if not text:
        return ""
    return translation_cache.get(text, text)


def generate_ai_descriptions_batch(commands_dict, pb):
    system = (
        "Ты — строгий технический писатель. Твоя задача: написать лаконичные описания для списка команд Telegram-бота.\n"
        "КРИТИЧЕСКИЕ ПРАВИЛА:\n"
        "1. Максимум 5-8 слов на команду.\n"
        "2. Начинай СТРОГО с глагола в 3-м лице единственного числа (например: Ищет, Скачивает, Генерирует).\n"
        "3. Никаких точек в конце и кавычек.\n"
        '4. Верни ответ СТРОГО в формате JSON: {"command_name": "описание"}.\n'
        "Не используй markdown-блоки, верни только сырой JSON!"
    )

    prompt_data = {}
    for cmd, data in commands_dict.items():
        aliases = config.COMMAND_ALIASES.get(cmd, [])
        prompt_data[cmd] = {
            "name": data["name"],
            "dev_description": data["desc"],
            "aliases": aliases,
        }

    prompt = f"Сгенерируй короткие описания для этих команд в JSON.\nВходные данные:\n{json.dumps(prompt_data, ensure_ascii=False)}"

    try:
        answer = asyncio.run(
            ask_groq_ai(user_prompt=prompt, system_prompt=system, temperature=0.1)
        )

        if answer:
            clean_ans = answer.strip()
            if clean_ans.startswith("```json"):
                clean_ans = clean_ans[7:]
            elif clean_ans.startswith("```"):
                clean_ans = clean_ans[3:]
            if clean_ans.endswith("```"):
                clean_ans = clean_ans[:-3]

            result = json.loads(clean_ans.strip())
            pb.add_log(f"Успешно сгенерировано {len(result)} описаний батчем.", "INFO")

            for k, v in result.items():
                result[k] = v.strip().strip(".").capitalize()

            return result
        else:
            pb.add_log(
                "Groq API не вернул ответ (все ключи забанены или лимит).", "ERROR"
            )
            return {}

    except json.JSONDecodeError as e:
        pb.add_log(f"Ошибка парсинга JSON от ИИ: {str(e)}", "ERROR")
        return {}
    except Exception as e:
        pb.add_log(f"Сбой Groq API при батч-запросе: {str(e)}", "ERROR")
        return {}


def translate_batch_groq(chunk, pb):
    system = (
        "Ты — профессиональный ИИ-переводчик. Твоя задача: перевести массив строк с русского на английский язык.\n"
        "КРИТИЧЕСКИЕ ПРАВИЛА:\n"
        "1. Сохраняй исходный порядок элементов.\n"
        "2. Переводи точно и технически грамотно.\n"
        '3. Верни ответ СТРОГО в формате JSON-массива строк: ["translation1", "translation2"].\n'
        "Не используй markdown-блоки, верни только сырой JSON!"
    )

    prompt = f"Переведи этот массив JSON: {json.dumps(chunk, ensure_ascii=False)}"

    try:
        answer = asyncio.run(
            ask_groq_ai(user_prompt=prompt, system_prompt=system, temperature=0.1)
        )

        if answer:
            clean_ans = answer.strip()
            if clean_ans.startswith("```json"):
                clean_ans = clean_ans[7:]
            elif clean_ans.startswith("```"):
                clean_ans = clean_ans[3:]
            if clean_ans.endswith("```"):
                clean_ans = clean_ans[:-3]

            result = json.loads(clean_ans.strip())
            return result
        else:
            pb.add_log("Groq API не вернул ответ при переводе.", "ERROR")
            return []

    except json.JSONDecodeError as e:
        pb.add_log(f"Ошибка парсинга JSON перевода от ИИ: {str(e)}", "ERROR")
        return []
    except Exception as e:
        pb.add_log(f"Сбой Groq API при переводе батча: {str(e)}", "ERROR")
        return []


def generate_features_table(active_cmds, owner_cmds, cache, lang="ru"):
    lines = []

    def get_desc(cmd, data):
        return cache.get(cmd, {}).get("ai_desc", data["desc"])

    if lang == "ru":
        lines.append("| | Функция | Описание |")
        lines.append("|---|---------|----------|")
        for cmd, data in active_cmds.items():
            ai_desc = get_desc(cmd, data)
            args = f" {data['args']}" if "args" in data else ""
            lines.append(
                f"| {data['icon']} | **{data['name']}** | `{cmd}{args}` — {ai_desc} |"
            )

        if owner_cmds:
            lines.append("| 👑 | **Команды владельца** | `---` |")
            for cmd, data in owner_cmds.items():
                ai_desc = get_desc(cmd, data)
                args = f" {data['args']}" if "args" in data else ""
                lines.append(
                    f"| {data['icon']} | **{data['name']}** | `{cmd}{args}` — {ai_desc} |"
                )
    else:
        lines.append("| | Feature | Description |")
        lines.append("|---|---------|-------------|")
        for cmd, data in active_cmds.items():
            ai_desc_en = t_en(get_desc(cmd, data))
            args = f" {data['args']}" if "args" in data else ""
            lines.append(
                f"| {data['icon']} | **{data['name']}** | `{cmd}{args}` — {ai_desc_en} |"
            )

        if owner_cmds:
            lines.append("| 👑 | **Owner Commands** | `---` |")
            for cmd, data in owner_cmds.items():
                ai_desc_en = t_en(get_desc(cmd, data))
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
        return False, f"Файл {os.path.basename(file_path)} не найден"
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

    cmds_to_process = {}
    for cmd, data in all_cmds.items():
        if (
            args.force
            or cmd not in cache
            or cache[cmd].get("short_desc") != data["desc"]
        ):
            cmds_to_process[cmd] = data

    chunk_size = 20
    cmds_keys = list(cmds_to_process.keys())
    chunks = [
        {k: cmds_to_process[k] for k in cmds_keys[i : i + chunk_size]}
        for i in range(0, len(cmds_keys), chunk_size)
    ]

    total_overall = len(chunks) + 3
    pb = UILoggerProgressBar(total_overall, max_log_lines=6)

    gui_handler = GUIHandler(pb)
    gui_handler.setFormatter(logging.Formatter("%(name)s: %(message)s"))

    asyncio_logger = logging.getLogger("asyncio")
    asyncio_logger.setLevel(logging.WARNING)
    asyncio_logger.handlers.clear()
    asyncio_logger.addHandler(gui_handler)

    for logger_name in ("httpx", "httpcore"):
        l = logging.getLogger(logger_name)
        l.setLevel(logging.WARNING)
        l.handlers.clear()
        l.addHandler(gui_handler)

    sys.stderr = StderrRedirector(pb)

    if chunks:
        pb.start("Анализ ИИ (Groq)", len(chunks))
        for idx, chunk in enumerate(chunks):
            pb.update_op(1, f"Чанк {idx + 1}/{len(chunks)}")
            ai_results = generate_ai_descriptions_batch(chunk, pb)

            for cmd, ai_desc in ai_results.items():
                if cmd in chunk:
                    cache[cmd] = {"short_desc": chunk[cmd]["desc"], "ai_desc": ai_desc}

            save_cache(cache, CACHE_FILE)
            pb.update_overall(1)
            time.sleep(1)
    else:
        pb.start("Анализ ИИ (Groq)", 1)
        pb.add_log("Все команды актуальны в кэше. ИИ пропущен.", "INFO")
        pb.update_op(1, "ИИ не требуется")
        pb.update_overall(1)

    pb.start("Перевод (EN)", 1)
    texts_to_translate = []
    for cmd, data in all_cmds.items():
        ai_desc = cache.get(cmd, {}).get("ai_desc", data["desc"])
        for t in (data["desc"], ai_desc):
            if t and t not in translation_cache and t not in texts_to_translate:
                texts_to_translate.append(t)

    if texts_to_translate:
        t_chunk_size = 20
        t_chunks = [
            texts_to_translate[i : i + t_chunk_size]
            for i in range(0, len(texts_to_translate), t_chunk_size)
        ]

        pb.start("Перевод (EN)", len(t_chunks))
        for i, chunk in enumerate(t_chunks):
            pb.update_op(1, f"Пакет {i + 1}/{len(t_chunks)}")

            translated = translate_batch_groq(chunk, pb)

            if isinstance(translated, list) and len(translated) == len(chunk):
                for orig, trans in zip(chunk, translated):
                    translation_cache[orig] = trans if trans else orig
            else:
                pb.add_log(
                    "Ошибка перевода пакета: несовпадение длин или неверный формат",
                    "ERROR",
                )
                for orig in chunk:
                    translation_cache[orig] = orig
            time.sleep(0.5)

        save_cache(translation_cache, TRANSLATION_CACHE_FILE)
    else:
        pb.update_op(1, "Переводы в кэше")
    pb.update_overall(1)

    pb.start("Сборка Markdown", 2)
    cmds_ru = generate_commands_section(active_cmds, active_owner_cmds, "ru")
    features_ru = generate_features_table(active_cmds, active_owner_cmds, cache, "ru")
    pb.update_op(1, "RU собрано")

    cmds_en = generate_commands_section(active_cmds, active_owner_cmds, "en")
    features_en = generate_features_table(active_cmds, active_owner_cmds, cache, "en")
    pb.update_op(1, "EN собрано")
    pb.update_overall(1)

    pb.start("Запись в файлы", 4)
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
        print(f"{C.YELLOW}{C.BOLD}[INFO] Сводка предупреждений и ошибок:{C.RESET}")
        for timestamp, msg, lvl in pb.logs:
            if lvl == "ERROR":
                print(f"  {C.RED}• [{timestamp}] [ERROR] {msg}{C.RESET}")
            elif lvl == "WARN":
                print(f"  {C.YELLOW}• [{timestamp}] [WARN] {msg}{C.RESET}")

    print(f"\n{C.MAGENTA}{C.BOLD}[ИТОГИ] Обновление файлов README:{C.RESET}")
    for success, msg in results:
        if success:
            print(f"  {C.GREEN}• [УСПЕХ] {msg}{C.RESET}")
        else:
            print(f"  {C.RED}• [ОШИБКА] {msg}{C.RESET}")
    print("\n")


if __name__ == "__main__":
    main()

import os
import re
import sys
import json
import requests
import threading
from deep_translator import GoogleTranslator

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(SCRIPT_DIR)

sys.path.insert(0, ROOT_DIR)

CACHE_FILE = os.path.join(SCRIPT_DIR, "ai_descriptions_cache.json")
TRANSLATION_CACHE_FILE = os.path.join(SCRIPT_DIR, "translation_cache.json")
README_RU = os.path.join(SCRIPT_DIR, "README-RU.md")
README_EN = os.path.join(SCRIPT_DIR, "README.md")

OLLAMA_URL = "http://127.0.0.1:11434/api/generate"
OLLAMA_MODEL = "qwen2.5:3b"

os.environ["OWNER_ID"] = "1"
os.environ["BOT_TOKEN"] = "dummy"

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


class DualProgressBar:
    def __init__(self, total_overall):
        self.total_overall = total_overall
        self.current_overall = 0
        self.total_op = 1
        self.current_op = 0
        self.op_name = ""
        self.active = False
        self.lock = threading.Lock()

    def start(self, op_name, total_op):
        with self.lock:
            self.op_name = op_name
            self.total_op = max(1, total_op)
            self.current_op = 0
            if not self.active:
                sys.stdout.write("\n\n\n\n")
                self.active = True
            self._draw()

    def update_op(self, step=1, text=""):
        with self.lock:
            self.current_op += step
            self._draw(text)

    def update_overall(self, step=1):
        with self.lock:
            self.current_overall += step
            self._draw()

    def _draw(self, text=""):
        sys.stdout.write("\033[4F")

        pct_ov = min(100, int(100 * self.current_overall / max(1, self.total_overall)))
        filled_ov = min(40, int(40 * self.current_overall / max(1, self.total_overall)))
        bar_ov = "█" * filled_ov + "░" * (40 - filled_ov)

        pct_op = min(100, int(100 * self.current_op / max(1, self.total_op)))
        filled_op = min(40, int(40 * self.current_op / max(1, self.total_op)))
        bar_op = "█" * filled_op + "░" * (40 - filled_op)

        safe_text = (text[:25] + "..") if len(text) > 27 else text

        sys.stdout.write(
            "\033[K------------------------------------------------------------\n"
        )
        sys.stdout.write(
            f"\033[K {C.MAGENTA}Общий прогресс : [{bar_ov}] {pct_ov:>3}%{C.RESET}\n"
        )
        sys.stdout.write(
            f"\033[K {C.CYAN}{self.op_name[:14]:<14} : [{bar_op}] {pct_op:>3}%  {safe_text}{C.RESET}\n"
        )
        sys.stdout.write(
            "\033[K------------------------------------------------------------\n"
        )
        sys.stdout.flush()

    def finish(self):
        with self.lock:
            self.current_overall = self.total_overall
            self.current_op = self.total_op
            self._draw("Готово")
            print("\n")


def load_cache():
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_cache(cache):
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, indent=4)


def load_trans_cache():
    if os.path.exists(TRANSLATION_CACHE_FILE):
        with open(TRANSLATION_CACHE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_trans_cache(trans_cache):
    with open(TRANSLATION_CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(trans_cache, f, ensure_ascii=False, indent=4)


translator = GoogleTranslator(source="ru", target="en")
translation_cache = load_trans_cache()


def t_en(text):
    if not text:
        return ""
    return translation_cache.get(text, text)


def get_ai_description(cmd, name, short_desc, cache):
    if cmd in cache and cache[cmd].get("short_desc") == short_desc:
        return cache[cmd]["ai_desc"]

    aliases = config.COMMAND_ALIASES.get(cmd, [])
    aliases_str = ", ".join(aliases) if aliases else "нет дополнительных синонимов"

    system = (
        "Ты — строгий технический писатель. Твоя задача — описать функцию Telegram-бота.\n"
        "ПРАВИЛА:\n"
        "1. ПИШИ СТРОГО НА РУССКОМ ЯЗЫКЕ. ЗАПРЕЩЕНО использовать китайские иероглифы или английский текст!\n"
        "2. Напиши ровно 1 короткое предложение (не более 10 слов).\n"
        "3. Начинай с глагола действия (например: 'Генерирует', 'Преобразует', 'Отвечает', 'Выдает').\n"
        "4. БЕЗ КАВЫЧЕК. БЕЗ ТОЧКИ В КОНЦЕ. БЕЗ ПРИВЕТСТВИЙ."
    )

    prompt = (
        f"Контекст: Это команда Telegram-бота.\n"
        f"Команда: {cmd}\n"
        f"Название: {name}\n"
        f"Краткая суть от разработчика: {short_desc}\n"
        f"Синонимы команды (помогают понять ее реальный смысл): {aliases_str}\n\n"
        f"Опиши 1 коротким предложением, что конкретно делает эта команда. Только само описание на русском:"
    )

    try:
        response = requests.post(
            OLLAMA_URL,
            json={
                "model": OLLAMA_MODEL,
                "prompt": prompt,
                "system": system,
                "stream": False,
                "options": {
                    "temperature": 0.1,
                    "top_p": 0.5,
                    "repeat_penalty": 1.2,
                    "num_predict": 40,
                },
            },
            timeout=60,
        )
        response.raise_for_status()

        ai_text = (
            response.json()
            .get("response", "")
            .strip()
            .strip("\"'-.*")
            .replace("\n", " ")
        )

        if any("\u4e00" <= char <= "\u9fff" for char in ai_text):
            raise ValueError("Галлюцинация: иероглифы")

        latin_chars = sum(1 for c in ai_text if "a" <= c.lower() <= "z")
        if latin_chars > len(ai_text) / 3:
            raise ValueError("Галлюцинация: английский текст")

        if not ai_text:
            raise ValueError("Пустой ответ")

        cache[cmd] = {"short_desc": short_desc, "ai_desc": ai_text}
        save_cache(cache)
        return ai_text
    except Exception:
        return short_desc


def generate_features_table(active_cmds, owner_cmds, cache, lang="ru"):
    lines = []
    if lang == "ru":
        lines.append("| | Функция | Описание |")
        lines.append("|---|---------|----------|")
        for cmd, data in active_cmds.items():
            ai_desc = get_ai_description(cmd, data["name"], data["desc"], cache)
            args = f" {data['args']}" if "args" in data else ""
            lines.append(
                f"| {data['icon']} | **{data['name']}** | `{cmd}{args}` — {ai_desc} |"
            )

        if owner_cmds:
            lines.append("| 👑 | **Команды владельца** | `---` |")
            for cmd, data in owner_cmds.items():
                ai_desc = get_ai_description(cmd, data["name"], data["desc"], cache)
                args = f" {data['args']}" if "args" in data else ""
                lines.append(
                    f"| {data['icon']} | **{data['name']}** | `{cmd}{args}` — {ai_desc} |"
                )
    else:
        lines.append("| | Feature | Description |")
        lines.append("|---|---------|-------------|")
        for cmd, data in active_cmds.items():
            ai_desc = get_ai_description(cmd, data["name"], data["desc"], cache)
            name_en = t_en(data["name"])
            ai_desc_en = t_en(ai_desc)
            args = f" {data['args']}" if "args" in data else ""
            lines.append(
                f"| {data['icon']} | **{name_en}** | `{cmd}{args}` — {ai_desc_en} |"
            )

        if owner_cmds:
            lines.append("| 👑 | **Owner Commands** | `---` |")
            for cmd, data in owner_cmds.items():
                ai_desc = get_ai_description(cmd, data["name"], data["desc"], cache)
                name_en = t_en(data["name"])
                ai_desc_en = t_en(ai_desc)
                args = f" {data['args']}" if "args" in data else ""
                lines.append(
                    f"| {data['icon']} | **{name_en}** | `{cmd}{args}` — {ai_desc_en} |"
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
            desc_en = t_en(data["desc"])
            content += f"- `{cmd}{args}` – {desc_en}\n"

        content += "\n### Public (`!помощь`)\n"
        for cmd, data in active_cmds.items():
            args = f" {data['args']}" if "args" in data else ""
            desc_en = t_en(data["desc"])
            content += f"- `{cmd}{args}` – {desc_en}\n"

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
    print(f"{C.MAGENTA}{C.BOLD}[INFO] Запуск сборки README...{C.RESET}")

    active_cmds = {
        k: v for k, v in config.COMMAND_METADATA.items() if not v.get("disabled", False)
    }
    owner_cmds = getattr(config, "OWNER_COMMAND_METADATA", {})
    active_owner_cmds = {
        k: v for k, v in owner_cmds.items() if not v.get("disabled", False)
    }

    all_cmds = {**active_cmds, **active_owner_cmds}

    cache = load_cache()

    total_ai_steps = len(all_cmds)
    total_translate_steps = len(all_cmds)
    total_files_steps = 4
    total_overall = total_ai_steps + total_translate_steps + total_files_steps + 1

    pb = DualProgressBar(total_overall)

    pb.start("Генерация ИИ", total_ai_steps)
    for cmd, data in all_cmds.items():
        pb.update_op(1, f"Анализ {cmd}")
        get_ai_description(cmd, data["name"], data["desc"], cache)
        pb.update_overall(1)

    pb.start("Сборка (RU)", 1)
    cmds_ru = generate_commands_section(active_cmds, active_owner_cmds, "ru")
    features_ru = generate_features_table(active_cmds, active_owner_cmds, cache, "ru")
    pb.update_op(1, "Таблицы сформированы")
    pb.update_overall(1)

    pb.start("Сбор строк", 1)
    texts_to_translate = []
    for cmd, data in all_cmds.items():
        ai_desc = get_ai_description(cmd, data["name"], data["desc"], cache)
        for t in (data["name"], data["desc"], ai_desc):
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
            except Exception:
                for orig in chunk:
                    translation_cache[orig] = orig

        save_trans_cache(translation_cache)
    else:
        pb.start("Перевод (EN)", 1)
        pb.update_op(1, "Всё взято из кэша")

    pb.update_overall(total_translate_steps)

    cmds_en = generate_commands_section(active_cmds, active_owner_cmds, "en")
    features_en = generate_features_table(active_cmds, active_owner_cmds, cache, "en")

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

    for success, msg in results:
        if success:
            print(f"  [SUCCESS] {msg}")
        else:
            print(f"  [ERROR] {msg}")

    print(f"\n{C.GREEN}{C.BOLD}[INFO] Все README файлы успешно обновлены!{C.RESET}")


if __name__ == "__main__":
    main()

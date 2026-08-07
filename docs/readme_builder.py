import os
import sys
import json
import time
import re
import argparse
import asyncio
import logging
from dotenv import load_dotenv

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(SCRIPT_DIR)

env_path = os.path.join(ROOT_DIR, ".env")
if os.path.exists(env_path):
    load_dotenv(env_path)

sys.path.insert(0, ROOT_DIR)

os.environ.setdefault("OWNER_ID", "1")
os.environ.setdefault("BOT_TOKEN", "dummy")

logging.getLogger("bot.utils.ai_core").setLevel(logging.CRITICAL)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)

try:
    import config
    from bot.utils.ai_core import ask_groq_ai
except Exception as e:
    print(f"[ERROR] Не удалось импортировать модули бота: {e}")
    sys.exit(1)

TRANSLATION_CACHE_FILE = os.path.join(SCRIPT_DIR, "translation_cache.json")
README_RU = os.path.join(ROOT_DIR, "docs", "README-RU.md")
README_EN = os.path.join(ROOT_DIR, "docs", "README.md")

TRANSLATION_BATCH_SIZE = 20

TRANSLATION_SYSTEM_PROMPT = (
    "Ты — профессиональный ИИ-переводчик. Твоя задача: перевести массив строк "
    "с русского на английский язык.\n"
    "КРИТИЧЕСКИЕ ПРАВИЛА:\n"
    "1. Сохраняй исходный порядок элементов.\n"
    "2. Переводи точно и технически грамотно.\n"
    '3. Верни ответ СТРОГО в формате JSON-массива строк: ["translation1", "translation2"].\n'
    "Не используй markdown-блоки, верни только сырой JSON!"
)

GROUP_LABELS_EN = {
    "ai": "🧠 AI & Personas",
    "media": "🎬 Media & Downloads",
    "fun": "🎭 Fun & Games",
    "tools": "🛠 Utilities",
}

LANG_LABELS = {
    "ru": {
        "cmd_col": "Команда",
        "desc_col": "Описание",
        "owner_section": "👑 Команды владельца",
        "rp_title": "RP-команды",
        "rp_reply_hint": "ответ на сообщение",
        "rp_nsfw_hint": "При включённом NSFW добавляются",
    },
    "en": {
        "cmd_col": "Command",
        "desc_col": "Description",
        "owner_section": "👑 Owner Commands",
        "rp_title": "RP commands",
        "rp_reply_hint": "reply to a message",
        "rp_nsfw_hint": "When NSFW enabled",
    },
}


class C:
    GREEN, YELLOW, RED, RESET = "\033[92m", "\033[93m", "\033[91m", "\033[0m"


def log(message: str, level: str = "INFO") -> None:
    color = {"INFO": C.GREEN, "WARN": C.YELLOW, "ERROR": C.RED}.get(level, C.RESET)
    print(f"{color}[{level}] {message}{C.RESET}")


def chunked(items: list, size: int) -> list:
    return [items[i : i + size] for i in range(0, len(items), size)]


def load_cache(filepath: str) -> dict:
    if not os.path.exists(filepath):
        return {}
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, ValueError):
        return {}


def save_cache(cache: dict, filepath: str) -> None:
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, indent=4)


def _strip_markdown_fence(text: str) -> str:
    cleaned = text.strip()
    if cleaned.startswith("```json"):
        cleaned = cleaned[7:]
    elif cleaned.startswith("```"):
        cleaned = cleaned[3:]
    if cleaned.endswith("```"):
        cleaned = cleaned[:-3]
    return cleaned.strip()


def ask_groq_json(system_prompt: str, user_prompt: str, error_context: str):
    try:
        answer = asyncio.run(
            ask_groq_ai(
                user_prompt=user_prompt, system_prompt=system_prompt, temperature=0.1
            )
        )
    except Exception as e:
        log(f"Сбой Groq API при {error_context}: {e}", "ERROR")
        return None

    if not answer:
        log(
            f"Groq API не вернул ответ при {error_context} (ключи забанены или лимит).",
            "ERROR",
        )
        return None

    try:
        return json.loads(_strip_markdown_fence(answer))
    except json.JSONDecodeError as e:
        log(f"Ошибка парсинга JSON при {error_context}: {e}", "ERROR")
        return None


translation_cache = load_cache(TRANSLATION_CACHE_FILE)


def t_en(text: str) -> str:
    if not text:
        return ""
    return translation_cache.get(text, text)


def translate_batch(texts: list) -> list:
    prompt = f"Переведи этот массив JSON: {json.dumps(texts, ensure_ascii=False)}"
    result = ask_groq_json(TRANSLATION_SYSTEM_PROMPT, prompt, "переводе")
    return result if isinstance(result, list) else []


def group_label(group_id: str, lang: str) -> str:
    return config.HELP_GROUPS[group_id] if lang == "ru" else GROUP_LABELS_EN[group_id]


def build_rows(cmds: dict, lang: str) -> list:
    rows = []
    for cmd, data in cmds.items():
        args = f" {data['args']}" if "args" in data else ""
        desc = data["desc"] if lang == "ru" else t_en(data["desc"])
        rows.append((data.get("icon", "🔹"), f"{cmd}{args}", desc))
    return rows


def render_table(rows: list, labels: dict) -> str:
    lines = [f"| | {labels['cmd_col']} | {labels['desc_col']} |", "|---|---|---|"]
    for icon, display, desc in rows:
        lines.append(f"| {icon} | `{display}` | {desc} |")
    return "\n".join(lines)


def generate_commands_section(active_cmds: dict, owner_cmds: dict, lang: str) -> str:
    labels = LANG_LABELS[lang]
    blocks = []

    for group_id in config.HELP_GROUPS:
        cmds_in_group = {
            cmd: data for cmd, data in active_cmds.items() if data.get("group") == group_id
        }
        if not cmds_in_group:
            continue
        rows = build_rows(cmds_in_group, lang)
        blocks.append(f"### {group_label(group_id, lang)}\n{render_table(rows, labels)}")

    if owner_cmds:
        rows = build_rows(owner_cmds, lang)
        blocks.append(
            f"### {labels['owner_section']} (`!ownerhelp`)\n{render_table(rows, labels)}"
        )

    sfw_rp = ", ".join(f"`{cmd}`" for cmd in config.SFW_RP_ACTIONS)
    nsfw_rp = ", ".join(f"`{cmd}`" for cmd in config.NSFW_RP_ACTIONS)
    blocks.append(
        f"**{labels['rp_title']}** ({labels['rp_reply_hint']}):\n"
        f"SFW: {sfw_rp}.  \n"
        f"{labels['rp_nsfw_hint']}: {nsfw_rp}."
    )

    return "\n\n".join(blocks)


def update_readme(file_path: str, marker_name: str, new_content: str) -> tuple:
    if not os.path.exists(file_path):
        return False, f"Файл {os.path.basename(file_path)} не найден"

    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()

    pattern = rf"(<!--\s*{marker_name}_START\s*-->).*?(<!--\s*{marker_name}_END\s*-->)"
    if not re.search(pattern, content, flags=re.DOTALL):
        return False, f"Маркеры {marker_name} не найдены в {os.path.basename(file_path)}"

    updated = re.sub(pattern, rf"\1\n{new_content}\n\2", content, flags=re.DOTALL)
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(updated)
    return True, f"Обновлён блок {marker_name} в {os.path.basename(file_path)}"


def collect_commands() -> tuple:
    active_cmds = {
        cmd: data
        for cmd, data in config.COMMAND_METADATA.items()
        if not data.get("disabled", False)
    }
    owner_cmds = {
        cmd: data
        for cmd, data in config.OWNER_COMMAND_METADATA.items()
        if not data.get("disabled", False)
    }
    return active_cmds, owner_cmds


def generate_translations(all_cmds: dict, force: bool = False) -> None:
    texts = []
    for data in all_cmds.values():
        text = data["desc"]
        if text and (force or text not in translation_cache) and text not in texts:
            texts.append(text)

    if not texts:
        log("Переводы уже в кэше.")
        return

    batches = chunked(texts, TRANSLATION_BATCH_SIZE)
    log(f"Перевожу {len(texts)} строк ({len(batches)} батчей)...")

    for i, batch in enumerate(batches, 1):
        log(f"Пакет перевода {i}/{len(batches)}...")
        translated = translate_batch(batch)
        if len(translated) == len(batch):
            for original, result in zip(batch, translated):
                translation_cache[original] = result or original
        else:
            log("Несовпадение длин ответа перевода, оставляю оригиналы.", "WARN")
            for original in batch:
                translation_cache.setdefault(original, original)
        time.sleep(0.5)

    save_cache(translation_cache, TRANSLATION_CACHE_FILE)


def render_and_write(active_cmds: dict, owner_cmds: dict) -> list:
    jobs = [
        (README_RU, "COMMANDS_SECTION", generate_commands_section(active_cmds, owner_cmds, "ru")),
        (README_EN, "COMMANDS_SECTION", generate_commands_section(active_cmds, owner_cmds, "en")),
    ]
    return [update_readme(*job) for job in jobs]


def main() -> None:
    parser = argparse.ArgumentParser(description="Утилита генерации README с использованием Groq ИИ")
    parser.add_argument(
        "--force", action="store_true", help="Игнорировать кэш и перевести все описания заново"
    )
    parser.add_argument(
        "--clear-cache", action="store_true", help="Очистить кэш переводов перед запуском"
    )
    args = parser.parse_args()

    if args.clear_cache and os.path.exists(TRANSLATION_CACHE_FILE):
        os.remove(TRANSLATION_CACHE_FILE)
        translation_cache.clear()
        log("Кэш переводов очищен.")

    log("Запуск сборки README (движок: Groq)...")

    active_cmds, owner_cmds = collect_commands()
    all_cmds = {**active_cmds, **owner_cmds}

    generate_translations(all_cmds, args.force)

    results = render_and_write(active_cmds, owner_cmds)

    print()
    log("Итоги обновления README:")
    for success, msg in results:
        log(msg, "INFO" if success else "ERROR")


if __name__ == "__main__":
    main()

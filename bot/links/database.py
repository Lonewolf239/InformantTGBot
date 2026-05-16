import sqlite3
import os
from datetime import datetime
from typing import List, Dict, Optional

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'bot_links.db')

def init_links_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS saved_links (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            url TEXT NOT NULL,
            type TEXT NOT NULL,
            from_user_id INTEGER,
            from_username TEXT,
            from_first_name TEXT,
            chat_id INTEGER,
            added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            is_viewed BOOLEAN DEFAULT 0,
            viewed_at TIMESTAMP
        )
    ''')

    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_links_type ON saved_links(type)
    ''')
    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_links_viewed ON saved_links(is_viewed)
    ''')

    conn.commit()
    conn.close()

def detect_link_type(url: str) -> str:
    url_lower = url.lower()
    if any(domain in url_lower for domain in [
        'music.youtube.com', 'youtube.com/music', 'music.youtu.be'
    ]):
        return "youtube_music"
    elif any(domain in url_lower for domain in [
        'youtube.com/watch', 'youtu.be/', 'youtube.com/shorts', 'youtube.com/playlist'
    ]):
        return "youtube"
    elif 'music.yandex' in url_lower:
        return "yandex_music"
    elif 'spotify.com' in url_lower or 'open.spotify.com' in url_lower:
        return "spotify"
    elif 'music.apple.com' in url_lower:
        return "apple_music"
    elif 'soundcloud.com' in url_lower:
        return "soundcloud"
    else:
        return "other"

def save_link(url: str, link_type: str, from_user_id: int, from_username: str, from_first_name: str, chat_id: int) -> bool:
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    try:
        cursor.execute('''
            INSERT INTO saved_links (url, type, from_user_id, from_username, from_first_name, chat_id, added_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (url, link_type, from_user_id, from_username, from_first_name, chat_id, datetime.now()))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"Ошибка сохранения ссылки: {e}")
        conn.close()
        return False

def get_link(link_id: int) -> str | None:
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT url FROM saved_links WHERE id = ?", (link_id,))
    result = cursor.fetchone()
    conn.close()
    return result[0]

def get_all_links(only_unviewed: bool = False) -> List:
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    if only_unviewed:
        cursor.execute('''
            SELECT id, url, type, from_username, from_first_name, added_at, is_viewed
            FROM saved_links WHERE is_viewed = 0
            ORDER BY added_at DESC
        ''')
    else:
        cursor.execute('''
            SELECT id, url, type, from_username, from_first_name, added_at, is_viewed
            FROM saved_links
            ORDER BY added_at DESC
        ''')

    links = cursor.fetchall()
    conn.close()
    return links

def mark_as_viewed(link_id: int):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE saved_links SET is_viewed = 1, viewed_at = ? WHERE id = ?",
        (datetime.now(), link_id)
    )
    conn.commit()
    conn.close()

def delete_link(link_id: int) -> bool:
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM saved_links WHERE id = ?", (link_id,))
    deleted = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return deleted

def get_unviewed_links_grouped() -> Dict[str, int]:
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute('''
        SELECT type, COUNT(*)
        FROM saved_links
        WHERE is_viewed = 0
        GROUP BY type
        ORDER BY COUNT(*) DESC
    ''')

    grouped = {}
    for link_type, count in cursor.fetchall():
        grouped[link_type] = count
    conn.close()
    return grouped

def get_unviewed_links_by_type(link_type: str) -> List:
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute('''
        SELECT id, url, type, from_username, from_first_name, added_at
        FROM saved_links
        WHERE is_viewed = 0 AND type = ?
        ORDER BY added_at DESC
    ''', (link_type,))

    results = cursor.fetchall()
    conn.close()
    return results

def get_stats() -> dict:
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute('''
        SELECT
            COUNT(*) as total,
            SUM(CASE WHEN is_viewed = 0 THEN 1 ELSE 0 END) as unviewed,
            COUNT(DISTINCT type) as types_count,
            COUNT(DISTINCT from_user_id) as senders_count
        FROM saved_links
    ''')

    result = cursor.fetchone()
    conn.close()
    return {
        'total': result[0] or 0,
        'unviewed': result[1] or 0,
        'types_count': result[2] or 0,
        'senders_count': result[3] or 0
    }

def format_date(date_str: str) -> str:
    try:
        dt = datetime.strptime(date_str, '%Y-%m-%d %H:%M:%S.%f')
    except:
        try:
            dt = datetime.strptime(date_str, '%Y-%m-%d %H:%M:%S')
        except:
            return date_str

    now = datetime.now()
    diff = now - dt

    if diff.days == 0:
        if diff.seconds < 3600:
            minutes = diff.seconds // 60
            return f"{minutes} мин. назад" if minutes > 0 else "только что"
        else:
            hours = diff.seconds // 3600
            return f"{hours} ч. назад"
    elif diff.days == 1:
        return "вчера"
    elif diff.days < 7:
        return f"{diff.days} дн. назад"
    else:
        return dt.strftime("%d.%m.%Y")

def get_type_emoji_and_name(link_type: str) -> tuple:
    type_info = {
        "youtube_music": ("🎵", "YouTube Music"),
        "youtube": ("▶️", "YouTube"),
        "yandex_music": ("🎶", "Яндекс Музыка"),
        "spotify": ("🟢", "Spotify"),
        "apple_music": ("🍎", "Apple Music"),
        "soundcloud": ("☁️", "SoundCloud"),
        "other": ("🔗", "Другое")
    }
    return type_info.get(link_type, ("🔗", "Другое"))

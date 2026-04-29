"""
app/database.py — SQLite 資料庫模組
記錄使用者資訊與每次互動紀錄（userId、訊息、回覆、時間戳記）。
"""
import sqlite3
import logging
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

DB_PATH = Path(__file__).parent.parent / "data" / "bot.db"


def get_connection() -> sqlite3.Connection:
    """建立並回傳 SQLite 連線。"""
    DB_PATH.parent.mkdir(exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """初始化資料庫，建立必要的資料表。"""
    with get_connection() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                user_id     TEXT PRIMARY KEY,
                first_seen  TEXT NOT NULL,
                last_active TEXT NOT NULL,
                message_count INTEGER DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS interactions (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id     TEXT NOT NULL,
                intent_type TEXT NOT NULL,
                user_message TEXT NOT NULL,
                bot_reply   TEXT NOT NULL,
                created_at  TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            );
        """)
    logger.info(f"SQLite 資料庫初始化完成：{DB_PATH}")


def upsert_user(user_id: str) -> None:
    """新增使用者（若已存在則更新最後活躍時間）。"""
    now = datetime.now().isoformat()
    with get_connection() as conn:
        conn.execute("""
            INSERT INTO users (user_id, first_seen, last_active, message_count)
            VALUES (?, ?, ?, 1)
            ON CONFLICT(user_id) DO UPDATE SET
                last_active = excluded.last_active,
                message_count = message_count + 1
        """, (user_id, now, now))


def save_interaction(
    user_id: str,
    intent_type: str,
    user_message: str,
    bot_reply: str,
) -> None:
    """儲存一筆互動紀錄。"""
    now = datetime.now().isoformat()
    with get_connection() as conn:
        conn.execute("""
            INSERT INTO interactions
                (user_id, intent_type, user_message, bot_reply, created_at)
            VALUES (?, ?, ?, ?, ?)
        """, (user_id, intent_type, user_message, bot_reply, now))


def get_user_stats(user_id: str) -> dict | None:
    """取得指定使用者的統計資訊。"""
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM users WHERE user_id = ?", (user_id,)
        ).fetchone()
        return dict(row) if row else None

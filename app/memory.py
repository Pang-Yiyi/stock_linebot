"""
app/memory.py — 對話 Session 記憶體管理
以 user_id 為 key，儲存每位使用者的對話歷史。
Session 超過 SESSION_TIMEOUT_MINUTES 分鐘無互動後自動清除。
"""
import logging
from datetime import datetime, timedelta
from app.config import SESSION_TIMEOUT_MINUTES, MAX_HISTORY_TURNS

logger = logging.getLogger(__name__)

# 結構：{ user_id: { "history": [...], "last_active": datetime } }
_store: dict = {}


def get_history(user_id: str) -> list[dict]:
    """取得使用者對話歷史，若 Session 已過期則回傳空串列。"""
    _cleanup_expired()
    session = _store.get(user_id)
    if not session:
        return []
    return session["history"]


def add_message(user_id: str, role: str, content: str) -> None:
    """新增一則訊息至對話歷史，並更新最後活躍時間。"""
    _cleanup_expired()
    if user_id not in _store:
        _store[user_id] = {"history": [], "last_active": datetime.now()}

    _store[user_id]["history"].append({"role": role, "parts": [content]})
    _store[user_id]["last_active"] = datetime.now()

    # 限制歷史長度（保留最近 N 輪 = 2N 則訊息）
    max_messages = MAX_HISTORY_TURNS * 2
    if len(_store[user_id]["history"]) > max_messages:
        _store[user_id]["history"] = _store[user_id]["history"][-max_messages:]


def clear_session(user_id: str) -> None:
    """手動清除指定使用者的 Session。"""
    _store.pop(user_id, None)


def _cleanup_expired() -> None:
    """清除所有超過 SESSION_TIMEOUT_MINUTES 的過期 Session。"""
    now = datetime.now()
    timeout = timedelta(minutes=SESSION_TIMEOUT_MINUTES)
    expired = [uid for uid, s in _store.items() if now - s["last_active"] > timeout]
    for uid in expired:
        del _store[uid]
        logger.debug(f"Session 已過期並清除：{uid}")

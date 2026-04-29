"""
app/handlers/gemini_handler.py — Gemini AI 對話模組
使用 google-genai 呼叫 Gemini 2.5 Flash，並整合對話歷史記憶。
"""
import logging
from google import genai
from google.genai import types
from app.config import GEMINI_API_KEY, GEMINI_MODEL
from app import memory

logger = logging.getLogger(__name__)

# 初始化 Gemini 客戶端
client = genai.Client(api_key=GEMINI_API_KEY)

SYSTEM_PROMPT = """你是一個專業的股票投資助理 LINE Bot，名叫「股小智」。
你的能力：
1. 回答股票、投資、理財相關問題
2. 用清楚易懂的繁體中文解說財經概念
3. 進行一般對話，保持友善、專業的語氣

注意事項：
- 不要提供具體的買賣建議或保證獲利
- 若使用者查詢即時股價，告知系統會自動查詢最新資料
- 回覆請簡潔，適合手機 LINE 閱讀（避免過長段落）
"""


async def chat(user_id: str, user_message: str) -> str:
    """
    與 Gemini 進行對話，自動帶入對話歷史。

    Args:
        user_id: LINE 使用者 ID（用於 Session 管理）
        user_message: 使用者輸入的訊息

    Returns:
        Gemini 回覆的文字
    """
    try:
        # 取得對話歷史，轉換為 google.genai Content 格式
        raw_history = memory.get_history(user_id)
        history = [
            types.Content(role=msg["role"], parts=[types.Part(text=msg["parts"][0])])
            for msg in raw_history
        ]

        # 建立 chat session
        chat_session = client.chats.create(
            model=GEMINI_MODEL,
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT,
            ),
            history=history,
        )

        # 發送訊息並取得回覆
        response = chat_session.send_message(user_message)
        reply_text = response.text.strip()

        # 更新對話歷史
        memory.add_message(user_id, "user", user_message)
        memory.add_message(user_id, "model", reply_text)

        return reply_text

    except Exception as e:
        logger.error(f"Gemini API 呼叫失敗 user_id={user_id} error={e}")
        return "🤖 AI 暫時無法回應，請稍後再試。"

"""
app/webhook.py — LINE Webhook 路由與事件分發
嚴格遵循 linebot-dev SKILL 規範：
  ✅ 使用 line-bot-sdk v3
  ✅ 立即回應 HTTP 200，耗時操作交給 BackgroundTasks
  ✅ 驗證 X-Line-Signature
  ✅ 背景任務一律使用 Push Message（不依賴 reply_token）
  ✅ 回傳空 JSON {}
"""
import logging
from fastapi import APIRouter, Request, HTTPException, BackgroundTasks

from linebot.v3.webhook import WebhookParser
from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.webhooks import (
    MessageEvent,
    TextMessageContent,
    FollowEvent,
    UnfollowEvent,
)
from linebot.v3.messaging import (
    ApiClient,
    Configuration,
    MessagingApi,
    PushMessageRequest,
    TextMessage,
)

from app.config import LINE_CHANNEL_SECRET, LINE_CHANNEL_ACCESS_TOKEN
from app.intent import classify_intent
from app.handlers import gemini_handler, stock_handler

logger = logging.getLogger(__name__)
router = APIRouter()

# ✅ 從環境變數初始化，絕不寫死
configuration = Configuration(access_token=LINE_CHANNEL_ACCESS_TOKEN)
parser = WebhookParser(LINE_CHANNEL_SECRET)


# ─────────────────────────────────────────
# Webhook 端點
# ─────────────────────────────────────────

@router.post("/webhook")
async def webhook(request: Request, background_tasks: BackgroundTasks):
    """
    LINE Messaging API Webhook 端點。
    ✅ 立即驗證簽章並回應 200，事件處理交給背景任務。
    """
    body = await request.body()
    signature = request.headers.get("X-Line-Signature", "")

    # ✅ 簽章驗證
    try:
        events = parser.parse(body.decode("utf-8"), signature)
    except InvalidSignatureError:
        logger.warning("收到無效簽章的請求，已拒絕")
        raise HTTPException(status_code=400, detail="Invalid signature")

    # ✅ 每個事件交給背景任務處理（避免超過 LINE 的 1 秒逾時限制）
    for event in events:
        background_tasks.add_task(handle_event, event)

    return {}  # ✅ 必須回傳空 JSON


# ─────────────────────────────────────────
# 事件分發
# ─────────────────────────────────────────

async def handle_event(event) -> None:
    """根據事件類型分發至對應的處理函式。"""
    if isinstance(event, MessageEvent):
        if isinstance(event.message, TextMessageContent):
            await handle_text_message(event)
        else:
            # 非文字訊息（貼圖、圖片等）→ 友善提示
            await push_message(
                event.source.user_id,
                "😊 目前只支援文字訊息，請輸入文字來查詢股價或聊天！"
            )
    elif isinstance(event, FollowEvent):
        await handle_follow(event)
    elif isinstance(event, UnfollowEvent):
        logger.info(f"使用者封鎖 Bot：{event.source.user_id}")


# ─────────────────────────────────────────
# 文字訊息處理（核心邏輯）
# ─────────────────────────────────────────

async def handle_text_message(event: MessageEvent) -> None:
    """
    處理文字訊息：
    1. 意圖識別 → 股價查詢 or AI 對話
    2. 呼叫對應模組取得回覆
    3. 用 Push Message 回傳（背景任務中 reply_token 可能已過期）
    """
    # ✅ 防禦性取 user_id（群組場景可能為 None）
    user_id = getattr(event.source, "user_id", None)
    if not user_id:
        logger.warning("無法取得 user_id，跳過處理")
        return

    text = event.message.text.strip()
    logger.info(f"收到訊息 user={user_id[:8]}... text={text[:30]}")

    # 意圖識別
    intent = classify_intent(text)

    if intent["type"] == "stock":
        reply = await stock_handler.get_stock_message(intent["symbol"])
    else:
        reply = await gemini_handler.chat(user_id, text)

    await push_message(user_id, reply)


# ─────────────────────────────────────────
# 加入好友
# ─────────────────────────────────────────

async def handle_follow(event: FollowEvent) -> None:
    """使用者加入好友時發送歡迎訊息。"""
    user_id = getattr(event.source, "user_id", None)
    if not user_id:
        return

    welcome = (
        "👋 歡迎使用股小智！\n\n"
        "我可以幫你：\n"
        "📈 查詢台股 / 美股即時股價\n"
        "🤖 回答股票與投資相關問題\n\n"
        "試試看：\n"
        "• 輸入「2330」查台積電股價\n"
        "• 輸入「NVDA 現在多少？」\n"
        "• 問我「本益比是什麼？」"
    )
    await push_message(user_id, welcome)


# ─────────────────────────────────────────
# 工具函式
# ─────────────────────────────────────────

async def push_message(user_id: str, text: str) -> None:
    """
    透過 LINE Push Message API 發送訊息。
    ✅ 背景任務統一使用此函式（不依賴 reply_token）
    """
    try:
        with ApiClient(configuration) as api_client:
            api = MessagingApi(api_client)
            api.push_message(
                PushMessageRequest(
                    to=user_id,
                    messages=[TextMessage(text=text)],
                )
            )
    except Exception as e:
        logger.error(f"Push Message 失敗 user_id={user_id} error={e}")

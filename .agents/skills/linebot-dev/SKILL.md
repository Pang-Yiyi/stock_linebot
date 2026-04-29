---
name: linebot-dev
description: 指導 AI 使用 line-bot-sdk-python v3 撰寫 LINE Bot 程式碼，包含標準 Webhook 寫法、事件處理、常見地雷與開發 checklist。
---

# Skill: LINE Bot 開發指南（linebot-dev）

## 目標
使用 **line-bot-sdk-python v3** 搭配 **FastAPI** 建立符合生產品質的 LINE Bot，避免常見錯誤，確保程式碼安全、可維護。

---

## 1. SDK 版本：v2 vs v3 差異對照

> ⚠️ **重要**：v2 與 v3 的 API 介面差異極大，混用會導致執行錯誤。本專案一律使用 **v3**。

| 項目 | v2（舊版，已棄用） | v3（現行版本） |
|------|------------------|--------------|
| 套件安裝 | `pip install line-bot-sdk` | `pip install line-bot-sdk` (>=3.0) |
| import 路徑 | `from linebot import LineBotApi, WebhookHandler` | `from linebot.v3.messaging import ...` |
| API 物件 | `LineBotApi(token)` | `ApiClient(configuration)` + `MessagingApi(client)` |
| Webhook 解析 | `WebhookHandler` | `WebhookParser` 或 `WebhookHandler` |
| 設定物件 | 無 | `Configuration(access_token=...)` |
| 傳送訊息 | `line_bot_api.reply_message(token, TextSendMessage(...))` | `api.reply_message_with_http_info(ReplyMessageRequest(...))` |
| 訊息物件 | `TextSendMessage(text="...")` | `TextMessage(text="...")` |
| 簽章驗證 | `handler.handle(body, signature)` | `parser.parse(body, signature)` 或同名 handler |

### v3 正確 import 範例

```python
# Webhook 解析
from linebot.v3.webhooks import (
    MessageEvent,
    TextMessageContent,
    FollowEvent,
    UnfollowEvent,
    PostbackEvent,
)

# API 呼叫
from linebot.v3.messaging import (
    ApiClient,
    Configuration,
    MessagingApi,
    ReplyMessageRequest,
    PushMessageRequest,
    TextMessage,
)

# 簽章驗證
from linebot.v3.webhook import WebhookParser
from linebot.v3.exceptions import InvalidSignatureError
```

---

## 2. Webhook + Handler 標準寫法

### 2.1 完整 FastAPI 範例（標準結構）

```python
# app/webhook.py
import os
import logging
from fastapi import APIRouter, Request, HTTPException, BackgroundTasks
from linebot.v3.webhook import WebhookParser
from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.webhooks import MessageEvent, TextMessageContent, FollowEvent
from linebot.v3.messaging import (
    ApiClient, Configuration, MessagingApi,
    ReplyMessageRequest, PushMessageRequest, TextMessage,
)

logger = logging.getLogger(__name__)
router = APIRouter()

# ✅ 從環境變數讀取，絕對不寫死在程式碼中
configuration = Configuration(
    access_token=os.environ["LINE_CHANNEL_ACCESS_TOKEN"]
)
parser = WebhookParser(os.environ["LINE_CHANNEL_SECRET"])


@router.post("/webhook")
async def webhook(request: Request, background_tasks: BackgroundTasks):
    body = await request.body()
    signature = request.headers.get("X-Line-Signature", "")

    # ✅ 簽章驗證：非法請求直接拒絕
    try:
        events = parser.parse(body.decode("utf-8"), signature)
    except InvalidSignatureError:
        raise HTTPException(status_code=400, detail="Invalid signature")

    # ✅ 立即回應 200，耗時操作交給背景任務
    for event in events:
        background_tasks.add_task(handle_event, event)

    return {}  # LINE 要求回傳空 JSON，不可有其他內容


async def handle_event(event):
    """分發事件至對應的 handler"""
    if isinstance(event, MessageEvent):
        if isinstance(event.message, TextMessageContent):
            await handle_text_message(event)
    elif isinstance(event, FollowEvent):
        await handle_follow(event)


async def handle_text_message(event: MessageEvent):
    user_id = event.source.user_id
    text = event.message.text
    reply_token = event.reply_token

    # ✅ 耗時操作完成後用 Push Message（reply token 已過期）
    response_text = f"你說：{text}"  # 替換為實際邏輯

    with ApiClient(configuration) as api_client:
        api = MessagingApi(api_client)
        # ✅ 使用 Push Message（背景任務中 reply token 可能已過期）
        api.push_message(
            PushMessageRequest(
                to=user_id,
                messages=[TextMessage(text=response_text)]
            )
        )


async def handle_follow(event: FollowEvent):
    """使用者加入好友時觸發"""
    user_id = event.source.user_id
    with ApiClient(configuration) as api_client:
        api = MessagingApi(api_client)
        api.push_message(
            PushMessageRequest(
                to=user_id,
                messages=[TextMessage(text="歡迎加入！傳訊息給我開始對話 👋")]
            )
        )
```

### 2.2 Reply vs Push Message 選擇原則

```
同步處理（< 1 秒內完成）     → 使用 Reply Message（需要 reply_token）
非同步背景任務               → 使用 Push Message（使用 user_id）
主動推播通知                 → 使用 Push Message（使用 user_id）
```

**Reply Message 正確用法（同步場景）：**
```python
with ApiClient(configuration) as api_client:
    api = MessagingApi(api_client)
    api.reply_message(
        ReplyMessageRequest(
            reply_token=event.reply_token,   # ✅ 只能用一次，5 分鐘內有效
            messages=[TextMessage(text="回覆內容")]
        )
    )
```

### 2.3 FastAPI 主程式

```python
# app/main.py
from fastapi import FastAPI
from app.webhook import router

app = FastAPI(title="Stock LINE Bot")
app.include_router(router)

@app.get("/")
async def health_check():
    return {"status": "ok", "service": "Stock LINE Bot"}
```

---

## 3. 常見地雷 ⚠️

### 地雷 1：Reply Token 限制

```python
# ❌ 錯誤：reply token 只能使用一次且有 5 分鐘時效
# 在背景任務中使用 reply_token 會失敗（token 已過期）
async def handle_event_wrong(event):
    await asyncio.sleep(3)  # 耗時操作
    api.reply_message(ReplyMessageRequest(
        reply_token=event.reply_token,  # ❌ 此時 token 可能已過期
        messages=[TextMessage(text="太慢了")]
    ))

# ✅ 正確：背景任務一律改用 Push Message
async def handle_event_correct(event):
    user_id = event.source.user_id
    await asyncio.sleep(3)  # 耗時操作
    api.push_message(PushMessageRequest(
        to=user_id,               # ✅ 用 user_id，不受時間限制
        messages=[TextMessage(text="處理完成！")]
    ))
```

### 地雷 2：API 金鑰絕對不能寫死

```python
# ❌ 錯誤：金鑰直接寫在程式碼中（嚴重安全漏洞）
configuration = Configuration(access_token="Abcdef123456...")

# ✅ 正確：從環境變數讀取
configuration = Configuration(
    access_token=os.environ["LINE_CHANNEL_ACCESS_TOKEN"]
)

# ✅ 啟動時驗證必要環境變數是否存在
REQUIRED_ENVS = [
    "LINE_CHANNEL_SECRET",
    "LINE_CHANNEL_ACCESS_TOKEN",
    "GEMINI_API_KEY",
]
for key in REQUIRED_ENVS:
    if not os.environ.get(key):
        raise EnvironmentError(f"缺少必要環境變數：{key}")
```

### 地雷 3：耗時操作必須背景處理

```python
# ❌ 錯誤：在 webhook handler 中直接呼叫 Gemini / 股價 API
@router.post("/webhook")
async def webhook(request: Request):
    events = parser.parse(body, signature)
    for event in events:
        await call_gemini_api(event)   # ❌ 超過 1 秒 LINE 會重送！
    return {}

# ✅ 正確：立即回應 200，耗時操作放 BackgroundTasks
@router.post("/webhook")
async def webhook(request: Request, background_tasks: BackgroundTasks):
    events = parser.parse(body, signature)
    for event in events:
        background_tasks.add_task(handle_event, event)  # ✅ 背景執行
    return {}
```

### 地雷 4：簽章驗證不可省略

```python
# ❌ 錯誤：跳過簽章驗證（任何人都能偽造請求）
@router.post("/webhook")
async def webhook(request: Request):
    body = await request.json()  # ❌ 直接解析，沒有驗證來源

# ✅ 正確：使用 WebhookParser 驗證 X-Line-Signature
@router.post("/webhook")
async def webhook(request: Request):
    body = await request.body()
    signature = request.headers.get("X-Line-Signature", "")
    try:
        events = parser.parse(body.decode("utf-8"), signature)
    except InvalidSignatureError:
        raise HTTPException(status_code=400, detail="Invalid signature")
```

### 地雷 5：Webhook 必須回傳空 JSON

```python
# ❌ 錯誤：回傳其他內容
return {"message": "ok"}    # LINE 平台可能誤判為失敗

# ✅ 正確：回傳空 JSON 物件
return {}
```

### 地雷 6：source.user_id 可能為 None（群組場景）

```python
# ❌ 錯誤：直接取 user_id
user_id = event.source.user_id  # 群組中可能為 None

# ✅ 正確：加上防禦性判斷
user_id = getattr(event.source, "user_id", None)
if not user_id:
    return  # 無法識別使用者，跳過處理
```

---

## 4. 所有事件類型與訊息類型

### 4.1 事件類型（Event Types）

| 事件類型 | Class | 觸發時機 |
|---------|-------|---------|
| 訊息事件 | `MessageEvent` | 使用者傳送任何訊息 |
| 加入好友 | `FollowEvent` | 使用者加入好友或解除封鎖 |
| 封鎖 | `UnfollowEvent` | 使用者封鎖 Bot |
| 加入群組 | `JoinEvent` | Bot 被加入群組或聊天室 |
| 離開群組 | `LeaveEvent` | Bot 被移除出群組 |
| Postback | `PostbackEvent` | 使用者點擊 Postback 按鈕 |
| 位置 | `BeaconEvent` | 使用者進入 Beacon 範圍 |
| 帳號連結 | `AccountLinkEvent` | 帳號連結完成 |
| 成員加入 | `MemberJoinedEvent` | 群組有新成員加入 |
| 成員離開 | `MemberLeftEvent` | 群組有成員離開 |

```python
from linebot.v3.webhooks import (
    MessageEvent, FollowEvent, UnfollowEvent,
    JoinEvent, LeaveEvent, PostbackEvent,
    MemberJoinedEvent, MemberLeftEvent,
)
```

### 4.2 訊息類型（Message Content Types）

| 訊息類型 | Class | 說明 |
|---------|-------|------|
| 文字 | `TextMessageContent` | 純文字訊息 |
| 圖片 | `ImageMessageContent` | 使用者傳送的圖片 |
| 影片 | `VideoMessageContent` | 使用者傳送的影片 |
| 音訊 | `AudioMessageContent` | 使用者傳送的語音 |
| 檔案 | `FileMessageContent` | 使用者傳送的檔案 |
| 位置 | `LocationMessageContent` | 使用者分享的位置 |
| 貼圖 | `StickerMessageContent` | 使用者傳送的貼圖 |

```python
from linebot.v3.webhooks import (
    TextMessageContent,
    ImageMessageContent,
    VideoMessageContent,
    AudioMessageContent,
    FileMessageContent,
    LocationMessageContent,
    StickerMessageContent,
)

# 判斷訊息類型
async def handle_message(event: MessageEvent):
    msg = event.message
    if isinstance(msg, TextMessageContent):
        print(f"文字: {msg.text}")
    elif isinstance(msg, ImageMessageContent):
        print(f"圖片 ID: {msg.id}")
    elif isinstance(msg, LocationMessageContent):
        print(f"位置: {msg.address}, lat={msg.latitude}")
    elif isinstance(msg, StickerMessageContent):
        print(f"貼圖: package={msg.package_id}, sticker={msg.sticker_id}")
```

### 4.3 可發送的訊息類型（Send Message Types）

| 類型 | Class | 說明 |
|------|-------|------|
| 文字 | `TextMessage` | 純文字，最多 5000 字元 |
| 圖片 | `ImageMessage` | 需提供 originalContentUrl + previewImageUrl |
| 影片 | `VideoMessage` | 需提供影片 URL |
| 音訊 | `AudioMessage` | 需提供音訊 URL + duration |
| 位置 | `LocationMessage` | 標題、地址、緯度、經度 |
| 貼圖 | `StickerMessage` | packageId + stickerId |
| 圖文選單 | `FlexMessage` | 高度自訂的結構化訊息 |
| Confirm | `TemplateMessage` + `ConfirmTemplate` | 確認型模板 |
| Buttons | `TemplateMessage` + `ButtonsTemplate` | 按鈕型模板 |

---

## 5. 開發前 Checklist ✅

### 5.1 環境設定

- [ ] 已建立 LINE Developers 帳號
- [ ] 已建立 Messaging API Channel
- [ ] 已取得 `Channel Secret` 與 `Channel Access Token`
- [ ] 已建立 `.env` 檔案並填入所有金鑰
- [ ] `.env` 已加入 `.gitignore`（確認不會被 commit）
- [ ] 已安裝 `line-bot-sdk >= 3.0`（執行 `pip show line-bot-sdk` 確認版本）

### 5.2 Webhook 設定

- [ ] LINE Developers Console → Messaging API → Webhook URL 已設定
- [ ] Webhook URL 必須是 **HTTPS**（本地開發使用 ngrok）
- [ ] **Use webhook** 已切換為 **ON**
- [ ] **Auto-reply messages** 建議關閉（避免官方預設回覆干擾）
- [ ] **Greeting messages** 視需求設定

### 5.3 程式碼安全

- [ ] 所有 API 金鑰透過 `os.environ` 讀取，無硬編碼
- [ ] Webhook 端點有進行 `X-Line-Signature` 簽章驗證
- [ ] 所有耗時操作（AI API、股價查詢）移至背景任務
- [ ] 錯誤發生時有適當的 try/except 與 logging
- [ ] 不在 log 中記錄使用者的訊息內容（隱私）

### 5.4 功能測試

- [ ] 傳送文字訊息，Bot 有正常回覆
- [ ] 傳送非文字訊息（貼圖、圖片），Bot 不會崩潰
- [ ] 模擬 Gemini API 失敗，Bot 回傳友善錯誤訊息
- [ ] 模擬股價 API 失敗，Bot 回傳友善錯誤訊息
- [ ] 確認 LINE Console 的 Webhook 傳送日誌無錯誤

### 5.5 部署前確認

- [ ] 雲端環境已設定所有環境變數
- [ ] LINE Webhook URL 已更新為雲端 HTTPS 端點
- [ ] Health check 端點 `GET /` 回傳正常
- [ ] 部署後傳送實際訊息測試

---

## 6. 快速參考：requirements.txt

```
fastapi>=0.110.0
uvicorn>=0.29.0
line-bot-sdk>=3.0.0
google-generativeai>=0.5.0
yfinance>=0.2.0
python-dotenv>=1.0.0
httpx>=0.27.0
```

---

## 7. 本地開發啟動流程

```bash
# 1. 建立虛擬環境
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate

# 2. 安裝依賴
pip install -r requirements.txt

# 3. 設定環境變數
cp .env.example .env
# 編輯 .env 填入實際金鑰

# 4. 啟動 FastAPI 服務
uvicorn app.main:app --reload --port 8000

# 5. 開啟 ngrok（新終端機視窗）
ngrok http 8000
# 複製 https://xxxx.ngrok-free.app 並貼至 LINE Developers Webhook URL
```

---

## 8. 注意事項

- **SDK 版本**：確保 `line-bot-sdk >= 3.0`，所有 import 路徑以 `linebot.v3` 開頭
- **非同步**：FastAPI handler 使用 `async def`，背景任務函式也使用 `async def`
- **一次性 Reply Token**：每個事件的 reply_token 只能使用一次，背景任務統一改用 Push Message
- **Webhook 回應**：handler 必須在 1 秒內回應 HTTP 200，否則 LINE 平台會重送請求（導致重複處理）
- **免費額度**：LINE Messaging API 免費方案每月 200 則 Push Message，Reply Message 不限；Gemini API 有免費額度限制

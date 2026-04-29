# 系統架構設計文件（ARCHITECTURE.md）

**文件名稱**：股票查詢 AI LINE Bot — 系統架構設計  
**版本**：v1.0  
**建立日期**：2026-04-29  
**對應 PRD**：docs/prd/prd.md v1.0  

---

## 1. 系統架構概述

### 1.1 架構風格
採用**單體後端服務架構（Monolithic Backend）**，以 Python FastAPI 作為 Webhook 伺服器，接收 LINE 平台訊息後進行意圖判斷，分流至 AI 對話模組或股價查詢模組。

### 1.2 高層架構圖

```
┌─────────────────────────────────────────────────────────────┐
│                        使用者端                              │
│                    LINE App (手機/桌面)                      │
└──────────────────────────┬──────────────────────────────────┘
                           │ HTTPS
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                   LINE Platform                              │
│              Messaging API (Webhook Relay)                   │
└──────────────────────────┬──────────────────────────────────┘
                           │ POST /webhook  HTTPS
                           ▼
┌─────────────────────────────────────────────────────────────┐
│              Python Backend (FastAPI)                        │
│  ┌─────────────────────────────────────────────────────┐    │
│  │  Webhook Handler                                     │    │
│  │  - X-Line-Signature 驗證                            │    │
│  │  - 解析 LINE Event                                  │    │
│  │  - 立即回應 HTTP 200（非同步處理）                  │    │
│  └──────────────────┬──────────────────────────────────┘    │
│                     │                                        │
│          ┌──────────▼──────────┐                            │
│          │   意圖識別模組       │                            │
│          │  Intent Classifier  │                            │
│          └──────┬──────────────┘                            │
│                 │                                            │
│       ┌─────────▼──────────┐  ┌──────────────────────────┐ │
│       │  AI 對話模組        │  │  股價查詢模組             │ │
│       │  Gemini Handler    │  │  Stock Handler            │ │
│       └─────────┬──────────┘  └────────────┬─────────────┘ │
│                 │                           │               │
└─────────────────┼───────────────────────────┼───────────────┘
                  │                           │
        ┌─────────▼──────────┐    ┌───────────▼──────────────┐
        │  Google Gemini API  │    │  Stock Price API          │
        │  gemini-2.5-flash   │    │  (yfinance / Fugle)       │
        └────────────────────┘    └──────────────────────────┘
                  │                           │
        └─────────────────────────────────────┘
                           │
                           ▼
                  LINE Push/Reply API
```

### 1.3 非同步處理策略

由於 LINE Webhook 要求在 **1 秒內**回應 HTTP 200，而 Gemini API / 股價 API 的處理時間可能超過此限制，採用以下策略：

```
LINE Platform
     │ POST /webhook
     ▼
FastAPI Webhook Handler
     │── 立即回應 200 OK ──►  LINE Platform（避免逾時）
     │
     └── 非同步背景任務 (BackgroundTasks)
              │
              ▼
         意圖識別 → Gemini / 股價 API
              │
              ▼
         LINE Push Message API（主動推播回覆）
```

---

## 2. 模組設計

### 2.1 模組職責說明

| 模組 | 檔案位置 | 職責 |
|------|---------|------|
| Webhook Handler | `app/webhook.py` | 接收 LINE 事件、簽章驗證、分發任務 |
| 意圖識別 | `app/intent.py` | 判斷使用者意圖（股價查詢 or AI 對話） |
| Gemini 對話 | `app/handlers/gemini_handler.py` | 呼叫 Gemini API，管理對話歷史 |
| 股價查詢 | `app/handlers/stock_handler.py` | 解析股票代號，呼叫股價 API，格式化回覆 |
| LINE 訊息發送 | `app/line_client.py` | 封裝 LINE Reply / Push Message API 呼叫 |
| 對話記憶管理 | `app/memory.py` | 管理各使用者的對話 Session（記憶體 Dict） |
| 設定管理 | `app/config.py` | 讀取環境變數，統一管理設定 |

### 2.2 意圖識別邏輯

意圖識別採用**關鍵字規則 + 正則表達式**（MVP 階段），未來可升級為 Gemini Function Calling。

```
使用者輸入訊息
      │
      ├─ 包含台股代號（4-6位數字）？          → 股價查詢
      ├─ 包含美股代號（大寫英文 2-5 字母）？   → 股價查詢
      ├─ 包含關鍵字（股價、現在多少、查詢...）？→ 股價查詢
      └─ 其他                                 → AI 對話
```

### 2.3 對話記憶結構（P1）

```python
# 記憶體 Dict，key = LINE user_id
session_store = {
    "U1234567890abcdef": {
        "history": [
            {"role": "user", "content": "台積電現在多少？"},
            {"role": "model", "content": "台積電 (2330) 目前股價為 980 元..."},
        ],
        "last_active": datetime(2026, 4, 29, 9, 30, 0)
    }
}
# Session 超過 30 分鐘無互動自動清除（排程清理）
```

---

## 3. API 設計

### 3.1 Webhook 端點

| 方法 | 路徑 | 說明 |
|------|------|------|
| `GET` | `/` | Health check，回傳服務狀態 |
| `POST` | `/webhook` | LINE Messaging API Webhook 端點 |

#### POST /webhook

**Request Headers：**
```
X-Line-Signature: {HMAC-SHA256 簽章}
Content-Type: application/json
```

**Request Body（LINE Event 範例）：**
```json
{
  "destination": "Uxxxxxxxxxxxx",
  "events": [
    {
      "type": "message",
      "replyToken": "nHuyWiB7yP5Zw52FIkcQobQuGDXCTA",
      "source": {
        "userId": "U1234567890abcdef",
        "type": "user"
      },
      "timestamp": 1625665242211,
      "message": {
        "type": "text",
        "id": "444573844083572737",
        "text": "台積電現在多少？"
      }
    }
  ]
}
```

**Response：**
```json
HTTP 200 OK
{}
```
> 回應需在 1 秒內完成，實際訊息透過非同步 Push Message 回傳。

### 3.2 內部模組介面

#### 意圖識別（intent.py）
```python
def classify_intent(text: str) -> dict:
    """
    Returns:
        {"type": "stock", "symbol": "2330"}
        {"type": "chat", "symbol": None}
    """
```

#### 股價查詢（stock_handler.py）
```python
async def get_stock_price(symbol: str) -> dict:
    """
    Returns:
        {
            "name": "台積電",
            "symbol": "2330",
            "price": 980.0,
            "change": +12.0,
            "change_pct": +1.24,
            "timestamp": "2026-04-29 09:30"
        }
    """
```

#### Gemini 對話（gemini_handler.py）
```python
async def chat(user_id: str, message: str) -> str:
    """
    帶入對話歷史，呼叫 Gemini API，更新 session，回傳 AI 回覆文字
    """
```

---

## 4. 資料流程

### 4.1 股價查詢流程

```
使用者 → LINE → Webhook Handler
                    │
                    ├─ 驗證簽章 ✓
                    ├─ 回應 HTTP 200（< 1 秒）
                    └─ 背景任務啟動
                              │
                              ▼
                        Intent Classifier
                        → type: "stock", symbol: "2330"
                              │
                              ▼
                        Stock Handler
                        → 呼叫 yfinance/Fugle API
                        → 取得股價資料
                        → 格式化訊息
                              │
                              ▼
                        LINE Push Message API
                        → 回傳格式化股價訊息給使用者
```

### 4.2 AI 對話流程

```
使用者 → LINE → Webhook Handler
                    │
                    ├─ 驗證簽章 ✓
                    ├─ 回應 HTTP 200（< 1 秒）
                    └─ 背景任務啟動
                              │
                              ▼
                        Intent Classifier
                        → type: "chat"
                              │
                              ▼
                        Memory Manager
                        → 讀取該 user_id 的對話歷史
                              │
                              ▼
                        Gemini Handler
                        → 組合 system prompt + 歷史 + 新訊息
                        → 呼叫 Gemini 2.5 Flash API
                        → 更新對話歷史
                              │
                              ▼
                        LINE Push Message API
                        → 回傳 AI 回覆給使用者
```

---

## 5. 目錄結構

```
w10stockBot/
├── app/
│   ├── __init__.py
│   ├── main.py                  # FastAPI 應用程式入口
│   ├── config.py                # 環境變數設定管理
│   ├── webhook.py               # LINE Webhook 路由與事件分發
│   ├── intent.py                # 意圖識別模組
│   ├── line_client.py           # LINE API 封裝（Reply / Push）
│   ├── memory.py                # 對話 Session 記憶體管理
│   └── handlers/
│       ├── __init__.py
│       ├── gemini_handler.py    # Gemini 2.5 Flash 對話處理
│       └── stock_handler.py     # 股價查詢與格式化
├── data/
│   └── stock_names.csv          # 台股代號與中文名稱對照表（P1）
├── docs/
│   ├── prd/
│   │   └── prd.md               # 產品需求文件
│   └── ARCHITECTURE.md          # 本文件
├── tests/
│   ├── test_intent.py           # 意圖識別單元測試
│   ├── test_stock_handler.py    # 股價查詢單元測試
│   └── test_gemini_handler.py   # Gemini 對話單元測試
├── .env.example                 # 環境變數範本（不含實際金鑰）
├── .gitignore                   # 排除 .env、__pycache__ 等
├── requirements.txt             # Python 依賴套件
└── README.md                    # 專案說明文件
```

---

## 6. 技術棧

| 層次 | 技術選擇 | 版本需求 | 說明 |
|------|---------|---------|------|
| 語言 | Python | ≥ 3.11 | 主要開發語言 |
| Web 框架 | FastAPI | ≥ 0.110 | 高效能非同步 Web 框架 |
| ASGI 伺服器 | Uvicorn | ≥ 0.29 | FastAPI 運行環境 |
| LINE SDK | line-bot-sdk | ≥ 3.x | 官方 LINE Messaging API SDK |
| AI 對話 | google-generativeai | ≥ 0.5 | Gemini 2.5 Flash API |
| 股價資料 | yfinance | ≥ 0.2 | 免費股價資料（含延遲） |
| 環境變數 | python-dotenv | ≥ 1.0 | .env 檔案讀取 |
| 本地開發 Tunnel | ngrok | 最新版 | 本地 Webhook 測試 |

---

## 7. 環境變數設計

```bash
# .env.example

# LINE Bot 設定
LINE_CHANNEL_SECRET=your_channel_secret_here
LINE_CHANNEL_ACCESS_TOKEN=your_access_token_here

# Google Gemini 設定
GEMINI_API_KEY=your_gemini_api_key_here
GEMINI_MODEL=gemini-2.5-flash

# 股價 API 設定（擇一）
STOCK_API_PROVIDER=yfinance        # yfinance | fugle | alphavantage
FUGLE_API_KEY=                     # 使用 Fugle 時填入
ALPHAVANTAGE_API_KEY=              # 使用 Alpha Vantage 時填入

# 應用程式設定
APP_HOST=0.0.0.0
APP_PORT=8000
SESSION_TIMEOUT_MINUTES=30
MAX_HISTORY_TURNS=10
```

---

## 8. 部署規劃

### 8.1 本地開發環境

```bash
# 1. 建立虛擬環境
python -m venv .venv
source .venv/bin/activate

# 2. 安裝依賴
pip install -r requirements.txt

# 3. 設定環境變數
cp .env.example .env
# 填入各 API 金鑰

# 4. 啟動服務
uvicorn app.main:app --reload --port 8000

# 5. 啟動 ngrok（另一個終端機）
ngrok http 8000
# 將 ngrok HTTPS URL 設定至 LINE Developers Webhook URL
```

### 8.2 雲端部署（Render / Railway）

```bash
# 啟動指令
uvicorn app.main:app --host 0.0.0.0 --port $PORT

# 需設定的環境變數（在平台 Dashboard 中設定）
LINE_CHANNEL_SECRET
LINE_CHANNEL_ACCESS_TOKEN
GEMINI_API_KEY
GEMINI_MODEL
STOCK_API_PROVIDER
```

### 8.3 部署檢查清單

- [ ] 所有環境變數已在雲端平台設定
- [ ] LINE Developers Webhook URL 已更新為雲端 HTTPS 端點
- [ ] LINE Developers Webhook 已啟用（Use webhook: ON）
- [ ] Health Check 端點 `GET /` 回傳正常
- [ ] 傳送測試訊息確認 Bot 正常回覆

---

## 9. 安全性設計

| 項目 | 設計 |
|------|------|
| Webhook 簽章驗證 | 每個請求驗證 `X-Line-Signature`（HMAC-SHA256），不合法請求回傳 400 |
| API 金鑰管理 | 所有金鑰存於環境變數，`.env` 加入 `.gitignore`，禁止 commit |
| 使用者資料 | 不持久化儲存使用者訊息，Session 30 分鐘後自動清除 |
| 錯誤訊息 | 系統錯誤不直接暴露給使用者，回傳友善提示訊息 |

---

## 10. 修訂記錄

| 版本 | 日期 | 修改人 | 修改內容 |
|------|------|--------|---------|
| v1.0 | 2026-04-29 | Antigravity | 初版建立 |

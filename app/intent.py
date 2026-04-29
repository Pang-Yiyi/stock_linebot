"""
app/intent.py — 意圖識別模組
判斷使用者輸入是「股價查詢」或「AI 對話」。
MVP 階段採用關鍵字規則 + 正則表達式。
"""
import re

# 台股代號：4~6 位數字（例：2330、00878）
_TAIWAN_STOCK_PATTERN = re.compile(r"\b\d{4,6}\b")

# 美股代號：1~5 個大寫英文字母（例：AAPL、NVDA、TSMC）
_US_STOCK_PATTERN = re.compile(r"\b[A-Z]{1,5}\b")

# 股票查詢關鍵字
_STOCK_KEYWORDS = [
    "股價", "現在多少", "現在幾塊", "漲跌", "今天漲",
    "今天跌", "收盤", "開盤", "查股票", "查一下",
    "股票", "price", "stock",
]

# 公司名稱 → 股票代號對照（常見台股，P1 功能可擴充為 CSV）
_NAME_TO_SYMBOL: dict[str, str] = {
    "台積電": "2330.TW",
    "鴻海": "2317.TW",
    "聯發科": "2454.TW",
    "中華電": "2412.TW",
    "台塑": "1301.TW",
    "富邦金": "2881.TW",
    "國泰金": "2882.TW",
    "台灣大": "3045.TW",
    "廣達": "2382.TW",
    "緯創": "3231.TW",
    "tsmc": "TSM",
    "nvidia": "NVDA",
    "apple": "AAPL",
    "google": "GOOGL",
    "microsoft": "MSFT",
    "meta": "META",
    "amazon": "AMZN",
    "tesla": "TSLA",
}


def classify_intent(text: str) -> dict:
    """
    判斷使用者意圖。

    Returns:
        {"type": "stock", "symbol": "2330.TW"}  → 股價查詢
        {"type": "chat",  "symbol": None}        → AI 對話
    """
    # 1. 檢查公司中文/英文名稱
    lower_text = text.lower()
    for name, symbol in _NAME_TO_SYMBOL.items():
        if name.lower() in lower_text:
            return {"type": "stock", "symbol": symbol}

    # 2. 檢查股票查詢關鍵字
    for keyword in _STOCK_KEYWORDS:
        if keyword.lower() in lower_text:
            # 嘗試從文字中擷取台股代號
            tw_match = _TAIWAN_STOCK_PATTERN.search(text)
            if tw_match:
                return {"type": "stock", "symbol": f"{tw_match.group()}.TW"}
            # 嘗試擷取美股代號
            us_match = _US_STOCK_PATTERN.search(text)
            if us_match:
                return {"type": "stock", "symbol": us_match.group()}
            # 有關鍵字但沒有明確代號
            return {"type": "stock", "symbol": None}

    # 3. 純台股代號（例：使用者直接輸入「2330」）
    tw_match = _TAIWAN_STOCK_PATTERN.search(text)
    if tw_match and len(text.strip()) <= 10:  # 避免誤判含數字的一般句子
        return {"type": "stock", "symbol": f"{tw_match.group()}.TW"}

    # 4. 純美股代號（例：使用者直接輸入「NVDA」）
    us_match = _US_STOCK_PATTERN.search(text)
    if us_match and text.strip() == us_match.group():
        return {"type": "stock", "symbol": us_match.group()}

    # 5. 其他 → AI 對話
    return {"type": "chat", "symbol": None}

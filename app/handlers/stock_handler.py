"""
app/handlers/stock_handler.py — 股價查詢模組
使用 yfinance 取得股票即時（或延遲 15 分鐘）報價，格式化為 LINE 訊息文字。
"""
import logging
import yfinance as yf
from datetime import datetime

logger = logging.getLogger(__name__)


async def get_stock_message(symbol: str) -> str:
    """
    查詢股票報價，回傳格式化的訊息字串。

    Args:
        symbol: 股票代號，例如 "2330.TW"（台股）或 "NVDA"（美股）

    Returns:
        格式化的股價訊息字串（供 LINE 顯示）
    """
    if not symbol:
        return "⚠️ 請提供股票代號，例如：「查 2330」或「台積電股價」"

    try:
        ticker = yf.Ticker(symbol)
        info = ticker.fast_info

        price = getattr(info, "last_price", None)
        prev_close = getattr(info, "previous_close", None)

        if price is None:
            return f"❌ 找不到股票「{symbol}」的資料，請確認代號是否正確。"

        # 計算漲跌
        change = round(price - prev_close, 2) if prev_close else 0
        change_pct = round((change / prev_close) * 100, 2) if prev_close else 0

        # 判斷漲跌方向
        if change > 0:
            direction = f"▲ +{change} (+{change_pct}%)"
            emoji = "📈"
        elif change < 0:
            direction = f"▼ {change} ({change_pct}%)"
            emoji = "📉"
        else:
            direction = f"— {change} ({change_pct}%)"
            emoji = "📊"

        # 取得股票名稱
        name = info.exchange or symbol

        # 格式化時間
        now = datetime.now().strftime("%Y-%m-%d %H:%M")

        message = (
            f"{emoji} {symbol}\n"
            f"當前股價：{price:.2f}\n"
            f"漲跌：{direction}\n"
            f"⏱ 更新時間：{now}\n"
            f"（資料可能有 15 分鐘延遲）"
        )
        return message

    except Exception as e:
        logger.error(f"查詢股價失敗 symbol={symbol} error={e}")
        return f"❌ 查詢股價時發生錯誤，請稍後再試。\n（代號：{symbol}）"

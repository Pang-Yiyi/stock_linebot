"""
app/config.py — 環境變數統一管理
啟動時驗證所有必要的環境變數，任何缺失立即報錯。
"""
import os
from dotenv import load_dotenv

load_dotenv()

# ✅ 必要環境變數清單 — 缺少任一個立即報錯
REQUIRED_ENVS = [
    "LINE_CHANNEL_SECRET",
    "LINE_CHANNEL_ACCESS_TOKEN",
    "GEMINI_API_KEY",
]
for key in REQUIRED_ENVS:
    if not os.environ.get(key):
        raise EnvironmentError(f"❌ 缺少必要環境變數：{key}，請檢查 .env 檔案")

# LINE Bot
LINE_CHANNEL_SECRET: str = os.environ["LINE_CHANNEL_SECRET"]
LINE_CHANNEL_ACCESS_TOKEN: str = os.environ["LINE_CHANNEL_ACCESS_TOKEN"]

# Gemini
GEMINI_API_KEY: str = os.environ["GEMINI_API_KEY"]
GEMINI_MODEL: str = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash-preview-04-17")

# 股價 API
STOCK_API_PROVIDER: str = os.environ.get("STOCK_API_PROVIDER", "yfinance")

# Session 設定
SESSION_TIMEOUT_MINUTES: int = int(os.environ.get("SESSION_TIMEOUT_MINUTES", "30"))
MAX_HISTORY_TURNS: int = int(os.environ.get("MAX_HISTORY_TURNS", "10"))

"""
app/main.py — FastAPI 應用程式入口
"""
import logging
from fastapi import FastAPI
from app.webhook import router
from app import database

# 設定 logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
)

app = FastAPI(
    title="股小智 — 股票查詢 AI LINE Bot",
    description="整合 Gemini 2.5 Flash 與即時股價查詢的 LINE Bot",
    version="1.0.0",
)

# 初始化資料庫
database.init_db()

app.include_router(router)


@app.get("/")
async def health_check():
    """Health check 端點，部署後可用來確認服務正常運作。"""
    return {"status": "ok", "service": "股小智 LINE Bot", "version": "1.0.0"}

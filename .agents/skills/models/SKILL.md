---
name: models
description: 根據 PRD 與架構設計，生成資料模型文件，包含 SQLite 資料表結構、欄位定義與關聯設計。
---

# Skill: 資料模型設計生成器（Models Generator）

## 目標
根據 PRD 功能需求，設計並輸出完整的資料模型文件（MODELS.md）。

## 輸出格式
生成 Markdown 文件，儲存至 `docs/MODELS.md`。

## 執行步驟
1. 讀取 PRD 與 ARCHITECTURE.md
2. 設計 SQLite 資料表
3. 輸出 MODELS.md，包含：資料表定義、欄位說明、關聯圖、初始資料規劃

---
name: architecture
description: 根據 PRD 生成系統架構設計文件，涵蓋前後端架構、API 設計、目錄結構與部署規劃。
---

# Skill: 系統架構設計生成器（Architecture Generator）

## 目標
根據 PRD 與技術選型，生成一份完整的系統架構設計文件（ARCHITECTURE.md）。

## 輸出格式
生成 Markdown 文件，儲存至 `docs/ARCHITECTURE.md`。

## 執行步驟
1. 讀取 `docs/prd/` 目錄下的 PRD 文件
2. 根據指定技術棧規劃架構
3. 輸出 ARCHITECTURE.md，包含：系統架構、API 設計、目錄結構、資料流程

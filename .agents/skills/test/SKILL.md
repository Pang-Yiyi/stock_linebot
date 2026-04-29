---
name: test
description: 根據實作的程式碼與 PRD 驗收標準，生成完整的手動測試清單。
---

# Skill: 測試驗證生成器（Test Generator）

## 目標
生成一份完整的手動測試清單，確保所有 P0 功能符合驗收標準。

## 輸出
- `docs/TEST_CHECKLIST.md`（手動測試清單）

## 執行步驟
1. 讀取 PRD 的驗收標準
2. 讀取實作程式碼確認 API 端點
3. 生成測試清單（功能、UI、API、邊界情況）

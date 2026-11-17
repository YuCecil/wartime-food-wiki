# 工作紀錄（log）

> 只往下加，不改舊的。格式見 AGENTS.md 第 7 節。查最近 5 筆：`grep "^## \[" wiki/log.md | tail -5`

## [2026-11-17] rule | 先訪談、後建檔：建立 W10 專案
- 依需求訪談（docs/需求訪談.md）重建專案：主規則改為 AGENTS.md（CLAUDE.md 只寫 @AGENTS.md），控制在 12,000 字元內
- 從上一版專案（W09「戰時餐桌」網站）移入：30 份資料卡、9 個故事、7 個名詞、overview、raw/ 原文與全文筆記、故事插圖
- 不移入：網站程式、時間軸／地圖／關係網資料、吉祥物與標誌、設計工具；圖表數字改寫成主題頁裡的 Markdown 表格
- 連結從 [[id]] 改成相對路徑 Markdown 連結（GitHub 與 Obsidian 都點得開）
- 新的健檢把引文上限從舊程式的 60 字改回規則寫的 50 字，並改成英文以單字計
- 新增簡報 graph：.agents/workflows/story-slides.md、tools/slides.py、templates/deck.html

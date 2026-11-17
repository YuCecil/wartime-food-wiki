---
description: 加入新資料：一次一篇，讀完、寫資料卡、整合進 wiki、檢查、記錄，才換下一篇。
argument: 檔名或網址（可省略＝處理 inbox/ 全部，但仍一篇一篇做）
---

# /ingest — 加入新資料（一次一篇）

目標：`$ARGUMENTS`（沒寫就處理 `inbox/` 裡的檔案，**一篇做完整套才換下一篇**）

1. **讀規則與現況**：AGENTS.md 第 2–5、8 節，`wiki/index.md`、`wiki/overview.md`。已經有資料卡的只補充、不新建。
2. **確認書目**：作者、年份、篇名、刊物卷期頁碼都要對過原文（不要相信檔名或搜尋結果的摘要）。查不到真實出處的資料不收。
3. **歸檔**：依 AGENTS.md 第 3 節取 id。PDF 放 `raw/papers/<id>.pdf` 並用 `pdftotext -layout` 轉成 `<id>.txt`；網頁存 `<id>.html` 與 `<id>.txt`，第一行寫網址與擷取日期。報紙放 `raw/newspapers/`，統計放 `raw/data/`。
4. **讀全文、寫全文筆記**：照 `templates/fulltext-notes.md` 寫 `raw/notes/<id>.md`，每條事實附頁碼，表格數字完整抄下。沒有全文就跳過，`depth` 照實填。
5. **寫資料卡**：照 `templates/source.md` 寫 `wiki/sources/<id>.md`。
6. **整合**（不能只寫資料卡）：新資訊併進相關主題頁「故事是這樣的」或「研究者怎麼看」，把 id 加進 `sources`，更新 `updated`；跟舊說法矛盾就兩說並列；能回答某故事「還不知道的事」的，把那條改掉；整體理解有變就改 `overview.md`；內容撐得起新故事（AGENTS.md 4.4 門檻）才開新主題頁。
7. **檢查**：`python3 tools/wiki.py index && python3 tools/wiki.py lint`，錯誤修到 0。
8. **記錄**：`wiki/log.md` 加一筆 `## [日期] ingest | 篇名（作者 年）`，寫新增、更新、發現。
9. **回報**：白話說讀到什麼、改了哪些頁、發現哪些矛盾或缺口。然後才處理下一篇。

處理完的檔案從 `inbox/` 移到 `raw/`，`inbox/` 保持只有 `.gitkeep`。

# 戰時餐桌：1937–1949 臺灣飲食 LLM Wiki

一個用 LLM 維護的研究筆記庫（Karpathy 提出的 LLM Wiki 做法），主題是戰爭期間到戰後初期（1937–1949）臺灣人吃什麼、怎麼吃：米穀配給、代用食、黑市、戰後米荒……；再用這個 wiki 為每個故事做一份給初學者自學的 HTML 簡報。

> **先看這裡**
> 1. 簡報：<https://yucecil.github.io/wartime-food-wiki/>
> 2. Wiki 目錄：[wiki/index.md](wiki/index.md)
> 3. 流程圖：[docs/流程圖.md](docs/流程圖.md)
>
> 其他資料夾是做簡報的過程檔（每份簡報的大綱、逐頁稿、審查紀錄在 `slides/<故事>/`），不看也沒關係。

- **看簡報**：<https://yucecil.github.io/wartime-food-wiki/>
  - [一天能吃多少米？米穀配給](https://yucecil.github.io/wartime-food-wiki/slides/t-rice-ration/deck.html)
  - [米不夠，吃什麼？代用食](https://yucecil.github.io/wartime-food-wiki/slides/t-substitute-food/deck.html)
  - [戰爭結束了，米卻更少了：戰後米荒](https://yucecil.github.io/wartime-food-wiki/slides/t-postwar-famine/deck.html)
- **看 wiki**：[wiki/index.md](wiki/index.md)（故事、人物與機構、資料卡的總目錄）
- **流程圖**：[docs/流程圖.md](docs/流程圖.md)
- **需求訪談**：[docs/需求訪談.md](docs/需求訪談.md)

## 三層結構

| 層 | 位置 | 內容 |
|---|---|---|
| 原始資料 | `raw/`（不上傳） | 論文 PDF、文字檔、全文筆記 |
| wiki | `wiki/` | 資料卡（sources）、故事（topics）、人物與機構（entities）、`log.md` |
| 成品 | `slides/<故事id>/` | 每份簡報的中間檔與 `deck.html` |

## 怎麼用（給 AI 代理）

規則在 [AGENTS.md](AGENTS.md)。

- 加一篇資料：`/ingest`（`.agents/workflows/ingest.md`）
- 做一份簡報：`/story-slides <故事id>`（`.agents/workflows/story-slides.md`）
- 健檢：`python3 tools/wiki.py lint`；更新目錄：`python3 tools/wiki.py index`
- 渲染檢查需要 playwright：`.venv/bin/python tools/slides.py render <故事id>`

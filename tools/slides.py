"""故事簡報 graph 的「程式檢查關卡」與「渲染」。流程說明見 .agents/workflows/story-slides.md。

每一關一個子指令，<id> 是故事的 id（例：t-rice-ration）。每次執行都記進 slides/<id>/runlog.jsonl。

  python3 tools/slides.py retrieve <id>    ① 檢索 wiki ＋ ② 覆蓋率關卡：列出可用資料，資料不夠就停
  python3 tools/slides.py cards <id>       ③ 證據卡關卡：原文要真的在資料裡、數字要在原文裡
  python3 tools/slides.py outline <id>     ④ 大綱關卡：頁數、學習目標、每頁有證據
  python3 tools/slides.py approve <id> <關卡> "<備註>"   記下使用者在人工關卡（style／outline／final）的確認
  python3 tools/slides.py script <id>      ⑤ 逐頁稿關卡：每句有出處、數字對得上證據卡、每頁字數
  python3 tools/slides.py review <id>      ⑥ 讀 AI 審查報告（review.md），列出要退回的頁
  python3 tools/slides.py build <id>       ⑦ 渲染：逐頁稿 → deck.html（程式做，不改任何字）
  python3 tools/slides.py render <id>      ⑧ 渲染檢查：桌機與手機每頁不溢出、圖片與連結都在（需要 .venv）
  python3 tools/slides.py report <id>      ⑨ 交件：把所有關卡紀錄整理成 report.md

結束碼：0＝通過；1＝沒通過，照輸出退回指定的節點；3＝停下來交給人。
"""
import datetime
import html
import json
import re
import sys
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
from wiki import read_page, section  # noqa: E402

GITHUB = "https://github.com/YuCecil/wartime-food-wiki/blob/main/"   # 資料卡的公開網址前綴
PAGES_MIN, PAGES_MAX = 8, 10        # 訪談第 10 題：8–10 頁
MAX_CHARS = 170                     # 每頁字數上限（不含出處）；自學用，比上台簡報多，但手機要放得下
MAX_ROUNDS = 3                      # 同一關最多重跑 3 輪，再不過就停下交給人
MIN_SOURCES = 3                     # 覆蓋率：至少 3 份讀過全文或部分的資料
CONTENT = {"text", "number", "compare", "quote", "image", "summary"}
LAYOUTS = CONTENT | {"cover", "goals", "check"}
CITE = re.compile(r"\[(s-[a-z0-9\-]+)#(E\d+)\]")
NUM = re.compile(r"\d[\d,]*(?:\.\d+)?")
CAT = {"主食": "rice", "副食": "meat", "制度": "rule", "市場": "market", "生活": "life", "戰後": "post"}


# ---------------- 共用 ----------------
def d(tid):
    return ROOT / "slides" / tid


def topic(tid):
    p = ROOT / "wiki/topics" / f"{tid}.md"
    if not p.exists():
        sys.exit(f"找不到故事 {tid}（wiki/topics/{tid}.md）")
    return read_page(p)


def source_meta(sid):
    p = ROOT / "wiki/sources" / f"{sid}.md"
    return read_page(p)[0] if p.exists() else None


def source_texts(sid):
    """這份資料在本機能讀到的文字（原文與全文筆記）。raw/ 不上傳，所以只有本機有。"""
    files = []
    for sub in ("papers", "notes", "newspapers"):
        for ext in (".txt", ".md"):
            f = ROOT / "raw" / sub / f"{sid}{ext}"
            if f.exists():
                files.append(f)
        files += sorted((ROOT / "raw" / sub).glob(f"{sid}-p*.txt"))
    return files


def norm(s):
    s = unicodedata.normalize("NFKC", s)
    return re.sub(r"[\s「」『』“”\"'‘’]", "", s)


def nums(s):
    return {n.replace(",", "").rstrip(".") for n in NUM.findall(s)}


def rounds(tid, gate):
    f = d(tid) / "runlog.jsonl"
    if not f.exists():
        return 0
    return sum(1 for l in f.read_text(encoding="utf-8").splitlines() if l and json.loads(l)["gate"] == gate)


def log(tid, gate, ok, problems, note=""):
    d(tid).mkdir(parents=True, exist_ok=True)
    n = rounds(tid, gate) + 1
    rec = {"time": datetime.datetime.now().isoformat(timespec="seconds"), "gate": gate, "round": n,
           "result": "通過" if ok else "退回", "problems": problems, "note": note}
    with open(d(tid) / "runlog.jsonl", "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    return n


def finish(tid, gate, problems, back, note=""):
    ok = not problems
    n = log(tid, gate, ok, problems, note)
    for p in problems:
        print("✗", p)
    if ok:
        print(f"✓ {gate}：第 {n} 輪通過")
        return 0
    if n >= MAX_ROUNDS:
        print(f"■ {gate}：已經 {n} 輪沒過，停下來交給使用者（硬上限 {MAX_ROUNDS} 輪）")
        return 3
    print(f"→ {gate}：第 {n} 輪沒過，{len(problems)} 個問題。退回：{back}")
    return 1


# ---------------- ①② 檢索與覆蓋率 ----------------
def cmd_retrieve(tid):
    meta, body = topic(tid)
    rows, usable = [], []
    for sid in meta.get("sources", []):
        m = source_meta(sid) or {}
        files = source_texts(sid)
        ok = m.get("depth") in ("全文", "部分") and files
        if ok:
            usable.append(sid)
        rows.append(f"| {sid} | {m.get('author')} {m.get('year')} | {m.get('depth')} | "
                    f"{'、'.join(f.relative_to(ROOT).as_posix() for f in files) or '（本機沒有文字檔）'} | {'可用' if ok else '只能當背景'} |")
    gaps = section(body, "還不知道的事").strip()
    out = [f"# 檢索結果：{meta['title']}", "",
           f"故事頁：wiki/topics/{tid}.md　產生時間：{datetime.date.today()}", "",
           "| 資料 | 作者 年 | 讀到哪裡 | 本機文字檔 | 能不能做證據卡 |", "|---|---|---|---|---|", *rows, "",
           f"可做證據卡的資料：{len(usable)} 份（門檻 {MIN_SOURCES} 份）", "",
           "## 故事頁列出的資料缺口", "", gaps or "（無）", ""]
    d(tid).mkdir(parents=True, exist_ok=True)
    (d(tid) / "sources.md").write_text("\n".join(out), encoding="utf-8")
    problems = [] if len(usable) >= MIN_SOURCES else [
        f"只有 {len(usable)} 份資料讀過全文或部分（要 {MIN_SOURCES} 份）：先用 ingest 補資料再回來"]
    print(f"已寫 slides/{tid}/sources.md；可用資料：{', '.join(usable) or '無'}")
    code = finish(tid, "覆蓋率", problems, "停下：補資料（ingest）")
    return 3 if problems else code


# ---------------- ③ 證據卡 ----------------
def parse_cards(tid):
    cards = {}
    for f in sorted((d(tid) / "cards").glob("s-*.md")):
        sid = f.stem
        for m in re.finditer(r"^## (E\d+)\s*\n(.*?)(?=^## |\Z)", f.read_text(encoding="utf-8"), re.M | re.S):
            fields = dict(re.findall(r"^(事實|頁|原文|用途)：\s*(.+)$", m.group(2), re.M))
            cards[f"{sid}#{m.group(1)}"] = fields
    return cards


def cmd_cards(tid):
    meta, _ = topic(tid)
    problems = []
    folder = d(tid) / "cards"
    files = sorted(folder.glob("s-*.md")) if folder.exists() else []
    if not files:
        problems.append("cards/ 裡沒有證據卡")
    cards = parse_cards(tid)
    for key, f in cards.items():
        sid = key.split("#")[0]
        if sid not in meta.get("sources", []):
            problems.append(f"{key}：這份資料不在故事頁的 sources 裡（證據卡只能用故事頁列的資料）")
        for k in ("事實", "頁", "原文"):
            if not f.get(k):
                problems.append(f"{key}：缺少「{k}」")
        quote = f.get("原文", "").strip().strip("「」")
        if not quote:
            continue
        text = norm("".join(p.read_text(encoding="utf-8", errors="ignore") for p in source_texts(sid)))
        for frag in [x for x in re.split(r"…+|⋯+|\.\.\.+", quote) if norm(x)]:
            if norm(frag) not in text:
                problems.append(f"{key}：原文「{frag[:20]}…」在 raw/ 的資料裡找不到（抄錯或是自己改寫了）")
                break
        missing = nums(f.get("事實", "")) - nums(quote)
        if missing:
            problems.append(f"{key}：事實裡的數字 {sorted(missing)} 原文裡沒有（換算或抄錯？）")
        n = len(re.findall(r"[぀-ヿ㐀-鿿]", quote)) + len(re.findall(r"[A-Za-z]+", quote))
        if n > 50:
            problems.append(f"{key}：原文超過 50 字（{n} 字）")
    print(f"證據卡 {len(files)} 份、證據 {len(cards)} 條")
    return finish(tid, "證據卡", problems, "③ 證據卡：只重抽有問題的那幾條")


# ---------------- ④ 大綱 ----------------
def parse_outline(tid):
    f = d(tid) / "outline.md"
    if not f.exists():
        return None
    t = f.read_text(encoding="utf-8")
    goals = re.findall(r"^\d+\.\s+(.+)$", section(t, "學習目標"), re.M)
    pages = []
    for line in section(t, "頁面").splitlines():
        m = re.match(r"^(\d+)\.\s*(\w+)\s*\|\s*(.+?)\s*\|\s*目標：\s*([\d,、\s—-]*)\s*\|\s*證據：\s*(.*)$", line.strip())
        if m:
            pages.append({"n": int(m.group(1)), "layout": m.group(2), "title": m.group(3),
                          "goals": re.findall(r"\d", m.group(4)), "cites": re.findall(r"s-[a-z0-9\-]+#E\d+", m.group(5))})
        elif re.match(r"^\d+\.", line.strip()):
            pages.append({"n": 0, "bad": line.strip()})
    return goals, pages


def cmd_outline(tid):
    problems = []
    parsed = parse_outline(tid)
    if not parsed:
        return finish(tid, "大綱", ["沒有 outline.md"], "④ 大綱")
    goals, pages = parsed
    cards = parse_cards(tid)
    if len(goals) != 3:
        problems.append(f"學習目標要 3 個（現在 {len(goals)} 個）")
    if not PAGES_MIN <= len(pages) <= PAGES_MAX:
        problems.append(f"頁數要 {PAGES_MIN}–{PAGES_MAX} 頁（現在 {len(pages)} 頁）")
    for p in pages:
        if "bad" in p:
            problems.append(f"這行格式看不懂：{p['bad'][:30]}")
            continue
        if p["layout"] not in LAYOUTS:
            problems.append(f"第 {p['n']} 頁：版型 {p['layout']} 不存在（可用：{', '.join(sorted(LAYOUTS))}）")
        if p["layout"] in CONTENT and p["layout"] != "summary" and not p["cites"]:
            problems.append(f"第 {p['n']} 頁：內容頁沒有指定證據卡")
        for c in p["cites"]:
            if c not in cards:
                problems.append(f"第 {p['n']} 頁：證據 {c} 不存在")
    good = [p for p in pages if "bad" not in p]
    if good:
        if good[0]["layout"] != "cover":
            problems.append("第 1 頁要是 cover（封面）")
        if len(good) > 1 and good[1]["layout"] != "goals":
            problems.append("第 2 頁要是 goals（學習目標）")
        if good[-1]["layout"] != "check":
            problems.append("最後一頁要是 check（自我檢查）")
        for i in range(1, len(goals) + 1):
            if not any(str(i) in p["goals"] for p in good if p["layout"] in CONTENT):
                problems.append(f"學習目標 {i} 沒有任何內容頁在教")
    used = {c.split("#")[0] for p in good for c in p["cites"]}
    unused = sorted({k.split("#")[0] for k in cards} - used)
    if unused:
        print("△ 這些資料抽了證據卡但大綱沒用到：", ", ".join(unused))
    return finish(tid, "大綱", problems, "④ 大綱（缺證據就退回 ③，缺資料就退回 ① 補檢索）")


def cmd_approve(tid, gate, note):
    gate = {"style": "人工：風格樣板", "outline": "人工：大綱", "final": "人工：交件"}.get(gate)
    if not gate:
        sys.exit("關卡只能是 style、outline、final")
    log(tid, gate, True, [], note)
    print(f"已記錄：{gate} 通過（{note}）")


# ---------------- ⑤ 逐頁稿 ----------------
def parse_script(tid):
    f = d(tid) / "script.md"
    if not f.exists():
        return None
    pages = []
    for m in re.finditer(r"^## (\d+) \| (\w+) \| (.+?)\s*\n(.*?)(?=^## |\Z)", f.read_text(encoding="utf-8"), re.M | re.S):
        lines = [l.rstrip() for l in m.group(4).strip().splitlines() if l.strip() and not l.startswith("<!--")]
        pages.append({"n": int(m.group(1)), "layout": m.group(2), "title": m.group(3).strip(), "lines": lines})
    return pages


def plain(s):
    return re.sub(r"^(大數字|說明|甲說|乙說|圖|答案|副標|- |\d+\. )：?", "", CITE.sub("", s)).strip()


def cjk_len(s):
    return len(re.findall(r"[぀-ヿ㐀-鿿A-Za-z0-9]", s))


def cmd_script(tid):
    problems = []
    pages = parse_script(tid)
    if not pages:
        return finish(tid, "逐頁稿", ["沒有 script.md，或標題格式不是「## 頁碼 | 版型 | 標題」"], "⑤ 逐頁稿")
    cards = parse_cards(tid)
    _, opages = parse_outline(tid) or ([], [])
    if len(pages) != len([p for p in opages if "bad" not in p]):
        problems.append(f"逐頁稿 {len(pages)} 頁，跟確認過的大綱頁數不一樣")
    for p in pages:
        w = f"第 {p['n']} 頁"
        if p["layout"] not in LAYOUTS:
            problems.append(f"{w}：版型 {p['layout']} 不存在")
        n = cjk_len(p["title"]) + sum(cjk_len(plain(l)) for l in p["lines"])
        if n > MAX_CHARS:
            problems.append(f"{w}：{n} 字，超過 {MAX_CHARS} 字（手機會放不下）")
        if p["layout"] == "number" and not any(l.startswith("大數字：") for l in p["lines"]):
            problems.append(f"{w}：number 版型要有「大數字：」一行")
        if p["layout"] == "compare":
            a = [l for l in p["lines"] if l.startswith("甲說：")]
            b = [l for l in p["lines"] if l.startswith("乙說：")]
            if not (a and b):
                problems.append(f"{w}：compare 版型要有「甲說：」和「乙說：」")
            elif {c[0] for c in CITE.findall(a[0])} == {c[0] for c in CITE.findall(b[0])}:
                problems.append(f"{w}：甲說、乙說要來自不同資料")
        if p["layout"] == "check":
            qs = [l for l in p["lines"] if re.match(r"^\d+\.", l)]
            ans = [l for l in p["lines"] if l.startswith("答案：")]
            if len(qs) != 3 or len(ans) != 3:
                problems.append(f"{w}：自我檢查要 3 題，每題下一行寫「答案：…（第 x 頁）」")
        if p["layout"] in ("cover", "goals", "check"):
            continue
        for l in p["lines"]:
            if l.startswith(("圖：", "（推論）")):
                continue
            cites = CITE.findall(l)
            if not cites:
                problems.append(f"{w}：這句沒有出處：{plain(l)[:24]}…")
                continue
            facts = ""
            for sid, e in cites:
                key = f"{sid}#{e}"
                if key not in cards:
                    problems.append(f"{w}：引用的證據 {key} 不存在")
                else:
                    facts += cards[key].get("事實", "") + cards[key].get("原文", "")
            extra = nums(plain(l)) - nums(facts)
            if extra:
                problems.append(f"{w}：數字 {sorted(extra)} 在引用的證據卡裡找不到：{plain(l)[:24]}…")
    return finish(tid, "逐頁稿", problems, "⑤ 逐頁稿：只修列出的那幾頁（證據卡本身錯就退回 ③）")


# ---------------- ⑥ AI 審查結果 ----------------
def cmd_review(tid):
    f = d(tid) / "review.md"
    if not f.exists():
        return finish(tid, "AI 審查", ["沒有 review.md：先請新的 AI 審查（只給逐頁稿與證據卡）"], "⑥ AI 審查")
    t = f.read_text(encoding="utf-8")
    fails = re.findall(r"^- 第 (\d+) 頁：不通過｜(.+?)｜(.+)$", t, re.M)
    passes = re.findall(r"^- 第 (\d+) 頁：通過", t, re.M)
    pages = parse_script(tid) or []
    problems = [f"第 {n} 頁（{kind}）：{why}" for n, kind, why in fails]
    if len(fails) + len(passes) < len(pages):
        problems.append(f"審查報告只看了 {len(fails) + len(passes)} 頁，少於 {len(pages)} 頁")
    back = "依問題類型：講錯／過度推論→⑤ 只修那頁；證據卡錯→③ 重抽那篇；缺重點→④ 大綱"
    return finish(tid, "AI 審查", problems, back)


# ---------------- ⑦ 渲染 ----------------
def cite_html(sid, e, cards):
    m = source_meta(sid) or {}
    page = cards.get(f"{sid}#{e}", {}).get("頁", "")
    label = f"{m.get('author', sid)} {m.get('year', '')}" + (f"，頁 {page}" if page and page not in ("無", "—") else "")
    return f'<a class="cite" href="{GITHUB}wiki/sources/{sid}.md" target="_blank" rel="noopener">{html.escape(label)}</a>'


def render_line(l, cards):
    cites = CITE.findall(l)
    text = html.escape(plain(l))
    text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
    if cites:
        text += ' <span class="cites">（' + "；".join(cite_html(s, e, cards) for s, e in cites) + "）</span>"
    return text


def cmd_build(tid):
    meta, _ = topic(tid)
    pages = parse_script(tid)
    if not pages:
        sys.exit("沒有 script.md")
    cards = parse_cards(tid)
    cat = CAT.get(meta.get("category"), "rice")
    img = meta.get("image")
    secs = []
    for p in pages:
        L = p["layout"]
        title = html.escape(p["title"])
        lines = p["lines"]
        get = lambda k: [l for l in lines if l.startswith(k)]
        rest = [l for l in lines if not l.startswith(("大數字：", "甲說：", "乙說：", "圖：", "副標：", "答案："))]
        inner = ""
        if L == "cover":
            sub = html.escape(plain(get("副標：")[0])) if get("副標：") else ""
            pic = f'<img class="cover-img" src="../../assets/img/{img}" alt="{html.escape(str(meta.get("imageAlt", "")))}">' if img else ""
            inner = (f'<div class="cover"><div class="ticket"><span class="stub">{meta.get("category", "")[:1]}</span>'
                     f'<div><p class="series">戰時餐桌・故事簡報</p><h1>{title}</h1><p class="sub">{sub}</p>'
                     f'<p class="meta">臺灣 {meta["period"][0]}–{meta["period"][-1]}　·　共 {len(pages)} 頁　·　用 ← → 或滑動翻頁</p></div></div>{pic}</div>')
        elif L == "goals":
            items = "".join(f"<li>{html.escape(plain(l))}</li>" for l in lines if re.match(r"^(- |\d+\.)", l))
            other = "".join(f"<p>{html.escape(plain(l))}</p>" for l in lines if not re.match(r"^(- |\d+\.)", l))
            inner = f"<h2>{title}</h2>{other}<ol class='goals'>{items}</ol>"
        elif L == "check":
            qa, q = [], None
            for l in lines:
                if re.match(r"^\d+\.", l):
                    q = l
                elif l.startswith("答案：") and q:
                    qa.append(f"<li><p>{html.escape(plain(q))}</p><details><summary>看答案</summary><p>{html.escape(plain(l))}</p></details></li>")
            inner = f"<h2>{title}</h2><ol class='qa'>{''.join(qa)}</ol>"
        else:
            body = ""
            if L == "number" and get("大數字："):
                big = get("大數字：")[0]
                bm = re.match(r"^大數字：\s*(.+?)(?:｜(.+?))?\s*$", CITE.sub("", big))
                body += (f'<p class="big"><span class="stamp-num">{html.escape(bm.group(1))}</span>'
                         f'<span class="big-label">{html.escape(bm.group(2) or "")}</span></p>')
            if L == "compare":
                body += ('<div class="compare">' +
                         "".join(f'<div class="side"><p class="who">{w}</p><p>{render_line(x, cards)}</p></div>'
                                 for w, x in (("一種說法", get("甲說：")[0]), ("另一種說法", get("乙說：")[0]))) + "</div>")
            body += "".join(f"<p>{render_line(l, cards)}</p>" for l in rest)
            if L == "image" and get("圖："):
                fn, _, cap = plain(get("圖：")[0]).partition("｜")
                body = (f'<figure><img src="../../assets/img/{html.escape(fn.strip())}" alt="{html.escape(cap.strip())}">'
                        f"<figcaption>{html.escape(cap.strip())}</figcaption></figure>") + body
            if L == "quote":
                body = f"<blockquote>{body}</blockquote>"
            inner = f"<h2>{title}</h2>{body}"
        secs.append(f'<section class="slide layout-{L}" id="p{p["n"]}" aria-label="第 {p["n"]} 頁"><div class="inner">{inner}</div></section>')
    tpl = (ROOT / "templates/deck.html").read_text(encoding="utf-8")
    out = (tpl.replace("{{TITLE}}", html.escape(meta["title"])).replace("{{CAT}}", cat)
           .replace("{{SLIDES}}", "\n".join(secs))
           .replace("{{WIKI}}", f"{GITHUB}wiki/topics/{tid}.md")
           .replace("{{TOTAL}}", str(len(pages))))
    (d(tid) / "deck.html").write_text(out, encoding="utf-8")
    print(f"已產生 slides/{tid}/deck.html（{len(pages)} 頁）")


# ---------------- ⑧ 渲染檢查 ----------------
def cmd_render(tid):
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        sys.exit("需要 playwright：用專案的 .venv 執行（.venv/bin/python tools/slides.py render <id>）")
    deck = d(tid) / "deck.html"
    shots = d(tid) / "shots"
    shots.mkdir(exist_ok=True)
    problems = []
    with sync_playwright() as pw:
        b = pw.chromium.launch(channel="chrome")
        for name, vp in (("桌機", {"width": 1280, "height": 800}), ("手機", {"width": 375, "height": 740})):
            pg = b.new_page(viewport=vp)
            errs = []
            pg.on("console", lambda m: errs.append(m.text) if m.type == "error" else None)
            pg.on("pageerror", lambda e: errs.append(str(e)))
            pg.goto(deck.as_uri())
            pg.wait_for_timeout(800)
            n = pg.evaluate("document.querySelectorAll('.slide').length")
            for i in range(1, n + 1):
                pg.evaluate(f"go({i})")
                pg.wait_for_timeout(150)
                r = pg.evaluate("""() => { const s=document.querySelector('.slide.active .inner');
                  const imgs=[...document.querySelectorAll('.slide.active img')];
                  return {over: s.scrollHeight - s.clientHeight, wide: document.documentElement.scrollWidth - innerWidth,
                          broken: imgs.filter(i => !i.complete || i.naturalWidth === 0).map(i => i.getAttribute('src'))}; }""")
                if r["over"] > 2:
                    problems.append(f"{name} 第 {i} 頁：內容超出畫面 {r['over']}px")
                if r["wide"] > 2:
                    problems.append(f"{name} 第 {i} 頁：出現橫向捲動 {r['wide']}px")
                for s in r["broken"]:
                    problems.append(f"{name} 第 {i} 頁：圖片載入失敗 {s}")
                pg.screenshot(path=str(shots / f"{'desktop' if name == '桌機' else 'mobile'}-{i:02d}.png"))
            problems += [f"{name}：主控台錯誤 {e}" for e in errs]
            pg.close()
        b.close()
    print(f"截圖存在 slides/{tid}/shots/")
    return finish(tid, "渲染檢查", problems, "⑤ 逐頁稿：把溢出的那頁縮短（不是改版面硬塞）")


# ---------------- ⑨ 交件報告 ----------------
def cmd_report(tid):
    meta, _ = topic(tid)
    f = d(tid) / "runlog.jsonl"
    recs = [json.loads(l) for l in f.read_text(encoding="utf-8").splitlines() if l] if f.exists() else []
    order = ["覆蓋率", "證據卡", "大綱", "人工：風格樣板", "人工：大綱", "逐頁稿", "AI 審查", "渲染檢查", "人工：交件"]
    out = [f"# 檢查報告：{meta['title']}", "", "> 由 `python3 tools/slides.py report` 從 runlog.jsonl 自動產生。", "",
           "## 各關卡結果", "", "| 關卡 | 跑了幾輪 | 最後結果 |", "|---|---|---|"]
    for g in order + sorted({r["gate"] for r in recs} - set(order)):
        rs = [r for r in recs if r["gate"] == g]
        if rs:
            out.append(f"| {g} | {len(rs)} | {rs[-1]['result']} |")
    out += ["", "## 每一輪的紀錄", ""]
    for r in recs:
        out.append(f"- {r['time']}　**{r['gate']}** 第 {r['round']} 輪：{r['result']}" + (f"（{r['note']}）" if r["note"] else ""))
        out += [f"  - {p}" for p in r["problems"]]
    cards = parse_cards(tid)
    pages = parse_script(tid) or []
    used = {f"{s}#{e}" for p in pages for l in p["lines"] for s, e in CITE.findall(l)}
    out += ["", "## Wiki 與簡報的對應", "", "| 頁 | 標題 | 用到的資料 |", "|---|---|---|"]
    for p in pages:
        srcs = sorted({s for l in p["lines"] for s, _ in CITE.findall(l)})
        out.append(f"| {p['n']} | {p['title']} | {', '.join(srcs) or '—'} |")
    out += ["", f"證據卡共 {len(cards)} 條，簡報用了 {len(used & set(cards))} 條。", ""]
    (d(tid) / "report.md").write_text("\n".join(out), encoding="utf-8")
    print(f"已寫 slides/{tid}/report.md")


if __name__ == "__main__":
    a = sys.argv[1:]
    cmds = {"retrieve": cmd_retrieve, "cards": cmd_cards, "outline": cmd_outline, "script": cmd_script,
            "review": cmd_review, "build": cmd_build, "render": cmd_render, "report": cmd_report}
    if len(a) == 2 and a[0] in cmds:
        sys.exit(cmds[a[0]](a[1]) or 0)
    if len(a) == 4 and a[0] == "approve":
        cmd_approve(a[1], a[2], a[3])
        sys.exit(0)
    print(__doc__)
    sys.exit(2)

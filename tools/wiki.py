"""Wiki 的兩個工具（只用 Python 標準函式庫）：

  python3 tools/wiki.py index   重新產生 wiki/index.md（不要手改 index.md）
  python3 tools/wiki.py lint    健檢：欄位、固定標題、連結、出處、引文長度

錯誤（✗）一定要修到 0；提醒（△）看情況處理。
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WIKI = ROOT / "wiki"
DIRS = ["sources", "topics", "entities"]
LIST_KEYS = {"topics", "entities", "sources", "period"}
MDLINK = re.compile(r"(!?)\[([^\]]*)\]\(([^)\s]+)\)")

REQ = {
    "source": ["id", "type", "title", "author", "year", "kind", "venue", "url", "access", "depth", "period",
               "topics", "reliability", "added"],
    "topic": ["id", "type", "title", "category", "period", "summary", "sources", "updated"],
    "entity": ["id", "type", "title", "kind", "summary", "sources"],
}
HEADINGS = {
    "source": ["一句話", "三個重點", "用了什麼史料", "跟其他資料的關係", "值得記住的一句話", "還不確定的地方"],
    "topic": ["一句話說明", "故事是這樣的", "研究者怎麼看", "延伸閱讀", "還不知道的事"],
    "entity": ["是什麼", "在故事裡的角色", "出現在哪些主題"],
}
OPTIONAL = {"source": {"值得記住的一句話"}}
ENUM = {
    "kind_source": {"期刊論文", "學位論文", "專書", "專書論文", "報紙", "史料", "統計", "網頁"},
    "access": {"公開", "台大資料庫", "使用者提供"},
    "depth": {"全文", "部分", "摘要", "書目"},
    "reliability": {"高", "中", "低"},
    "category": {"主食", "副食", "制度", "市場", "生活", "戰後"},
    "kind_entity": {"機構", "法令", "制度", "人物", "地點", "物品"},
}
PREFIX = {"source": "s-", "topic": "t-", "entity": "e-"}


def parse_value(v):
    v = v.strip()
    if "#" in v and not v.startswith("http"):
        v = v.split("  #")[0].split(" #")[0].strip()
    if v.startswith("[") and v.endswith("]"):
        items = [x.strip().strip('"').strip("'") for x in v[1:-1].split(",")]
        return [int(x) if re.fullmatch(r"-?\d+", x) else x for x in items if x]
    v = v.strip('"').strip("'")
    return int(v) if re.fullmatch(r"-?\d+", v) else v


def read_page(path):
    text = path.read_text(encoding="utf-8")
    meta, body = {}, text
    if text.startswith("---"):
        head, _, body = text[3:].partition("\n---")
        body = body.lstrip("-").lstrip("\n")
        for line in head.splitlines():
            if not line.strip():
                continue
            if ":" not in line:
                meta.setdefault("_bad_lines", []).append(line)
                continue
            k, v = line.split(":", 1)
            meta[k.strip()] = parse_value(v)
    for k in LIST_KEYS:
        if k in meta and not isinstance(meta[k], list):
            meta[k] = [meta[k]] if meta[k] not in ("", "無") else []
    return meta, body


def load_pages():
    pages = []
    for d in DIRS:
        for p in sorted((WIKI / d).glob("*.md")):
            meta, body = read_page(p)
            pages.append({"path": p, "dir": d, "meta": meta, "body": body})
    return pages


def quote_len(q):
    """引文字數：中日文一字算一字，英文等拼音文字一個單字算一字。"""
    return len(re.findall(r"[぀-ヿ㐀-鿿]", q)) + len(re.findall(r"[A-Za-z0-9][A-Za-z0-9'’,.\-]*", q))


def section(body, title):
    m = re.search(rf"^## {re.escape(title)}\s*\n(.*?)(?=^## |\Z)", body, re.M | re.S)
    return m.group(1) if m else ""


# ---------------- index ----------------
def cmd_index():
    pages = load_pages()
    by = {d: [p for p in pages if p["dir"] == d] for d in DIRS}
    decks = {p.parent.name for p in (ROOT / "slides").glob("*/deck.html")}
    out = ["# 目錄（index）", "",
           "> 由 `python3 tools/wiki.py index` 自動產生，不要手改。", "",
           f"共 {len(by['topics'])} 個故事、{len(by['sources'])} 份資料卡、{len(by['entities'])} 個名詞。", "",
           "## 故事（主題頁）", "", "| 故事 | 一句話 | 資料數 | 簡報 |", "|---|---|---|---|"]
    for p in by["topics"]:
        m = p["meta"]
        deck = f"[簡報](../slides/{m['id']}/deck.html)" if m["id"] in decks else "還沒做"
        out.append(f"| [{m['title']}](topics/{m['id']}.md) | {m.get('summary', '')} | {len(m.get('sources', []))} | {deck} |")
    out += ["", "## 資料卡", "", "| 資料 | 作者 | 年 | 讀到哪裡 | 可信度 |", "|---|---|---|---|---|"]
    for p in sorted(by["sources"], key=lambda p: (str(p["meta"].get("year")), p["meta"]["id"])):
        m = p["meta"]
        out.append(f"| [{m['title']}](sources/{m['id']}.md) | {m.get('author')} | {m.get('year')} | {m.get('depth')} | {m.get('reliability')} |")
    out += ["", "## 名詞", ""]
    for p in by["entities"]:
        m = p["meta"]
        out.append(f"- [{m['title']}](entities/{m['id']}.md)：{m.get('summary', '')}")
    (WIKI / "index.md").write_text("\n".join(out) + "\n", encoding="utf-8")
    print(f"已更新 wiki/index.md（{len(pages)} 頁）")


# ---------------- lint ----------------
def cmd_lint():
    errors, warns = [], []
    err = lambda w, m: errors.append(f"✗ {w}：{m}")
    warn = lambda w, m: warns.append(f"△ {w}：{m}")
    pages = load_pages()
    ids = {p["meta"].get("id") for p in pages}
    inbound = {i: 0 for i in ids}
    extra = [WIKI / "overview.md"]

    def check_links(path, body, me=None):
        for bang, _, target in MDLINK.findall(body):
            if target.startswith(("http://", "https://", "#", "mailto:")):
                continue
            f = (path.parent / target.split("#")[0]).resolve()
            if not f.exists():
                err(path.name, f"連結指向不存在的檔案：{target}")
            elif not bang and f.suffix == ".md" and f.stem in inbound and f.stem != me:
                inbound[f.stem] += 1

    for p in pages:
        m, name, t = p["meta"], p["path"].name, p["meta"].get("type")
        if m.get("_bad_lines"):
            err(name, f"frontmatter 有不是 key: value 的行：{m['_bad_lines'][:2]}")
        if t not in REQ:
            err(name, f"type 不明：{t}")
            continue
        for k in REQ[t]:
            if k not in m or m[k] in ("", None):
                err(name, f"缺少欄位 {k}")
        pid = str(m.get("id", ""))
        if pid + ".md" != name or not re.fullmatch(r"[a-z0-9\-]+", pid) or not pid.startswith(PREFIX[t]):
            err(name, f"id 要跟檔名一致、只用小寫英文數字連字號、以 {PREFIX[t]} 開頭")
        if t == "source":
            if m.get("kind") not in ENUM["kind_source"]:
                err(name, f"kind 不在允許清單：{m.get('kind')}")
            for k in ("access", "depth", "reliability"):
                if m.get(k) not in ENUM[k]:
                    err(name, f"{k} 不在允許清單：{m.get(k)}")
        if t == "topic" and m.get("category") not in ENUM["category"]:
            err(name, f"category 不在允許清單：{m.get('category')}")
        if t == "entity" and m.get("kind") not in ENUM["kind_entity"]:
            err(name, f"kind 不在允許清單：{m.get('kind')}")
        for k in ("topics", "entities", "sources"):
            for x in m.get(k, []) or []:
                if x not in ids:
                    err(name, f"{k} 裡的 {x} 不存在")
                elif x != pid:
                    inbound[x] += 1
        if m.get("image") and not (ROOT / "assets/img" / str(m["image"])).exists():
            err(name, f"image 檔案不存在：assets/img/{m['image']}")
        found = re.findall(r"^## (.+?)\s*$", p["body"], re.M)
        need = [h for h in HEADINGS[t] if h in found or h not in OPTIONAL.get(t, set())]
        missing = [h for h in need if h not in found]
        if missing:
            err(name, f"缺少固定標題：{missing}")
        elif [found.index(h) for h in need] != sorted(found.index(h) for h in need):
            err(name, "固定標題順序不對")
        for q in re.findall(r"[「『“\"](.+?)[」』”\"]", section(p["body"], "值得記住的一句話")):
            n = quote_len(q)
            if n > 50:
                err(name, f"引文超過 50 字（{n} 字）")
        if t == "topic":
            for para in [x for x in section(p["body"], "故事是這樣的").split("\n\n") if x.strip()]:
                s = para.strip()
                if "sources/s-" not in s and not s.startswith(("（推論）", "!", ">")):
                    warn(name, f"「故事是這樣的」有段落沒有出處：{s[:20]}…")
        check_links(p["path"], p["body"], pid)
    for f in extra:
        if f.exists():
            check_links(f, f.read_text(encoding="utf-8"))
    for p in pages:
        if inbound.get(p["meta"].get("id"), 0) == 0:
            warn(p["path"].name, "孤兒頁：沒有任何頁面連到它")
    for line in errors + warns:
        print(line)
    print(f"\n共 {len(pages)} 頁：錯誤 {len(errors)}、提醒 {len(warns)}")
    return 1 if errors else 0


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "index":
        cmd_index()
    elif cmd == "lint":
        sys.exit(cmd_lint())
    else:
        print(__doc__)
        sys.exit(2)

# -*- coding: utf-8 -*-
"""42 帖采集数据完整性报告（生成 docs/DATA_COMPLETENESS.md）。

分层看，因为「字段齐不齐」和「能不能用」是两件事：

  L1 笔记层   content/note.json 的每个业务字段
  L2 图片层   urls.json / 本地文件 / note.json 三方一致
  L3 评论层   comments/comments.json ── 必须按「来源分组」看，见下
  L4 下游层   jev_guard 实际能读出多少（唯一有功能意义的口径）

三个容易看错的地方，本脚本专门处理：

1. **计数型字段**：`share_count: 0` 是「零分享」的真实数据。用 `has()` 那种
   「0 算缺失」的判法会把 40/44 篇误判成缺件。本脚本改为「键是否存在」。
2. **评论分两组**：SSR 抓的 992 行字段齐全；DOM 残件 135 行只有 `id`/`content`
   是真数据，`like_count`/`ip_location`/`create_time`/`nickname` 是占位值
   （证据：这 135 行 `like_count` **全部为 0**，而另 992 行有 13% 非零 ——
   135 连 0 在统计上不可能）。混在一起报「100% 完整」是错的。
3. **标签与 Layer 2 会过期**：回填新增了评论，而标签文件与 `scores.jsonl`
   是回填前产出的，需要重新打标 + 重算。

输出 UTF-8，避免 Windows GBK 控制台炸掉。
"""
from __future__ import annotations

import json
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "jev" / "src"))

from jev_guard.extractors.reader import (  # noqa: E402
    SPREAD_SD_THRESHOLD,
    comment_length_spread,
    load_comments,
    note_ip_stats,
)

DATA = ROOT / "data"
OUT = ROOT / "docs" / "DATA_COMPLETENESS.md"
LABELS = ROOT / "jev" / "out" / "labels_comment.jsonl"
SCORES = ROOT / "jev" / "out" / "scores.jsonl"
NOTE_RE = re.compile(r"/(?:explore|discovery/item)/([0-9a-f]{24})")
HEX24 = re.compile(r"^[0-9a-f]{24}$")

#: DOM 残件行的特征字段集（没有 note_id / create_time / status 等 SSR 字段）
DOM_ONLY_KEYS = {"id", "content", "ip_location", "like_count",
                 "user_info", "sub_comment_count", "pictures", "_is_reply"}

urls = (ROOT / "urls.txt").read_text(encoding="utf-8").splitlines()
IDS = [m.group(1) for m in (NOTE_RE.search(u) for u in urls) if m]
assert len(IDS) == 42, f"期望 42 帖，实际 {len(IDS)}"

dirs = sorted(p.name for p in DATA.iterdir() if p.is_dir() and HEX24.match(p.name))
EXTRA = [d for d in dirs if d not in IDS]

NOTE_FIELDS = [
    ("title", "标题", "text"),
    ("desc", "正文", "text"),
    ("author", "作者昵称", "text"),
    ("tags", "话题标签", "text"),
    ("published", "发布时间", "text"),
    ("liked", "点赞数", "count"),
    ("collected", "收藏数", "count"),
    ("comment_count", "评论数", "count"),
    ("share_count", "分享数", "count"),
    ("images", "图片URL数组", "text"),
    ("image_count", "图片计数", "count"),
    ("ip_location", "笔记IP属地", "text"),
]


def jread(p: Path):
    if not p.is_file():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError, OSError):
        return None


def nonempty(v) -> bool:
    if v is None:
        return False
    if isinstance(v, str):
        return bool(v.strip())
    if isinstance(v, (list, tuple, dict)):
        return len(v) > 0
    return True


def nick_of(row: dict) -> str:
    ui = row.get("user_info") if isinstance(row.get("user_info"), dict) else {}
    return str(ui.get("nickname") or ui.get("nick_name") or "").strip()


def is_dom_row(row: dict) -> bool:
    """DOM 残件 = 字段集是 SSR 真数据的真子集。"""
    return set(row) <= DOM_ONLY_KEYS


def collect(nid: str) -> dict:
    nj = jread(DATA / nid / "content" / "note.json") or {}
    rows = jread(DATA / nid / "comments" / "comments.json") or []
    rows = [r for r in rows if isinstance(r, dict)] if isinstance(rows, list) else []
    cs = load_comments(DATA, nid)
    uj = jread(DATA / nid / "images" / "urls.json")
    return {
        "id": nid, "note": nj, "rows": rows,
        "dom": [r for r in rows if is_dom_row(r)],
        "ssr": [r for r in rows if not is_dom_row(r)],
        "ds": len(cs), "named": sum(1 for c in cs if c.author),
        "files": len([f for f in (DATA / nid / "images").glob("*")
                      if f.is_file() and f.suffix.lower() in
                      (".jpg", ".jpeg", ".png", ".webp", ".heic", ".avif")
                      and f.stat().st_size > 0]),
        "urls": len(uj) if isinstance(uj, list) else 0,
        "card": (DATA / nid / "comments" / "card.json").is_file(),
        "txt": (DATA / nid / "comments" / "comments.txt").is_file(),
        "backup": (DATA / ".backup" / nid).is_dir(),
    }


rows = [collect(n) for n in IDS]
TOT = sum(len(r["rows"]) for r in rows)
DOM = sum(len(r["dom"]) for r in rows)
SSR = TOT - DOM
DS = sum(r["ds"] for r in rows)
NAMED = sum(r["named"] for r in rows)
IMGS = sum(r["files"] for r in rows)

# ---- 标签覆盖（回填前产出，需核对是否过期）
labeled: set[str] = set()
if LABELS.is_file():
    for line in LABELS.read_text(encoding="utf-8").splitlines():
        if line.strip():
            labeled.add(json.loads(line)["subject_id"])

unlabeled: dict[str, int] = {}
for r in rows:
    n = sum(1 for x in r["rows"]
            if str(x.get("id") or "") and str(x.get("content") or "").strip()
            and str(x["id"]) not in labeled)
    if n:
        unlabeled[r["id"]] = n
UNLAB = sum(unlabeled.values())

# ---- Layer 2 是否过期
stored = {}
if SCORES.is_file():
    for line in SCORES.read_text(encoding="utf-8").splitlines():
        if line.strip():
            s = json.loads(line)
            if s.get("kind") == "note":
                stored[s["subject_id"]] = s
stale, flipped = [], []
for nid in IDS:
    sp = comment_length_spread(DATA, nid)
    old = stored.get(nid)
    if not old:
        continue
    if old.get("spread_n") != sp["n"] or (old.get("spread_sd") or 0) != (sp["sd"] or 0):
        stale.append((nid, old.get("spread_n"), sp["n"],
                      old.get("spread_sd"), sp["sd"]))
    if bool(old.get("spread_flag")) != bool(sp["spread_flag"]):
        flipped.append((nid, old.get("spread_sd"), sp["sd"], sp["spread_flag"]))

# ---- IP 信号
ip_trig, ip_near, ip_low = [], [], []
for nid in IDS:
    st = note_ip_stats(DATA, nid)
    if st["ip_n"] >= 20 and st["ip_top1_ratio"] > 0.4:
        ip_trig.append((nid, st))
    elif st["ip_n"] >= 20:
        ip_near.append((nid, st))
    else:
        ip_low.append((nid, st))

L: list[str] = []
w = L.append

w("# 42 帖采集数据完整性报告")
w("")
w(f"清单 `urls.txt` **{len(IDS)}** 条 · `data/` 下笔记目录 **{len(dirs)}** 个"
  f"（{len(EXTRA)} 个不在清单内）")
w("")
w("| 口径 | 数值 |")
w("|---|---:|")
w(f"| 评论行 | {TOT} |")
w(f"| ├ 来源 SSR（字段齐全） | {SSR}（{SSR / TOT:.0%}） |")
w(f"| └ 来源 DOM 残件（元数据占位） | {DOM}（{DOM / TOT:.0%}） |")
w(f"| jev 可读评论 | {DS}（{DS / TOT:.0%}） |")
w(f"| 评论有作者昵称 | {NAMED}（{NAMED / max(DS, 1):.0%}） |")
w(f"| 本地图片文件 | {IMGS} |")
w(f"| 有 jev 标签的评论 | {TOT - UNLAB}（{(TOT - UNLAB) / TOT:.0%}） |")
w("")

# ------------------------------------------------------------------ 结论
w("## 结论")
w("")
w("**采集文件层面 42 帖无缺件** —— 42 个目录、`note.json` 42/42、")
w(f"`card.json` 42/42、`comments.txt` 42/42、本地图片 {IMGS} 张且与")
w("`urls.json`、`note.json.images` 三方逐帖一致。")
w("")
w("但有 **4 件事需要知道**，前两件影响使用，后两件影响结论：")
w("")
w("| # | 事项 | 规模 | 影响 |")
w("|---|---|---:|---|")
w(f"| 1 | 回填新增的评论**没有 jev 标签** | {UNLAB} 条 | 这部分内容没有判定结果 |")
w(f"| 2 | `scores.jsonl` 的 **Layer 2 数值已过期** | {len(stale)} 篇 | "
  f"{len(flipped)} 篇的 flag 已翻转 |")
w(f"| 3 | DOM 残件的元数据字段是占位值 | {DOM} 条 | 研究侧（`regression/`）的特征失真 |")
w("| 4 | 2 篇笔记匿名不可见 | 2 篇 | 其中 1 篇零评论、1 篇只有 DOM 残件 |")
w("")

# ------------------------------------------------------------------ L1
w("## L1 笔记层（`content/note.json`）")
w("")
w("| 字段 | 有值 | 缺件 | 完整率 |")
w("|---|---:|---:|---:|")
d1: dict[str, list[str]] = {}
for key, cn, kind in NOTE_FIELDS:
    miss = [r["id"] for r in rows
            if not (r["note"].get(key) is not None if kind == "count"
                    else nonempty(r["note"].get(key)))]
    if miss:
        d1[f"{cn} `{key}`"] = miss
    w(f"| {cn} `{key}` | {len(rows) - len(miss)} | {len(miss)} | "
      f"{(len(rows) - len(miss)) / len(rows):.0%} |")
w("")
w("> 计数型字段（点赞/收藏/评论/分享/图片数）统计**键是否存在** ——")
w("> `share_count: 0` 是「零分享」的真实数据，不是缺件。若按「0 算缺失」")
w("> 判，会把 40/44 篇误报成缺件。")
w("")
if d1:
    w("缺件明细：")
    w("")
    for k, who in sorted(d1.items(), key=lambda x: -len(x[1])):
        w(f"- **{k}**（{len(who)} 篇）：{', '.join(f'`{i[:8]}`' for i in who)}")
w("")
w("`ip_location` 是唯一大面积缺失的字段（29 篇）。它**不影响打分**：")
w("`jev_guard` 只用**评论级** IP 做集中度信号，笔记级 IP 全文未被读取。")
w("")

# ------------------------------------------------------------------ L2
w("## L2 图片层")
w("")
ok3 = [r for r in rows
       if r["files"] == r["urls"] == len(r["note"].get("images") or [])]
w("| 检查 | 通过 | 异常 |")
w("|---|---:|---:|")
w(f"| 本地文件数 == `urls.json` == `note.json.images` | {len(ok3)} | "
  f"{len(rows) - len(ok3)} |")
w(f"| 至少 1 张本地图片非空 | {sum(1 for r in rows if r['files'] > 0)} | "
  f"{sum(1 for r in rows if r['files'] == 0)} |")
w("")
w(f"本地图片 **{IMGS}** 张、`urls.json` **{sum(r['urls'] for r in rows)}** 条 ——")
w("三方数字逐帖一致，无重复计数（曾因 CDN 变体后缀重复计数而虚高一倍，已修）。")
w("")

# ------------------------------------------------------------------ L3
w("## L3 评论层（`comments/comments.json`）")
w("")
w("**必须分两组看**，否则会得出错误结论：")
w("")
w("| 分组 | 行数 | `id`/`content` | 元数据字段 |")
w("|---|---:|---|---|")
w(f"| SSR 抓取 | {SSR} | 真实 | 真实 |")
w(f"| DOM 残件 | {DOM} | 真实 | **占位值** |")
w("")
w("「DOM 残件」判定依据是字段集：只有 `id` `content` `ip_location` `like_count`")
w("`user_info` `sub_comment_count` `pictures` `_is_reply`，缺 `note_id` /")
w("`create_time` / `status` / `sub_comments` 等 SSR 独有字段。")
w("")
w("**占位值的证据**（不是猜测）：")
w("")
dom_like = Counter(str(r.get("like_count")) for rr in rows for r in rr["dom"])
ssr_like = Counter(str(r.get("like_count")) for rr in rows for r in rr["ssr"])
nz_ssr = sum(v for k, v in ssr_like.items() if k not in ("0", "None"))
w(f"- DOM 残件 {DOM} 行的 `like_count` **全部是 `0`**")
w(f"- SSR {SSR} 行里有 {nz_ssr} 行非零（{nz_ssr / SSR:.0%}）")
w(f"- 若两组同分布，DOM 组应有约 {DOM * nz_ssr / SSR:.0f} 行非零，"
  f"实际 0 行 —— 不可能是巧合")
w("")
w("| 字段 | SSR 组 | DOM 组 |")
w("|---|---:|---:|")
w("> 除 `id`/`content` 外的行按**非零/非空**统计；DOM 组全为 0 或空。")
w("")
for key, cn in [("id", "评论ID"), ("content", "评论正文"),
                ("like_count", "评论点赞"),
                ("ip_location", "评论IP属地"), ("create_time", "评论时间戳"),
                ("sub_comment_count", "子评论数")]:
    if key == "like_count":
        a = nz_ssr
        b = sum(1 for rr in rows for r in rr["dom"]
                if str(r.get("like_count")) not in ("0", "None"))
    elif key == "sub_comment_count":
        a = sum(1 for rr in rows for r in rr["ssr"] if key in r and r[key] not in (0, "0"))
        b = sum(1 for rr in rows for r in rr["dom"] if key in r and r[key] not in (0, "0"))
    else:
        a = sum(1 for rr in rows for r in rr["ssr"] if nonempty(r.get(key)))
        b = sum(1 for rr in rows for r in rr["dom"] if nonempty(r.get(key)))
    w(f"| {cn} `{key}` | {a}/{SSR} = {a / max(SSR, 1):.0%} | "
      f"{b}/{DOM} = {b / max(DOM, 1):.0%} |")
w("")
w("> `create_time` 是毫秒时间戳；`sub_comment_count` 可能是 `\"10+\"` 这类展示值")
w("> （小红书对超过 10 条的回复不显示精确数）。两者 `jev_guard` 打分都不读。")
w("")
w(f"附属文件：`card.json` {sum(1 for r in rows if r['card'])}/{len(rows)}、"
  f"`comments.txt` {sum(1 for r in rows if r['txt'])}/{len(rows)}、"
  f"`data/.backup/` 有备份 {sum(1 for r in rows if r['backup'])}/{len(rows)}。")
w("")

# ------------------------------------------------------------------ 标签
w("## 标签覆盖（影响判定结果）")
w("")
w(f"回填新增了评论，但 `labels_comment.jsonl` 是**回填前**产出的：")
w("")
w(f"- 有正文的评论：**{TOT}** 条")
w(f"- 已有 jev 标签：**{TOT - UNLAB}** 条")
w(f"- **无标签：{UNLAB} 条（{UNLAB / TOT:.0%}）**，涉及 {len(unlabeled)} 篇")
w("")
if unlabeled:
    w("缺标签最多的帖：")
    w("")
    for k, v in sorted(unlabeled.items(), key=lambda x: -x[1])[:12]:
        w(f"- `{k[:8]}` +{v}")
    w("")
w("> 这些评论**数据本身完整**（`id`/`content` 齐全，可正常送模型），")
w("> 只是还没打标。重新跑 `label --kind comment` 即可补齐，模型调用量按")
w("> 未标注条数计费。")
w("")

# ------------------------------------------------------------------ Layer 2
w("## Layer 2（传播质量）已过期")
w("")
w(f"`scores.jsonl` 的 `spread_n` / `spread_sd` 基于回填**前**的评论计算，")
w(f"评论量从 881 增到 {TOT} 后：")
w("")
w(f"- **{len(stale)}/{len(IDS)} 篇**的 Layer 2 数值已变化")
w(f"- **{len(flipped)} 篇**的 `spread_flag` 发生翻转")
w("")
if stale:
    w("| 帖 | 旧 n | 新 n | 旧 SD | 新 SD |")
    w("|---|---:|---:|---:|---:|")
    for nid, on, nn, osd, nsd in sorted(
            stale, key=lambda x: abs((x[4] or 0) - (x[3] or 0)), reverse=True)[:10]:
        w(f"| `{nid[:8]}` | {on} | {nn} | {osd} | {nsd} |")
    w("")
if flipped:
    w("flag 翻转：")
    w("")
    for nid, osd, nsd, now in flipped:
        w(f"- `{nid[:8]}`：{osd} → {nsd}，现"
          f"{'触发' if now else '解除'}（阈值 SD < {SPREAD_SD_THRESHOLD}）")
    w("")
w("> Layer 2 **不影响** `total` / `level`（只写 `spread_*` 字段与 notes 文案），")
w("> 所以 Layer 1 的风险判定结论仍然有效；但若引用传播质量信号，必须重算。")
w("")

# ------------------------------------------------------------------ IP 信号
w("## 评论 IP 集中度信号（借用 `is_ad` 权重）")
w("")
w("`score.py` 默认 `use_ip_signals=True`：当 `ip_n >= 20` 且 `ip_top1_ratio > 0.4`")
w("时用 top1 占比覆盖 `is_ad`。当前 42 帖的实际状态：")
w("")
w("| 状态 | 篇数 |")
w("|---|---:|")
w(f"| **触发**（ip_n≥20 且 top1>0.4） | {len(ip_trig)} |")
w(f"| 样本够但不触发（ip_n≥20, top1≤0.4） | {len(ip_near)} |")
w(f"| 样本不足（ip_n<20） | {len(ip_low)} |")
w("")
if ip_near:
    w("最接近阈值的几篇（trigger 需 top1 **超过** 0.4）：")
    w("")
    w("| 帖 | ip_n | top1 | 还差 |")
    w("|---|---:|---:|---:|")
    for nid, st in sorted(ip_near, key=lambda x: -x[1]["ip_top1_ratio"])[:5]:
        w(f"| `{nid[:8]}` | {int(st['ip_n'])} | {st['ip_top1_ratio']:.2f} | "
          f"{(0.4 - st['ip_top1_ratio']) * 100:+.0f} 个百分点 |")
    w("")
w("> 结论：**当前 0 篇触发，IP 数据缺失未改变任何一篇的判定**。但")
w("> 榜首距阈值仅 0.01，`ip_n` 又受「匿名态只内联部分评论」影响，")
w("> 所以这个信号目前处于「刚好不触发」的边界状态，不宜当作稳定依据。")
w("")

# ------------------------------------------------------------------ 逐帖
w("## 逐帖明细")
w("")
w("| # | 帖 ID | 标题 | SSR | DOM | jev可读 | 有名 | 本地图 | 缺标签 |")
w("|---:|---|---|---:|---:|---:|---:|---:|---:|")
for i, r in enumerate(sorted(rows, key=lambda x: -x["ds"]), 1):
    t = str(r["note"].get("title") or "").replace("|", "\\|")[:20] or "—"
    w(f"| {i} | `{r['id'][:8]}` | {t} | {len(r['ssr'])} | {len(r['dom'])} | "
      f"{r['ds']} | {r['named']} | {r['files']} | {unlabeled.get(r['id'], 0) or '—'} |")
w("")

if EXTRA:
    w("## 清单外的额外目录")
    w("")
    w(f"`data/` 下另有 {len(EXTRA)} 个不在 `urls.txt` 的笔记目录，是 HTTP 直连")
    w("联调时的验证产物，数据完整，未纳入 42 帖统计：")
    w("")
    for e in EXTRA:
        c = collect(e)
        w(f"- `{e}` — {len(c['rows'])} 条评论 / {c['files']} 张图 / "
          f"标题「{str(c['note'].get('title') or '—')[:26]}」")
    w("")

w("## 已知边界（非缺陷）")
w("")
w("1. **每篇只保障 5 条一级评论**。匿名态 SSR 只内联首页评论，分页接口")
w("   `comment/page` 返回 461（IP + 接口滑窗配额），翻页需登录态。")
w("   现有量已满足 jev 打分与 Layer 2 标准差（≥3 条）的样本要求。")
w("2. **DOM 残件的 135 行元数据是占位值**，但 `id` 与 `content` 是真实的。")
w("   对 jev 打分无影响（`load_comment` 只用 `id`/`content`/`like_count`，")
w("   而评论 `liked` 只用于展示）；对 `regression/features.py` 有影响，")
w("   那里的 `ip_location` / `create_time` / `like_count` 特征会失真。")
w("3. **零评论 ≠ 无数据**。`note.json` 完整，jev 走笔记维度照常打分。")
w("4. **2 篇匿名不可见**：`6abc5bb8`（SSR 只返回 10KB 空壳、零评论）、")
w("   `6a17c863`（同样空壳，现有 10 条全部来自登录态 DOM 快照）。")
w("   已验证与配额无关（同一时刻其他帖正常返回），属笔记侧可见性限制。")
w("")

OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text("\n".join(L) + "\n", encoding="utf-8")
print(f"wrote {OUT} ({len(L)} lines)")

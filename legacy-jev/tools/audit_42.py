"""42篇笔记的数据齐全度审计 —— 逐字段给出真实覆盖率。

只读，不改任何东西。输出 out/data_audit_42.md
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from jev_guard.core.config import load_config  # noqa: E402
from jev_guard.extractors.reader import iter_note_ids  # noqa: E402

cfg = load_config()
L: list[str] = []


def emit(s: str = "") -> None:
    L.append(s)


def has(v) -> bool:
    """字段是否有真实值（0/空串/空列表都算没有）。"""
    return v not in (None, "", [], {}, 0, "0", -1, "-1")


NOTE_FIELDS = [
    ("title", "标题", ("title", "作品标题")),
    ("desc", "正文", ("desc", "作品描述")),
    ("tags", "标签", ("tags", "作品标签")),
    ("author", "作者", ("author", "作者昵称")),
    ("liked", "点赞数", ("liked", "点赞数量")),
    ("collected", "收藏数", ("collected", "收藏数量")),
    ("comment_count", "评论数", ("comment_count", "评论数量")),
    ("share", "分享数", ("share_count", "分享数量")),
    ("published", "发布时间", ("published", "发布时间")),
    ("ip_location", "IP属地", ("ip_location", "IP属地")),
]

CMT_FIELDS = [
    ("content", "正文", ("content",)),
    ("create_time", "时间戳", ("create_time",)),
    ("ip_location", "IP属地", ("ip_location",)),
    ("like_count", "点赞数", ("like_count", "liked")),
    ("user_info", "用户信息", ("user_info",)),
    ("sub_comment_count", "回复数", ("sub_comment_count",)),
]

ids = list(iter_note_ids(cfg.data_root))
emit("# 42 篇笔记数据齐全度审计")
emit()
emit(f"笔记目录总数：**{len(ids)}**")
emit()

# ---------------------------------------------------------------- 笔记层
emit("## 1. 笔记层字段覆盖率")
emit()
cov = {k: 0 for k, *_ in NOTE_FIELDS}
per_note: dict[str, dict] = {}

for nid in ids:
    p = cfg.data_root / nid / "content" / "note.json"
    if not p.is_file():
        continue
    try:
        n = json.loads(p.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        continue
    if not isinstance(n, dict):
        continue
    row = {}
    for key, _label, alts in NOTE_FIELDS:
        v = next((n[a] for a in alts if a in n), None)
        ok = has(v)
        row[key] = ok
        cov[key] += int(ok)
    per_note[nid] = row

emit("| 字段 | 有值 | 覆盖率 | 缺失的 note |")
emit("| --- | ---: | ---: | --- |")
for key, label, _ in NOTE_FIELDS:
    miss = [nid[:8] for nid, r in per_note.items() if not r.get(key)]
    m = f"{len(miss)} 篇: `{'`, `'.join(miss)}`" if miss else "—"
    emit(f"| {label} | {cov[key]}/{len(per_note)} | "
         f"{cov[key] / len(per_note) * 100:.0f}% | {m} |")
emit()

# ---------------------------------------------------------------- 评论存在性
emit("## 2. 评论采集情况")
emit()
rows = []
for nid in ids:
    p = cfg.data_root / nid / "content" / "note.json"
    if not p.is_file():
        continue
    try:
        n = json.loads(p.read_text(encoding="utf-8"))
        claim = int(n.get("comment_count") or n.get("评论数量") or 0)
    except Exception:  # noqa: BLE001
        claim = 0
    cpath = cfg.data_root / nid / "comments" / "comments.json"
    got = 0
    if cpath.is_file():
        try:
            arr = json.loads(cpath.read_text(encoding="utf-8"))
            got = len(arr) if isinstance(arr, list) else 0
        except Exception:  # noqa: BLE001
            got = 0
    rows.append((nid, claim, got))

have_c = [r for r in rows if r[2] > 0]
zero_c = [r for r in rows if r[2] == 0]
full_c = [r for r in rows if r[1] > 0 and r[1] <= r[2]]
trunc = [r for r in rows if 0 < r[2] < r[1]]
t10 = [r for r in rows if r[2] == 10]

emit(f"- 有评论的笔记：**{len(have_c)}/{len(rows)}**")
emit(f"- 完全没有评论的笔记：**{len(zero_c)}** 篇")
emit(f"- 完整采集（标称 ≤ 实际）：**{len(full_c)}** 篇")
emit(f"- 部分采集（0 < 实际 < 标称）：**{len(trunc)}** 篇")
emit(f"-恰好 10 条（疑似单页上限）：**{len(t10)}** 篇")
emit()
emit(f"- 评论总计：**{sum(r[2] for r in rows)}** 条")
emit(f"- 标称总计：**{sum(r[1] for r in rows)}** 条")
emit()

if zero_c:
    emit("### 完全没有评论的笔记")
    emit()
    for nid, claim, _ in zero_c:
        emit(f"- `{nid[:8]}` 标称 {claim} 条")
    emit()

# ---------------------------------------------------------------- 评论层字段
emit("## 3. 评论层字段覆盖率")
emit()
emit(f"按**有评论的 {len(have_c)} 篇**统计，共 "
     f"{sum(r[2] for r in rows)} 条评论。")
emit()
emit("| 字段 | 有值评论数 | 占比 |")
emit("| --- | ---: | ---: |")
ccov = {k: 0 for k, *_ in CMT_FIELDS}
tot_c = 0
per_note_c: dict[str, set] = {}
for nid, _c, got in rows:
    if not got:
        continue
    cpath = cfg.data_root / nid / "comments" / "comments.json"
    try:
        arr = json.loads(cpath.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        continue
    ok_set = set()
    for r in arr:
        if not isinstance(r, dict):
            continue
        tot_c += 1
        for key, _l, alts in CMT_FIELDS:
            v = next((r[a] for a in alts if a in r), None)
            if has(v):
                ccov[key] += 1
                ok_set.add(key)
    per_note_c[nid] = ok_set

for key, label, _ in CMT_FIELDS:
    emit(f"| {label} | {ccov[key]}/{tot_c} | "
         f"{ccov[key] / tot_c * 100:.1f}% |")
emit()

# ---------------------------------------------------------------- 分组
emit("## 4. 按「评论字段完整度」分组")
emit()
emit("这决定哪些笔记能做互动分析。")
emit()
groups: dict[str, list[str]] = {}
CORE = ("content", "create_time", "ip_location", "like_count")
for nid, _c, got in rows:
    if not got:
        continue
    s = per_note_c.get(nid, set())
    n_ok = sum(1 for k in CORE if k in s)
    key = ("完整（4/4 核心字段）" if n_ok == 4
           else f"残缺（{n_ok}/4）")
    groups.setdefault(key, []).append(nid)

emit("| 组别 | 笔记数 | note |")
emit("| --- | ---: | --- |")
for k in sorted(groups):
    v = groups[k]
    emit(f"| {k} | {len(v)} | `{'`, `'.join(x[:8] for x in v)}` |")
emit()

usable = groups.get("完整（4/4 核心字段）", [])
emit("## 5. 结论")
emit()
emit(f"-笔记互动指标：**{len(per_note)}/{len(per_note)}** 篇齐全")
emit(f"- 评论核心字段齐全的笔记：**{len(usable)}/{len(rows)}** 篇")
emit(f"- 这 {len(usable)} 篇共 "
     f"{sum(r[2] for r in rows if r[0] in usable)} 条评论可用于互动分析")
emit()
if len(usable) < len(rows):
    emit(f"**{len(rows) - len(usable)} 篇的评论缺 create_time / ip_location / "
         "like_count，无法做时间与地域分析。**")

out = ROOT / "out" / "data_audit_42.md"
out.write_text("\n".join(L), encoding="utf-8")
print(f"written: {out}")
""" brainstorm 探针：测那些「纯文本 + 笔记级字段」就能算的信号。

只测匿名可得的数据：
  笔记层 liked/collected/comment_count/share/published/image_count/tags
  评论层 content（正文）
输出 out/brainstorm.md
"""

from __future__ import annotations

import json
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from jev_guard.core.config import load_config  # noqa: E402
from jev_guard.extractors.reader import (  # noqa: E402
    iter_note_ids, load_comments, load_note, to_int,
)

cfg = load_config()
L: list[str] = []


def emit(s: str = "") -> None:
    L.append(s)


def read_json(p: Path):
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return None


def spearman(a: list[float], b: list[float]) -> float:
    n = len(a)
    if n < 3:
        return 0.0

    def ranks(xs):
        order = sorted(range(len(xs)), key=lambda i: xs[i])
        r = [0.0] * len(xs)
        for pos, i in enumerate(order):
            r[i] = float(pos)
        return r

    ra, rb = ranks(a), ranks(b)
    ma, mb = sum(ra) / n, sum(rb) / n
    num = sum((x - ma) * (y - mb) for x, y in zip(ra, rb))
    den = (sum((x - ma) ** 2 for x in ra) * sum((y - mb) ** 2 for y in rb)) ** 0.5
    return num / den if den else 0.0


scores = [json.loads(l) for l in
          (ROOT / "out" / "scores.jsonl").read_text(encoding="utf-8").splitlines()
          if l.strip()]
note_score = {s["subject_id"]: s for s in scores if s["kind"] == "note"}

# ---------------------------------------------------------------- 载入
notes = []
for nid in iter_note_ids(cfg.data_root):
    s = load_note(cfg.data_root, nid)
    if not s:
        continue
    raw = read_json(cfg.data_root / nid / "content" / "note.json") or {}
    sc = note_score.get(nid)
    if not sc:
        continue
    notes.append({
        "id": nid, "s": s, "raw": raw, "risk": sc["total"],
        "level": sc["level"],
        "dims": {d["name"]: d["value"] for d in sc["dimensions"]},
    })

emit("# brainstorm：匿名可得数据能挖出什么信号")
emit()
emit(f"可用笔记：**{len(notes)}**")
emit()

HYP = ">?！？!！…～~"
EMOJI = re.compile(
    "["
    "\U0001F300-\U0001FAFF"
    "\U00002600-\U000027BF"
    "\U0001F1E6-\U0001F1FF"
    "]+"
)

# ================================================================ 1. 模板化评论
emit("## 信号 1：重复评论文本（刷评的直接证据）")
emit()
emit("纯文本就能查 —— 如果多条评论文本完全一样，")
emit("那不是真实用户写的，是刷的。")
emit()
dup_total = 0
dup_examples = []
all_texts = Counter()
for n in notes:
    for c in load_comments(cfg.data_root, n["id"]):
        t = re.sub(r"\s+", "", c.text or "")
        if len(t) >= 4:
            all_texts[t] += 1

for t, k in all_texts.most_common():
    if k >= 2:
        dup_total += k
        dup_examples.append((t, k))
emit(f"- 评论总数（≥4字）：**{sum(all_texts.values())}** 条")
emit(f"- 出现重复的文本：**{len(dup_examples)}** 组")
emit(f"- 涉及条数：**{dup_total}** 条")
emit()
if dup_examples:
    emit("| 重复文本 | 次数 |")
    emit("| --- | ---: |")
    for t, k in dup_examples[:15]:
        emit(f"| {t[:40]} | **{k}** |")
    emit()
else:
    emit("**没有发现完全重复的评论文本。**")
    emit()
    emit("> 这本身是个结论：当前 42 篇里**没有明显的模板刷评**。")
    emit("> 但样本只有 10 条/篇（20 篇），重复概率本来就低。")
    emit()

# ================================================================ 2. 话题标签数
emit("## 信号 2：话题标签数量")
emit()
emit("正常 UGC 打 1-3 个话题，营销号/官号会堆 8+ 个。")
emit()
rows = []
for n in notes:
    tags = n["s"].tags
    if not tags:
        continue
    rows.append((len(tags), n["risk"], n["level"], n["id"]))
if rows:
    rows.sort()
    emit("| 笔记 | 标签数 | jev风险 | 等级 |")
    emit("| --- | ---: | ---: | --- |")
    for k, r, lv, nid in rows:
        emit(f"| `{nid[:8]}` | {k} | {r:.3f} | {lv} |")
    emit()
    ks = [k for k, *_ in rows]
    rs = [r for _, r, *_ in rows]
    emit(f"- n = **{len(rows)}**")
    emit(f"- 标签数中位数：**{sorted(ks)[len(ks) // 2]}**")
    emit(f"- 标签数 vs jev风险 Spearman = **{spearman(rs, ks):+.3f}**")
    emit()
    by: dict[str, list[int]] = defaultdict(list)
    for k, _r, lv, _n in rows:
        by[lv].append(k)
    emit("| 等级 | 篇数 | 标签数中位 |")
    emit("| --- | ---: | ---: |")
    for lv in ("high", "medium", "low"):
        g = by.get(lv, [])
        if g:
            emit(f"| {lv} | {len(g)} | {sorted(g)[len(g) // 2]} |")
    emit()

# ================================================================ 3. 发布时长
emit("## 信号 3：发布时长（去除「新帖评论没长起来」的混淆）")
emit()
emit("这是上一轮我漏掉的控制变量 —— 评赞比可能只是「发布多久」的代理。")
emit()
NOW = datetime(2026, 10, 8, tzinfo=timezone.utc)
rows2 = []
for n in notes:
    ms = to_int(n["raw"].get("time_ms") or n["raw"].get("时间戳") or 0)
    if not ms:
        continue
    dt = datetime.fromtimestamp(ms / 1000, tz=timezone.utc)
    age_days = (NOW - dt).days
    rows2.append((age_days, n["risk"], n["level"], n["id"],
                   n["s"].comment_count, n["s"].liked))
if rows2:
    rows2.sort()
    emit("| 笔记 | 发布天数 | 赞 | 评论 | 评赞比 | jev风险 | 等级 |")
    emit("| --- | ---: | ---: | ---: | ---: | ---: | --- |")
    for a, r, lv, nid, lc, lk in rows2:
        cr = lc / lk * 100 if lk else 0
        emit(f"| `{nid[:8]}` | {a} | {lk} | {lc} | {cr:.1f}% | "
             f"{r:.3f} | {lv} |")
    emit()
    ages = [x[0] for x in rows2]
    risks = [x[1] for x in rows2]
    crs = [(x[4] / x[5]) if x[5] else 0 for x in rows2]
    emit("| 关系 | Spearman | 判断 |")
    emit("| --- | ---: | --- |")
    for name, xs in (("发布天数", ages), ("评赞比", crs)):
        r = spearman(risks, xs)
        a_ = abs(r)
        j = "**强**" if a_ > 0.5 else ("显著" if a_ > 0.31
                                       else ("弱" if a_ > 0.2 else "无"))
        emit(f"| jev风险 ~ {name} | {r:+.3f} | {j} |")
    emit()
    emit(f"- 发布天数范围：**{min(ages)} ~ {max(ages)} 天**")
    emit(f"- 中位数：**{sorted(ages)[len(ages) // 2]} 天**")
    emit()

# ================================================================ 4. 正文长度
emit("## 信号 4：正文长度 / 标题长度")
emit()
rows3 = []
for n in notes:
    tl = len(n["s"].title or "")
    bl = len(n["s"].text or "")
    if tl == 0 and bl == 0:
        continue
    rows3.append((tl, bl, n["risk"], n["level"], n["id"]))
if rows3:
    rows3.sort(key=lambda x: -(x[1]))
    emit("| 笔记 | 标题字数 | 正文字数 | 标题/正文 | jev风险 | 等级 |")
    emit("| --- | ---: | ---: | ---: | ---: | --- |")
    for tl, bl, r, lv, nid in rows3:
        ratio = f"{tl / bl:.2f}" if bl else "-"
        emit(f"| `{nid[:8]}` | {tl} | {bl} | {ratio} | {r:.3f} | {lv} |")
    emit()
    tls = [x[0] for x in rows3]
    bls = [x[1] for x in rows3]
    rs = [x[2] for x in rows3]
    emit(f"- n = **{len(rows3)}**")
    emit(f"- 标题字数 vs 风险 Spearman = **{spearman(rs, tls):+.3f}**")
    emit(f"- 正文字数 vs 风险 Spearman = **{spearman(rs, bls):+.3f}**")
    emit()
    by2: dict[str, list[int]] = defaultdict(list)
    for _tl, b, _r, lv, _n in rows3:
        by2[lv].append(b)
    emit("| 等级 | 篇数 | 正文字数中位 |")
    emit("| --- | ---: | ---: |")
    for lv in ("high", "medium", "low"):
        g = by2.get(lv, [])
        if g:
            emit(f"| {lv} | {len(g)} | {sorted(g)[len(g) // 2]} |")
    emit()

# ================================================================ 5. 图片数
emit("## 信号 5：图片数量")
emit()
rows4 = [(n["s"].image_count, n["risk"], n["level"], n["id"])
         for n in notes]
rows4.sort(key=lambda x: -x[0])
emit("| 笔记 | 图片数 | jev风险 | 等级 |")
emit("| --- | ---: | ---: | --- |")
for k, r, lv, nid in rows4:
    emit(f"| `{nid[:8]}` | {k} | {r:.3f} | {lv} |")
emit()
emit(f"- 图片数 vs 风险 Spearman = "
     f"**{spearman([x[1] for x in rows4], [x[0] for x in rows4]):+.3f}**")
by3: dict[str, list[int]] = defaultdict(list)
for k, _r, lv, _n in rows4:
    by3[lv].append(k)
emit()
emit("| 等级 | 篇数 | 图片数中位 |")
emit("| --- | ---: | ---: |")
for lv in ("high", "medium", "low"):
    g = by3.get(lv, [])
    if g:
        emit(f"| {lv} | {len(g)} | {sorted(g)[len(g) // 2]} |")
emit()

# ================================================================ 6. 作者
emit("## 信号 6：作者矩阵")
emit()
emit("同一作者发多篇 → 账号矩阵/官方号集中投放")
emit()
auth = Counter(n["s"].author for n in notes if n["s"].author)
emit("| 作者 | 篇数 | 等级分布 |")
emit("| --- | ---: | --- |")
for a, k in auth.most_common():
    lvs = Counter(n["level"] for n in notes if n["s"].author == a)
    emit(f"| {a} | {k} | {dict(lvs)} |")
emit()
multi = [a for a, k in auth.items() if k >= 2]
emit(f"- 发了 ≥2 篇的作者：**{len(multi)}** 个")
for a in multi:
    g = [n for n in notes if n["s"].author == a]
    emit(f"  - `{a}`：{len(g)} 篇，"
         f"风险 {[f'{x[chr(114)+chr(105)+chr(115)+chr(107)]:.2f}' for x in g]}，"
         f"等级 {[x['level'] for x in g]}")
emit()

# ================================================================ 7. 评论疑问率
emit("## 信号 7：评论疑问率（真实讨论 vs 打卡）")
emit()
emit("问号/疑问词多 → 真实讨论；纯打卡/感谢 → 水军或路人")
emit()
neg_by_note: dict[str, list[float]] = {}
q_by_note: dict[str, list[float]] = {}
len_by_note: dict[str, list[float]] = {}
cmt_to_note: dict[str, str] = {}
for nid in iter_note_ids(cfg.data_root):
    arr = read_json(cfg.data_root / nid / "comments" / "comments.json")
    if not isinstance(arr, list):
        continue
    for r in arr:
        if isinstance(r, dict) and r.get("id"):
            cmt_to_note[str(r["id"])] = nid

for s in scores:
    if s["kind"] != "comment":
        continue
    nid = cmt_to_note.get(s["subject_id"])
    if nid is None:
        continue
    c = next((x for x in load_comments(cfg.data_root, nid)
              if x.subject_id == s["subject_id"]), None)
    if c is None:
        continue
    v = next((d["value"] for d in s["dimensions"]
              if d["name"] == "negativity"), None)
    if v is not None:
        neg_by_note.setdefault(nid, []).append(v)
    t = c.text or ""
    q_by_note.setdefault(nid, []).append(
        1.0 if (HYP in t or any(w in t for w in ("吗", "怎么", "为什么", "如何")))
        else 0.0)
    len_by_note.setdefault(nid, []).append(float(len(t)))

rows5 = [(n["id"], n["risk"], n["level"],
          sum(q_by_note.get(n["id"], [])) / max(len(q_by_note.get(n["id"], [1])), 1),
          sum(len_by_note.get(n["id"], [])) / max(len(len_by_note.get(n["id"], [1])), 1),
          len(neg_by_note.get(n["id"], [])))
         for n in notes if n["id"] in neg_by_note]
if rows5:
    emit("| 笔记 | 等级 | jev风险 | 评论数 | 疑问率 | 评论均长 | 负面均值 |")
    emit("| --- | --- | ---: | ---: | ---: | ---: | ---: |")
    for nid, r, lv, q, cl, nc in sorted(rows5, key=lambda x: -(x[1])):
        nv = neg_by_note.get(nid, [])
        nm = sum(nv) / len(nv) if nv else 0
        emit(f"| `{nid[:8]}` | {lv} | {r:.3f} | {nc} | {q * 100:.0f}% | "
             f"{cl:.0f} | {nm:.3f} |")
    emit()
    emit("| 关系 | Spearman |")
    emit("| --- | ---: |")
    for name, xs in (("疑问率", [x[3] for x in rows5]),
                     ("评论均长", [x[4] for x in rows5]),
                     ("评论数", [x[5] for x in rows5])):
        emit(f"| jev风险 ~ {name} | "
             f"{spearman([x[1] for x in rows5], xs):+.3f} |")
    emit()

# ================================================================ 8. 标题党
emit("## 信号 8：标题党指数（标题 vs 正文长度失衡）")
emit()
rows6 = []
for n in notes:
    tl, bl = len(n["s"].title or ""), len(n["s"].text or "")
    if tl == 0 or bl == 0:
        continue
    rows6.append((tl / bl, n["risk"], n["level"], n["id"], tl, bl))
rows6.sort(reverse=True)
emit("| 笔记 | 标题/正文比 | 标题 | 正文 | jev风险 | 等级 |")
emit("| --- | ---: | ---: | ---: | ---: | --- |")
for ratio, r, lv, nid, tl, bl in rows6:
    emit(f"| `{nid[:8]}` | **{ratio:.2f}** | {tl} | {bl} | "
         f"{r:.3f} | {lv} |")
emit()
emit(f"- 标题/正文比 vs 风险 Spearman = "
     f"**{spearman([x[1] for x in rows6], [x[0] for x in rows6]):+.3f}**")
emit(f"- n = **{len(rows6)}**")
emit()
hi = [x for x in rows6 if x[0] > 0.5]
if hi:
    emit(f"标题长度超正文一半的：**{len(hi)}** 篇 —— ")
    emit(f"其中 high {sum(1 for x in hi if x[2] == 'high')} 篇，"
         f"low {sum(1 for x in hi if x[2] == 'low')} 篇")
    emit()

out = ROOT / "out" / "brainstorm.md"
out.write_text("\n".join(L), encoding="utf-8")
print(f"written: {out}")
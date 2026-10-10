"""互动数据可用性探针 —— 在决定怎么接入之前，先确认信号是否存在。

只读，不改任何东西。输出 out/engagement_probe.md。
"""

import json
import statistics
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from jev_guard.core.config import load_config  # noqa: E402
from jev_guard.extractors.reader import (  # noqa: E402
    iter_note_ids,
    load_comments,
    load_note,
    to_int,
)

CFG = load_config()
L: list[str] = []


def emit(s: str = "") -> None:
    L.append(s)


def read(p: Path):
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None


# ---------------------------------------------------------------- 1. 笔记层
emit("## 1. 笔记层互动字段覆盖率")
emit()
notes = []
for nid in iter_note_ids(CFG.data_root):
    s = load_note(CFG.data_root, nid)
    if s:
        notes.append(s)

rows = [
    ("liked", lambda s: s.liked),
    ("collected", lambda s: s.collected),
    ("comment_count", lambda s: s.comment_count),
    ("share", lambda s: s.share),
    ("image_count", lambda s: s.image_count),
]
emit("| 字段 | 非零数 | 中位数 | 最大值 |")
emit("| --- | ---: | ---: | ---: |")
for name, f in rows:
    vals = [f(s) for s in notes]
    nz = [v for v in vals if v > 0]
    med = int(statistics.median(nz)) if nz else 0
    emit(f"| {name} | {len(nz)}/{len(notes)} | {med} | {max(vals) if vals else 0} |")
emit()

# ---------------------------------------------------------------- 2. 评论层字段
emit("## 2. 评论层字段可用性")
emit()
all_rows = []
for nid in iter_note_ids(CFG.data_root):
    arr = read(CFG.data_root / nid / "comments" / "comments.json")
    if isinstance(arr, list):
        all_rows.extend(r for r in arr if isinstance(r, dict))

emit(f"评论总数：**{len(all_rows)}**")
emit()
checks = [
    ("like_count", lambda r: to_int(r.get("like_count", 0))),
    ("sub_comment_count", lambda r: to_int(r.get("sub_comment_count", 0))),
    ("ip_location", lambda r: 1 if r.get("ip_location") else 0),
    ("create_time", lambda r: 1 if r.get("create_time") else 0),
    ("show_tags", lambda r: 1 if r.get("show_tags") else 0),
    ("_is_reply", lambda r: 1 if "_is_reply" in r else 0),
]
emit("| 字段 | 有值数 | 占比 | 非零/非空 |")
emit("| --- | ---: | ---: | ---: |")
for name, f in checks:
    vals = [f(r) for r in all_rows]
    have = sum(1 for v in vals if v)
    emit(f"| {name} | {have}/{len(all_rows)} | {have / len(all_rows) * 100:.1f}% | "
         f"{sum(1 for v in vals if v) if name in ('like_count', 'sub_comment_count') else '-'} |")
emit()

# create_time 格式
emit("### create_time 格式样例")
emit()
samples = [r.get("create_time") for r in all_rows if r.get("create_time")][:3]
for v in samples:
    emit(f"- `{v!r}` (type={type(v).__name__})")
emit()

# ---------------------------------------------------------------- 3. 子评论是否采集
emit("## 3. 嵌套回复采集情况")
emit()
sub_declared = sum(to_int(r.get("sub_comment_count", 0)) for r in all_rows)
sub_embedded = sum(len(r.get("sub_comments") or []) for r in all_rows
                  if isinstance(r.get("sub_comments"), list))
emit(f"- `sub_comment_count` 声明的回复总数：**{sub_declared}**")
emit(f"- `sub_comments` 字段里实际内嵌的回复：**{sub_embedded}**")
emit(f"- `sub_comment_has_more=True` 的条数："
     f"{sum(1 for r in all_rows if r.get('sub_comment_has_more'))}")
emit()
emit("> 若内嵌远少于声明，说明回复层**没有采集**，回复相关信号不可用。")
emit()

# ---------------------------------------------------------------- 4. IP 分布
emit("## 4. IP 属地分布（省级粒度）")
emit()
ips = [str(r.get("ip_location") or "").strip() for r in all_rows if r.get("ip_location")]
emit(f"有 IP 的评论：**{len(ips)}/{len(all_rows)}**")
emit()
if ips:
    c = Counter(ips)
    uniq = len(c)
    emit(f"去重后省份数：**{uniq}**")
    emit()
    emit("| 省份 | 条数 | 占比 |")
    emit("| --- | ---: | ---: |")
    for k, v in c.most_common(12):
        emit(f"| {k} | {v} | {v / len(ips) * 100:.1f}% |")
    emit()
    top1 = c.most_common(1)[0]
    emit(f"单一省份最大占比：**{top1[1] / len(ips) * 100:.1f}%**（{top1[0]}）")
    # 多样本下的自然集中度基线
    emit()
    emit("### 逐笔记的地域集中度（这是真正该看的粒度）")
    emit()
    emit("| 笔记 | 评论数 | 省份数 | top1占比 | 期望基线 | 超出倍数 |")
    emit("| --- | ---: | ---: | ---: | ---: | ---: |")
    ratios = []
    for nid in iter_note_ids(CFG.data_root):
        cs = load_comments(CFG.data_root, nid)
        locs = [str(read(CFG.data_root / nid / "comments" / "comments.json") or [])]
        arr = read(CFG.data_root / nid / "comments" / "comments.json") or []
        locs = [str(a.get("ip_location") or "").strip() for a in arr
                if isinstance(a, dict) and a.get("ip_location")]
        n = len(locs)
        if n < 5:
            continue
        cc = Counter(locs)
        t1 = cc.most_common(1)[0][1] / n
        # 多项分布下最大占比的期望 ~ 3/n（k远大于n时的经验值）
        base = 3.0 / n
        ratios.append(t1 / base)
        emit(f"| `{nid[:8]}` | {n} | {len(cc)} | {t1 * 100:.0f}% | "
             f"{base * 100:.0f}% | {t1 / base:.1f}x |")
    if ratios:
        emit()
        emit(f"**超出倍数：中位数 {statistics.median(ratios):.2f}x，"
             f"最大 {max(ratios):.2f}x**")
emit()

# ---------------------------------------------------------------- 5. 核心假设检验
emit("## 5. 你的核心假设：笔记热度 vs 评论热度 是否脱节")
emit()
emit("| 笔记 | 赞 | 藏 | 评论数 | 评论总赞 | 赞/藏比 | 评论均赞 |")
emit("| --- | ---: | ---: | ---: | ---: | ---: | ---: |")
pairs = []
for nid in iter_note_ids(CFG.data_root):
    s = load_note(CFG.data_root, nid)
    if not s or s.liked <= 0:
        continue
    cs = load_comments(CFG.data_root, nid)
    if not cs:
        continue
    sum_c = sum(c.liked for c in cs)
    avg_c = sum_c / len(cs)
    ratio = s.liked / s.collected if s.collected > 0 else float("inf")
    pairs.append((s.liked, s.collected, len(cs), sum_c, avg_c, ratio, nid))
    emit(f"| `{nid[:8]}` | {s.liked} | {s.collected} | {len(cs)} | {sum_c} | "
         f"{ratio:.1f} | {avg_c:.1f} |")

if pairs:
    emit()
    liked = [p[0] for p in pairs]
    avg_c = [p[4] for p in pairs]
    n = len(pairs)

    def spearman(a, b):
        ra = {v: i for i, v in enumerate(sorted(a))}
        rb = {v: i for i, v in enumerate(sorted(b))}
        sa = [ra[v] for v in a]
        sb = [rb[v] for v in b]
        ma, mb = statistics.mean(sa), statistics.mean(sb)
        num = sum((x - ma) * (y - mb) for x, y in zip(sa, sb))
        den = (sum((x - ma) ** 2 for x in sa) *
               sum((y - mb) ** 2 for y in sb)) ** 0.5
        return num / den if den else 0.0

    emit(f"n = {n} 篇")
    emit()
    emit(f"- 笔记点赞 vs **评论平均点赞** Spearman = **{spearman(liked, avg_c):+.3f}**")
    zero_avg = sum(1 for p in pairs if p[4] < 1)
    emit(f"- 评论平均点赞 < 1 的笔记：**{zero_avg}/{n}** 篇")
    emit()
    emit("> n 很小，这个系数**不能当结论**，只能当方向参考。")
emit()

out = Path("out/engagement_probe.md")
out.write_text("\n".join(L), encoding="utf-8")
print(f"written: {out}")
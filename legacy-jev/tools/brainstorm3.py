"""第三轮挖掘：is_useful 维度 + 评论级组合信号。

is_useful（真实体验）jev 已经给所有 873 条打了分，但从没进过任何分析。
  - meav=0.257（比 negativity 0.280 更低）
  - >=0.8 的有 75 条（真实体验），<0.2 的有 550 条

测：
  1. is_useful vs 评论长度 —— 两个是不是同一个信号？
  2. 笔记级 is_useful 分布 vs jev 风险
  3. 同篇评论的长度方差（真实讨论天然有长有短，刷评长度整齐）
  4. 评论方向：追问 vs 表达（"求链接" vs "我用了觉得"）
  5. 评论首词分布（求/借楼/多少钱 vs 我/用了/感觉）

输出 out/brainstorm3.md
"""

from __future__ import annotations

import json
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from jev_guard.core.config import load_config  # noqa: E402
from jev_guard.extractors.reader import (  # noqa: E402
    iter_note_ids, load_comments,
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


def mean(xs):
    return sum(xs) / len(xs) if xs else 0.0


scores = [json.loads(l) for l in
          (ROOT / "out" / "scores.jsonl").read_text(encoding="utf-8").splitlines()
          if l.strip()]
note_score = {s["subject_id"]: s for s in scores if s["kind"] == "note"}

# ---- 评论级 is_useful + 正文 ----
cmt_use: dict[str, float] = {}
cmt_ad: dict[str, float] = {}
for s in scores:
    if s["kind"] != "comment":
        continue
    for d in s["dimensions"]:
        if d["name"] == "is_useful":
            cmt_use[s["subject_id"]] = d["value"]
        elif d["name"] == "is_ad":
            cmt_ad[s["subject_id"]] = d["value"]

emit("# 第三轮挖掘")
emit()

# ================================================================ 1. is_useful vs 长度
emit("## 1. is_useful vs 评论长度 —— 是不是同一个信号")
emit()
pairs = []
for nid in iter_note_ids(cfg.data_root):
    for c in load_comments(cfg.data_root, nid):
        u = cmt_use.get(c.subject_id)
        if u is None:
            continue
        t = (c.text or "").strip()
        pairs.append((u, float(len(t)), t))
if pairs:
    us = [p[0] for p in pairs]
    ls = [p[1] for p in pairs]
    emit(f"- n = **{len(pairs)}** 条")
    emit(f"- is_useful vs 评论长度 Spearman = "
         f"**{spearman(us, ls):+.3f}**")
    emit()
    emit("| is_useful区间 | 条数 | 评论均长 | 例句 |")
    emit("| --- | ---: | ---: | --- |")
    ex = {}
    for u, ln, t in pairs:
        k = "<0.2" if u < 0.2 else ("0.2-0.5" if u < 0.5 else ">=0.5")
        ex.setdefault(k, []).append((ln, t))
    for k in ("<0.2", "0.2-0.5", ">=0.5"):
        g = ex.get(k, [])
        ml = mean([x[0] for x in g]) if g else 0
        eg = g[0][1][:36] if g else "-"
        emit(f"| {k} | {len(g)} | {ml:.0f} | {eg} |")
    emit()
    emit("如果两者 r > 0.7 → 同一信号，用长度就行（免费）；")
    emit("如果 r < 0.3 → is_useful 是独立信息，值得保留。")
    emit()

# ================================================================ 2. 笔记级 is_useful
emit("## 2. 笔记级 is_useful 均值 vs jev 风险")
emit()
rows = []
for nid in iter_note_ids(cfg.data_root):
    sc = note_score.get(nid)
    if not sc:
        continue
    us = [cmt_use[c.subject_id] for c in load_comments(cfg.data_root, nid)
          if c.subject_id in cmt_use]
    rows.append((nid, sc["total"], sc["level"], mean(us), len(us)))
rows.sort(key=lambda x: -x[1])
emit("| 笔记 | jev | 等级 | 评论is_useful均值 | 评论数 |")
emit("| --- | ---: | --- | ---: | ---: |")
for nid, r, lv, m, k in rows:
    emit(f"| `{nid[:8]}` | {r:.3f} | {lv} | {m:.3f} | {k} |")
emit()
ok = [(x[1], x[3]) for x in rows if x[4] > 0]
emit()
emit(f"- n = **{len(ok)}** 篇")
emit(f"- jev风险 ~ 笔记 is_useful 均值 Spearman = "
     f"**{spearman([x[0] for x in ok], [x[1] for x in ok]):+.3f}**")
emit()
by: dict[str, list[float]] = {}
for _nid, _r, lv, m, k in rows:
    if k > 0:
        by.setdefault(lv, []).append(m)
emit("| 等级 | 篇数 | is_useful均值中位 |")
emit("| --- | ---: | ---: |")
for lv in ("high", "medium", "low"):
    g = sorted(by.get(lv, []))
    if g:
        emit(f"| {lv} | {len(g)} | {g[len(g) // 2]:.3f} |")
emit()

# ================================================================ 3. 长度方差
emit("## 3. 同篇评论长度的离散度（真实讨论天然有长有短）")
emit()
emit("刷评/水军评论长度整齐 → 标准差小；")
emit("真实讨论有长有短 → 标准差大。")
emit()
rows3 = []
for nid in iter_note_ids(cfg.data_root):
    sc = note_score.get(nid)
    if not sc:
        continue
    lens = [float(len((c.text or "").strip()))
            for c in load_comments(cfg.data_root, nid)
            if (c.text or "").strip()]
    if len(lens) < 3:
        continue
    import statistics
    sd = statistics.stdev(lens)
    rows3.append((nid, sc["total"], sc["level"], mean(lens), sd,
                  max(lens) - min(lens), len(lens)))
rows3.sort(key=lambda x: x[4])
emit("| 笔记 | jev | 等级 | 评论数 | 均长 | 标准差 | 极差 |")
emit("| --- | ---: | --- | ---: | ---: | ---: | ---: |")
for nid, r, lv, m, sd, rg, k in rows3:
    emit(f"| `{nid[:8]}` | {r:.3f} | {lv} | {k} | {m:.0f} | {sd:.1f} | "
         f"{rg:.0f} |")
emit()
ok3 = [(x[1], x[4]) for x in rows3]
emit()
emit(f"- n = **{len(ok3)}** 篇（评论≥3条的）")
emit(f"- jev风险 ~ 长度标准差 Spearman = "
     f"**{spearman([x[0] for x in ok3], [x[1] for x in ok3]):+.3f}**")
emit()

# ================================================================ 4. 评论方向
emit("## 4. 评论方向：追问 vs 表达")
emit()
ASK = re.compile(r"(吗|么|怎么|如何|为什么|哪里|多少|求|链接|购买|在哪|有吗)")
EMO = re.compile(
    "["
    "\U0001F300-\U0001FAFF"
    "\U00002600-\U000027BF"
    "\U0001F1E6-\U0001F1FF"
    "]+"
)
rows4 = []
for nid in iter_note_ids(cfg.data_root):
    sc = note_score.get(nid)
    if not sc:
        continue
    ts = [(c.text or "") for c in load_comments(cfg.data_root, nid)
          if (c.text or "").strip()]
    if not ts:
        continue
    n_ask = sum(1 for t in ts if ASK.search(t))
    n_emo = sum(1 for t in ts if EMO.search(t) and len(t.strip()) <= 12)
    n_exp = sum(1 for t in ts if len(t.strip()) >= 25)
    rows4.append((nid, sc["total"], sc["level"], len(ts),
                  n_ask / len(ts), n_emo / len(ts), n_exp / len(ts)))
rows4.sort(key=lambda x: -x[1])
emit("| 笔记 | jev | 等级 | 评论数 | 追问率 | 短表情率 | 长表达率 |")
emit("| --- | ---: | --- | ---: | ---: | ---: | ---: |")
for nid, r, lv, k, qa, ea, xa in rows4:
    emit(f"| `{nid[:8]}` | {r:.3f} | {lv} | {k} | {qa * 100:.0f}% | "
         f"{ea * 100:.0f}% | {xa * 100:.0f}% |")
emit()
ok4 = rows4
emit()
for name, idx in (("追问率", 4), ("短表情率", 5), ("长表达率", 6)):
    emit(f"- jev风险 ~ {name} Spearman = "
         f"**{spearman([x[1] for x in ok4], [x[idx] for x in ok4]):+.3f}**")
emit()

# ================================================================ 5. 首词
emit("## 5. 评论首字分布（刷评的 linguistic 指纹）")
emit()
first = Counter()
for nid in iter_note_ids(cfg.data_root):
    for c in load_comments(cfg.data_root, nid):
        t = (c.text or "").strip()
        if len(t) >= 4:
            first[t[0]] += 1
emit("| 首字 | 次数 |")
emit("| --- | ---: |")
for w, k in first.most_common(15):
    emit(f"| `{w}` | {k} |")
emit()
q_words = sum(first[w] for w in first
              if w in ("求", "借", "出", "卖", "拼", "出", "靠", "代"))
emit()
emit(f"- 疑似黄牛首字（求/借/出/卖/拼/代/靠）：**{q_words}** 条")
emit()

out = ROOT / "out" / "brainstorm3.md"
out.write_text("\n".join(L), encoding="utf-8")
print(f"written: {out}")
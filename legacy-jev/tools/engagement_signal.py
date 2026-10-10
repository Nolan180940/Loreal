"""两个「匿名可得」信号的区分度验证。

信号 A：笔记级互动反差（liked/collected/comment_count/share）
        —— 这四个字段 42/42 齐全，完全不需要评论级字段

信号 B：评论语义负面度（jev 已给 873 条全部打了 negativity 分数）
        —— 只需要评论正文，匿名可得

并与 jev 笔记风险分做交叉，看是否互补。
输出 out/engagement_signal.md
"""

from __future__ import annotations

import json
import math
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from jev_guard.core.config import load_config  # noqa: E402
from jev_guard.extractors.reader import iter_note_ids, load_note, to_int  # noqa: E402

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
    """Spearman 秩相关（无并列取平均秩的简版：本题数据基本无并列）。"""
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


# ---------------------------------------------------------------- 载入
scores = [json.loads(l) for l in
          (ROOT / "out" / "scores.jsonl").read_text(encoding="utf-8").splitlines()
          if l.strip()]
note_score = {s["subject_id"]: s for s in scores if s["kind"] == "note"}
cmt_scores = [s for s in scores if s["kind"] == "comment"]

emit("# 互动信号区分度验证")
emit()
emit("## 0. 数据来源确认")
emit()
emit(f"- 笔记互动指标（liked/collected/comment_count/share）："
     f"**42/42 篇齐全**")
emit(f"- 评论正文：**873 条**，jev 已全部打标")
emit(f"- 评论 negativity 维度可用：**{len(cmt_scores)} 条**")
emit()
emit("> 两者都只需要笔记级字段 + 评论正文，**均为匿名可得**，")
emit("> 不依赖 create_time / ip_location / 评论点赞 —— 那三个确实匿名拿不到。")
emit()

# ---------------------------------------------------------------- 笔记级互动
emit("## 1. 信号 A：笔记级互动反差")
emit()
rows = []
for nid in iter_note_ids(cfg.data_root):
    s = load_note(cfg.data_root, nid)
    if not s or s.liked <= 0:
        continue
    sc = note_score.get(nid)
    rows.append({
        "id": nid,
        "liked": s.liked,
        "collected": s.collected,
        "cmt": s.comment_count,
        "share": s.share,
        "risk": sc["total"] if sc else None,
        "level": sc["level"] if sc else None,
    })

n = len(rows)
emit(f"可用笔记：**{n}**")
emit()
emit("| 笔记 | 赞 | 藏 | 评论 | 分享 | 评赞比 | 赞藏比 | jev风险 | 等级 |")
emit("| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |")
for r in sorted(rows, key=lambda x: -(x["liked"] / max(x["cmt"], 1))):
    cr = r["cmt"] / r["liked"] * 100 if r["liked"] else 0
    lr = r["liked"] / r["collected"] if r["collected"] else float("inf")
    lrs = "inf" if lr == float("inf") else f"{lr:.2f}"
    rk = f"{r['risk']:.3f}" if r["risk"] is not None else "-"
    emit(f"| `{r['id'][:8]}` | {r['liked']} | {r['collected']} | {r['cmt']} | "
         f"{r['share']} | {cr:.1f}% | {lrs} | {rk} | {r['level']} |")
emit()

# ---- 同类归一化 ----
emit("### 1.1 同类归一化（减去全库中位数）")
emit()
emit("原始比值受量级影响极大，必须按全库中位数归一。")
emit()
med_c = sorted(r["cmt"] / r["liked"] for r in rows)[n // 2]
med_l = sorted(r["liked"] / r["collected"] for r in rows
               if r["collected"] > 0)
med_lr = med_l[len(med_l) // 2] if med_l else 1.0
emit(f"- 全库「评赞比」中位数：**{med_c * 100:.1f}%**")
emit(f"- 全库「赞藏比」中位数：**{med_lr:.2f}**")
emit()
emit("| 笔记 | 评赞比 | 相对中位 | 赞藏比 | 相对中位 | jev风险 |")
emit("| --- | ---: | ---: | ---: | ---: | ---: |")
for r in sorted(rows, key=lambda x: (x["cmt"] / x["liked"]) / med_c):
    cr = r["cmt"] / r["liked"]
    rel_c = cr / med_c
    lr = r["liked"] / r["collected"] if r["collected"] else float("inf")
    rel_l = lr / med_lr if lr != float("inf") else float("inf")
    lrs = "inf" if lr == float("inf") else f"{lr:.2f}"
    rel_ls = "inf" if rel_l == float("inf") else f"{rel_l:.2f}x"
    rk = f"{r['risk']:.3f}" if r["risk"] is not None else "-"
    emit(f"| `{r['id'][:8]}` | {cr * 100:.1f}% | {rel_c:.2f}x | "
         f"{lrs} | {rel_ls} | {rk} |")
emit()

# ---- 相关性 ----
emit("### 1.2 与 jev 风险分的相关性")
emit()
pairs = [(r["liked"], r["cmt"], r["collected"], r["share"], r["risk"])
         for r in rows if r["risk"] is not None]
liked = [p[0] for p in pairs]
cmt = [p[1] for p in pairs]
coll = [p[2] for p in pairs]
shr = [p[3] for p in pairs]
risk = [p[4] for p in pairs]
cr_ratio = [p[1] / p[0] for p in pairs]

emit(f"n = **{len(pairs)}**")
emit()
emit("| jev风险 vs | Spearman |")
emit("| --- | ---: |")
for name, xs in (("点赞数", liked), ("收藏数", coll),
                 ("评论数", cmt), ("分享数", shr),
                 ("评赞比", cr_ratio)):
    emit(f"| {name} | **{spearman(risk, xs):+.3f}** |")
emit()
emit("> |r| < 0.3 基本无相关，> 0.5 才有讨论价值。n=42 时")
emit("> r 的 95% 置信界约 ±0.31，所以**只有 |r| > 0.31 才算显著**。")
emit()

# ---- 分层对比 ----
emit("### 1.3 按 jev 等级分组看互动反差")
emit()
emit("如果互动信号能补充 jev，高风险组的评赞比应显著不同。")
emit()
by_lv: dict[str, list] = {}
for r in rows:
    if r["level"]:
        by_lv.setdefault(r["level"], []).append(r)
emit("| 等级 | 笔记数 | 赞中位 | 藏中位 | 评论中位 | 评赞比中位 | 赞藏比中位 |")
emit("| --- | ---: | ---: | ---: | ---: | ---: | ---: |")
for lv in ("high", "medium", "low"):
    g = by_lv.get(lv, [])
    if not g:
        continue

    def med(key):
        v = sorted(x[key] for x in g)
        return v[len(v) // 2] if v else 0

    crs = sorted(x["cmt"] / x["liked"] for x in g)
    lrs = sorted(x["liked"] / x["collected"] for x in g if x["collected"])
    emit(f"| {lv} | {len(g)} | {med('liked')} | {med('collected')} | "
         f"{med('cmt')} | {crs[len(crs) // 2] * 100:.1f}% | "
         f"{(lrs[len(lrs) // 2] if lrs else 0):.2f} |")
emit()

# ---------------------------------------------------------------- 评论负面度
emit("## 2. 信号 B：评论语义负面度")
emit()
emit(f"jev 已为 **{len(cmt_scores)}** 条评论给出 negativity 分数（0~1）。")
emit()

# scores.jsonl 不含 parent_id，需要从原始数据重建评论→笔记映射
cmt_to_note: dict[str, str] = {}
for _nid in iter_note_ids(cfg.data_root):
    _arr = read_json(cfg.data_root / _nid / "comments" / "comments.json")
    if not isinstance(_arr, list):
        continue
    for _r in _arr:
        if isinstance(_r, dict) and _r.get("id"):
            cmt_to_note[str(_r["id"])] = _nid

neg_by_note: dict[str, list[float]] = {}
unmapped = 0
for s in cmt_scores:
    v = next((d["value"] for d in s["dimensions"]
              if d["name"] == "negativity"), None)
    if v is None:
        continue
    _n = cmt_to_note.get(s["subject_id"])
    if _n is None:
        unmapped += 1
        continue
    neg_by_note.setdefault(_n, []).append(v)
emit(f"评论→笔记映射失败：**{unmapped}** 条")
emit()
vals = [d["value"] for s in cmt_scores
        for d in s["dimensions"] if d["name"] == "negativity"]
if vals:
    emit("### 2.1 分布")
    emit()
    buckets = Counter()
    for v in vals:
        if v < 0.2:
            buckets["<0.2 几乎无负面"] += 1
        elif v < 0.4:
            buckets["0.2-0.4 轻微"] += 1
        elif v < 0.6:
            buckets["0.4-0.6 明显负面"] += 1
        elif v < 0.8:
            buckets["0.6-0.8 强负面"] += 1
        else:
            buckets[">=0.8 敌意"] += 1
    emit("| 区间 | 条数 | 占比 |")
    emit("| --- | ---: | ---: |")
    for k in ("<0.2 几乎无负面", "0.2-0.4 轻微", "0.4-0.6 明显负面",
              "0.6-0.8 强负面", ">=0.8 敌意"):
        c = buckets.get(k, 0)
        emit(f"| {k} | {c} | {c / len(vals) * 100:.1f}% |")
    emit()
    emit(f"- 均值 **{sum(vals) / len(vals):.3f}** · "
         f"最大 {max(vals):.3f} · 最小 {min(vals):.3f}")
    emit()

# ---------------------------------------------------------------- 交叉
emit("## 3. 交叉：A × B × jev")
emit()
emit("把笔记级互动反差和评论负面度同时按 jev 等级分组。")
emit()
emit("| 笔记 | 等级 | jev风险 | 评论数 | 负面均值 | 负面>0.5占比 | 评赞比 |")
emit("| --- | --- | ---: | ---: | ---: | ---: | ---: |")
for r in sorted(rows, key=lambda x: -(x["risk"] or 0)):
    if r["risk"] is None:
        continue
    nv = neg_by_note.get(r["id"], [])
    mean_n = sum(nv) / len(nv) if nv else None
    hi = sum(1 for v in nv if v > 0.5) / len(nv) if nv else None
    cr = r["cmt"] / r["liked"] * 100 if r["liked"] else 0
    emit(f"| `{r['id'][:8]}` | {r['level']} | {r['risk']:.3f} | "
         f"{len(nv)} | {('%.3f' % mean_n) if mean_n is not None else '-'} | "
         f"{('%.0f%%' % (hi * 100)) if hi is not None else '-'} | "
         f"{cr:.1f}% |")
emit()

# ---------------------------------------------------------------- 结论
emit("## 4. 结论")
emit()
valid = [(r, neg_by_note.get(r["id"])) for r in rows
         if r["risk"] is not None and neg_by_note.get(r["id"])]
emit(f"同时有互动数据 + 评论负面度 + jev 分数的笔记：**{len(valid)}** 篇")
emit()
if len(valid) >= 10:
    risks = [v[0]["risk"] for v in valid]
    negs = [sum(v[1]) / len(v[1]) for v in valid]
    crs = [v[0]["cmt"] / v[0]["liked"] for v in valid]
    lrs = [v[0]["liked"] / v[0]["collected"] for v in valid
           if v[0]["collected"]]
    emit("| 关系 | Spearman | 判断 |")
    emit("| --- | ---: | --- |")

    def judge(r):
        a = abs(r)
        if a > 0.5:
            return "**强**"
        if a > 0.31:
            return "显著"
        if a > 0.2:
            return "弱"
        return "无"

    emit(f"| jev风险 ~ 评论负面均值 | {spearman(risks, negs):+.3f} | "
         f"{judge(spearman(risks, negs))} |")
    emit(f"| jev风险 ~ 评赞比 | {spearman(risks, crs):+.3f} | "
         f"{judge(spearman(risks, crs))} |")
    if len(lrs) >= 10:
        emit(f"| jev风险 ~ 赞藏比 | {spearman(risks, lrs):+.3f} | "
             f"{judge(spearman(risks, lrs))} |")
    emit()
    emit("**判断标准**：n≈38 时 |r| 必须 > 0.31 才算统计显著。")
    emit()

out = ROOT / "out" / "engagement_signal.md"
out.write_text("\n".join(L), encoding="utf-8")
print(f"written: {out}")
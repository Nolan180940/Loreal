"""把人工判断与 jev 判断对比，算一致率。

三方对比：
    jev 分数分档  vs  人工判断

输出：混淆矩阵、一致率、Cohen's kappa、以及**逐条分歧**（最有价值的部分）。
分歧条目直接指向需要改进的地方 —— 阈值、权重、还是提问措辞。
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
OUT = Path(r"d:\LOreal-ai\jev\out")
DATA = Path(r"d:\LOreal-ai\data")

my = json.loads((OUT / "my_judgments.json").read_text(encoding="utf-8"))["judgments"]
scores: dict[str, dict] = {}
for line in (OUT / "scores.jsonl").read_text(encoding="utf-8").splitlines():
    if line.strip():
        r = json.loads(line)
        if r.get("kind") == "note":
            scores[r["subject_id"]] = r

rows = []
for sid, j in my.items():
    if sid not in scores:
        continue
    s = scores[sid]
    nj = DATA / sid / "content" / "note.json"
    title = ""
    if nj.is_file():
        n = json.loads(nj.read_text(encoding="utf-8"))
        title = str(n.get("作品标题") or n.get("title") or "")
    rows.append({
        "sid": sid, "title": title,
        "human": j["label"], "jev_level": s["level"],
        "total": s["total"], "reason": j["reason"],
        "dims": {d["name"]: d["value"] for d in s.get("dimensions", [])},
    })

rows.sort(key=lambda r: -r["total"])
LEVELS = ("high", "medium", "low")

conf: dict[tuple[str, str], int] = {}
for r in rows:
    conf[(r["human"], r["jev_level"])] = conf.get((r["human"], r["jev_level"]), 0) + 1

n = len(rows)
agree = sum(v for (a, b), v in conf.items() if a == b)
exact = agree / n if n else 0
# 二值化一致率：high 算正例
bin_agree = sum(v for (a, b), v in conf.items()
                if (a == "high") == (b == "high")) / n if n else 0

pe = sum(sum(v for (a, _), v in conf.items() if a == k)
         * sum(v for (_, b), v in conf.items() if b == k) for k in LEVELS) / (n * n)
kappa = (exact - pe) / (1 - pe) if pe < 1 else 0.0

tp = conf.get(("high", "high"), 0)
fn = sum(conf.get(("high", lv), 0) for lv in ("medium", "low"))
fp = sum(conf.get((lv, "high"), 0) for lv in ("medium", "low"))
prec = tp / (tp + fp) if tp + fp else 0
rec = tp / (tp + fn) if tp + fn else 0
f1 = 2 * prec * rec / (prec + rec) if prec + rec else 0

L = []
L.append("=" * 74)
L.append(f"jev 判断 vs 人工判断  n={n}")
L.append("=" * 74)
L.append("")
L.append(f"完全一致率 (3档)      {exact:.1%}")
L.append(f"二值一致率 (high/其他) {bin_agree:.1%}")
L.append(f"Cohen's kappa         {kappa:.3f}")
L.append(f"高风险精确率 {prec:.1%}  召回率 {rec:.1%}  F1 {f1:.3f}")
L.append("")
L.append("混淆矩阵（行=人工  列=jev）")
L.append(f"  {'':>8}" + "".join(f"{lv:>9}" for lv in LEVELS) + "   合计")
for h in LEVELS:
    row = [conf.get((h, j), 0) for j in LEVELS]
    L.append(f"  {h:>8}" + "".join(f"{v:>9}" for v in row) + f"{sum(row):>8}")
L.append("")

L.append("=" * 74)
L.append("分歧条目（人工 ≠ jev）—— 这是最需要看的部分")
L.append("=" * 74)
diffs = [r for r in rows if r["human"] != r["jev_level"]]
if not diffs:
    L.append("（无分歧）")
for r in diffs:
    d = r["dims"]
    L.append(f"\n{r['sid'][:8]}  人工={r['human']}  jev={r['jev_level']}"
             f"  总分={r['total']:.3f}")
    L.append(f"  标题: {r['title'][:44]}")
    L.append(f"  维度: " + " ".join(f"{k}={v:.2f}" for k, v in d.items()))
    L.append(f"  人工理由: {r['reason'][:100]}")

L.append("")
L.append("=" * 74)
L.append("逐条明细")
L.append("=" * 74)
for r in rows:
    mark = "OK " if r["human"] == r["jev_level"] else "DIF"
    L.append(f"  {mark} {r['sid'][:8]} 总分={r['total']:.3f} "
             f"人工={r['human']:<6} jev={r['jev_level']:<6} {r['title'][:32]}")

(OUT / "accuracy_report.txt").write_text("\n".join(L), encoding="utf-8")
print("\n".join(L[:20]))
print(f"\n[written] {OUT / 'accuracy_report.txt'}")
print(f"分歧 {len(diffs)}/{n} 条")
"""校准检查：Layer 2 阈值该用「纯整齐度」还是「整齐且短」。

实现里 SPREAD 只看标准差（整齐度），不看平均长度。所以要验证：
加上「平均长度 < 15」这个条件，AUC 会不会更高？
输出 out/spread_calibration.md
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from jev_guard.core.config import load_config  # noqa: E402
from jev_guard.extractors.reader import (  # noqa: E402
    comment_length_spread, iter_note_ids,
)

cfg = load_config()
L: list[str] = []


def emit(s: str = "") -> None:
    L.append(s)


def auc(scores: list[float], labels: list[bool]) -> float:
    pos = [s for s, y in zip(scores, labels) if y]
    neg = [s for s, y in zip(scores, labels) if not y]
    if not pos or not neg:
        return 0.5
    win = sum(1 for p in pos for q in neg if p > q)
    tie = sum(1 for p in pos for q in neg if p == q)
    return (win + 0.5 * tie) / (len(pos) * len(neg))


HUMAN = json.loads((ROOT / "out" / "my_judgments.json")
                   .read_text(encoding="utf-8"))["judgments"]
scores = [json.loads(l) for l in
          (ROOT / "out" / "scores.jsonl").read_text(encoding="utf-8").splitlines()
          if l.strip()]
note_score = {s["subject_id"]: s for s in scores if s["kind"] == "note"}

emit("# Layer 2 阈值校准")
emit()

rows = []
for nid in iter_note_ids(cfg.data_root):
    if nid not in note_score:
        continue
    sp = comment_length_spread(cfg.data_root, nid)
    if sp["sd"] is None:
        continue
    rows.append((nid, sp["sd"], sp["mean"], sp["n"],
                 HUMAN.get(nid, {}).get("label"),
                 note_score[nid]["level"], note_score[nid]["total"]))

emit(f"可用笔记：**{len(rows)}** 篇（评论 ≥3 条）")
emit()

# ---- 逐条明细 ----
emit("## 1. 逐条明细")
emit()
emit("| 笔记 | 人工 | jev | SD | 均长 | 评论数 | SD<7 |")
emit("| --- | --- | ---: | ---: | ---: | ---: | :-: |")
for nid, sd, mean, n, h, lv, t in sorted(rows, key=lambda x: x[1]):
    emit(f"| `{nid[:8]}` | {h or '-'} | {lv} | {sd:.1f} | {mean:.0f} | {n} | "
         f"{'⚠' if sd < 7 else ''} |")
emit()

# ---- AUC 对比 ----
emit("## 2. AUC 对比（人工 high vs 其他）")
emit()
lab = [r[4] == "high" for r in rows if r[4]]
sub = [r for r in rows if r[4]]
emit(f"- n = **{len(sub)}** 条有��工标签")
emit()

emit("| 判据 | AUC | 说明 |")
emit("| --- | ---: | --- |")
emit(f"| 仅 SD（当前实现） | "
     f"**{auc([-r[1] for r in sub], lab):.3f}** | 纯整齐度 |")
emit(f"| 仅 均长 | {auc([-r[2] for r in sub], lab):.3f} | 一阶信号 |")
for mc in (10.0, 15.0, 20.0):
    v = [(-r[1] if r[2] < mc else 10.0) for r in sub]
    emit(f"| SD<7 且 均长<{mc:.0f} | {auc(v, lab):.3f} | 加上长度条件 |")
emit()

# ---- 阈值扫描 ----
emit("## 3. SD 阈值扫描")
emit()
emit("| 阈值 | 命中数 | 其中人工high | 命中准确率 |")
emit("| ---: | ---: | ---: | ---: |")
for th in (5.0, 6.0, 7.0, 8.0, 10.0, 12.0, 15.0):
    hit = [r for r in sub if r[1] < th]
    if not hit:
        continue
    hit_h = sum(1 for r in hit if r[4] == "high")
    emit(f"| {th:.0f} | {len(hit)} | {hit_h} | {hit_h / len(hit) * 100:.0f}% |")
emit()
emit("「命中准确率」= 命中的人里有多少真被判high。")
emit("越高说明这个告警越准（低误报）。")
emit()

out = ROOT / "out" / "spread_calibration.md"
out.write_text("\n".join(L), encoding="utf-8")
print(f"written: {out}")
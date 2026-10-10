"""敏感性实验：如果把 SD 提升为一等维度参与加权，会发生什么。

纯离线实验，不改任何生产代码。
映射：spread_risk = clamp(1 - SD/14, 0, 1)   # SD=7(告警阈值) -> 0.5
备选：binary（flag -> 1.0，否则 0.0）
权重扫描：0(基线) / 0.1 / 0.2 / 0.3
评估：24 条人工标签上的三分类一致率、二值一致率、high P/R/F1、翻档数
输出 out/promotion_experiment.md
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from jev_guard.core.config import load_config  # noqa: E402
from jev_guard.core.models import (  # noqa: E402
    DimensionScore, Label, SubjectKind,
)
from jev_guard.core.scoring import RuleEngine  # noqa: E402
from jev_guard.extractors.reader import (  # noqa: E402
    comment_length_spread, iter_note_ids, load_note,
)
from jev_guard.pipeline.score import build_index  # noqa: E402

cfg = load_config()
L: list[str] = []


def emit(s: str = "") -> None:
    L.append(s)


idx = build_index(ROOT / "out" / "labels_all.jsonl")
my = json.loads((ROOT / "out" / "my_judgments.json")
                .read_text(encoding="utf-8"))["judgments"]


class W:
    """WeightConfig 的替身，多一个 spread 字段。"""

    def __init__(self, spread: float) -> None:
        self.has_risk = 0.35
        self.exaggeration = 0.30
        self.is_ad = 0.25
        self.is_cta = 0.10
        self.spread = spread


def spread_risk(nid: str, mode: str) -> float | None:
    sp = comment_length_spread(cfg.data_root, nid)
    if sp["sd"] is None:
        return None
    if mode == "binary":
        return 1.0 if sp["spread_flag"] else 0.0
    return max(0.0, min(1.0, 1.0 - sp["sd"] / 14.0))


def run(weight: float, mode: str = "linear") -> dict[str, object]:
    eng = RuleEngine(cfg.thresholds, W(weight))
    out = {}
    for nid in iter_note_ids(cfg.data_root):
        lab = idx.get(nid)
        if lab is None:
            continue
        sr = spread_risk(nid, mode)
        dims = lab.dimensions
        if sr is not None:
            dims = dims + (DimensionScore(name="spread", value=sr),)
        lab2 = Label(subject_id=nid, kind=SubjectKind.NOTE,
                     dimensions=dims, model=lab.model)
        subj = load_note(cfg.data_root, nid)
        rs = eng.evaluate(lab2, text=subj.text_for_model if subj else "")
        out[nid] = rs
    return out


emit("# 敏感性实验：SD 提升为一等维度")
emit()

base = run(0.0)
n_no_sd = sum(1 for k in base if spread_risk(k, "linear") is None)
emit(f"- 有标签的笔记：**{len(base)}** 篇，其中 **{n_no_sd}** 篇评论 <3 条"
     f"（无 SD，该维度对它们永远缺席）")
emit()

emit("## 1. 权重扫描（linear 映射，24 条人工标签）")
emit()
emit("| spread权重 | 三分类一致 | 二值一致 | high精确 | high召回 | F1 | 翻档数 |")
emit("| ---: | ---: | ---: | ---: | ---: | ---: | ---: |")
for w in (0.0, 0.1, 0.2, 0.3):
    got = run(w)
    ids = [k for k in my if k in got and k in base]
    n = len(ids)
    exact = sum(1 for k in ids if got[k].level.value == my[k]["label"]) / n
    binag = (sum(1 for k in ids
                 if (got[k].level.value == "high") == (my[k]["label"] == "high"))
             / n)
    tp = sum(1 for k in ids if got[k].level.value == "high"
             and my[k]["label"] == "high")
    fp = sum(1 for k in ids if got[k].level.value == "high"
             and my[k]["label"] != "high")
    fn = sum(1 for k in ids if got[k].level.value != "high"
             and my[k]["label"] == "high")
    prec = tp / (tp + fp) if tp + fp else 0.0
    rec = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * prec * rec / (prec + rec) if prec + rec else 0.0
    flips = sum(1 for k in ids if got[k].level != base[k].level)
    mark = "（基线）" if w == 0.0 else ""
    emit(f"| {w} {mark} | {exact * 100:.1f}% | {binag * 100:.1f}% | "
         f"{prec * 100:.0f}% | {rec * 100:.0f}% | {f1:.3f} | {flips} |")
emit()

emit("## 2. binary 映射（flag -> 1.0）")
emit()
emit("| spread权重 | 三分类一致 | 二值一致 | 翻档数 |")
emit("| ---: | ---: | ---: | ---: |")
for w in (0.1, 0.2):
    got = run(w, "binary")
    ids = [k for k in my if k in got and k in base]
    n = len(ids)
    exact = sum(1 for k in ids if got[k].level.value == my[k]["label"]) / n
    binag = (sum(1 for k in ids
                 if (got[k].level.value == "high") == (my[k]["label"] == "high"))
             / n)
    flips = sum(1 for k in ids if got[k].level != base[k].level)
    emit(f"| {w} | {exact * 100:.1f}% | {binag * 100:.1f}% | {flips} |")
emit()

emit("## 3. 翻档明细（w=0.2, linear）")
emit()
got = run(0.2)
ids = [k for k in my if k in got and k in base]
flips = [(k, base[k].level.value, got[k].level.value, my[k]["label"])
         for k in ids if got[k].level != base[k].level]
if flips:
    emit("| 笔记 | 人工 | 基线 | 加SD后 | 变化 |")
    emit("| --- | --- | --- | --- | --- |")
    for k, b, a, h in sorted(flips, key=lambda x: x[2] != x[3]):
        good = "✅ 修正" if a == h and b != h else (
            "❌ 误伤" if b == h and a != h else "中性")
        emit(f"| `{k[:8]}` | {h} | {b} | {a} | {good} |")
else:
    emit("（无翻档）")
emit()

emit("## 3. 结论判据")
emit()
emit("- 若一致率下降或出现「误伤」：今天不该提升，等独立标注再说")
emit("- 若一致率上升：也要打折 —— 人工标签与 jev 相关（AUC=1.000），")
emit("  上升可能只是过拟合我自己的判断")

out = ROOT / "out" / "promotion_experiment.md"
out.write_text("\n".join(L), encoding="utf-8")
print(f"written: {out}")
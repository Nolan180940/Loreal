"""验证 Layer 2 接入后Layer 1 是否被污染。

对比 scores_before.jsonl 与 scores.jsonl：
  - total 必须逐条完全一致（这是方案 A 的核心承诺）
  - level 必须完全一致
  - 新增字段应有值
输出 out/layer2_impact.md
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
L: list[str] = []


def emit(s: str = "") -> None:
    L.append(s)


def load(p: Path) -> dict[str, dict]:
    if not p.is_file():
        return {}
    out = {}
    for line in p.read_text(encoding="utf-8").splitlines():
        if line.strip():
            r = json.loads(line)
            out[r["subject_id"]] = r
    return out


before = load(ROOT / "out" / "scores_before.jsonl")
after = load(ROOT / "out" / "scores.jsonl")

emit("# Layer 2 接入影响评估")
emit()
emit(f"- 接入前：**{len(before)}** 条")
emit(f"- 接入后：**{len(after)}** 条")
emit()

# ---- 1. total / level 是否被污染 ----
emit("## 1. Layer 1 不变量检查（核心）")
emit()
notes_b = {k: v for k, v in before.items() if v.get("kind") == "note"}
notes_a = {k: v for k, v in after.items() if v.get("kind") == "note"}

common = [k for k in notes_b if k in notes_a]
total_diff = [k for k in common
              if abs(notes_b[k]["total"] - notes_a[k]["total"]) > 1e-9]
level_diff = [k for k in common if notes_b[k]["level"] != notes_a[k]["level"]]

emit(f"- 可对比笔记：**{len(common)}** 篇")
emit(f"- `total` 变化：**{len(total_diff)}** 条")
emit(f"- `level` 变化：**{len(level_diff)}** 条")
emit()
if total_diff or level_diff:
    emit("**⚠ 有变化，说明 Layer 2 污染了 Layer 1**")
    for k in total_diff[:10]:
        emit(f"  - `{k[:8]}` {notes_b[k]['total']} -> {notes_a[k]['total']}")
else:
    emit("**✅ `total` 与 `level` 逐条完全一致 —— Layer 1 未被污染**")
emit()

# ---- 2. Layer 2 覆盖情况 ----
emit("## 2. Layer 2 字段覆盖")
emit()
has_sd = [k for k, v in notes_a.items() if v.get("spread_sd") is not None]
flagged = [k for k, v in notes_a.items() if v.get("spread_flag")]
emit(f"- 有 `spread_sd` 的笔记：**{len(has_sd)}/{len(notes_a)}**")
emit(f"- 触发告警（SD < 7）：**{len(flagged)}** 篇")
emit()
emit("| 笔记 | total | level | 评论数 | 均长 | SD | L2告警 |")
emit("| --- | ---: | --- | ---: | ---: | ---: | :-: |")
for k in sorted(flagged, key=lambda x: notes_a[x].get("spread_sd") or 0):
    v = notes_a[k]
    emit(f"| `{k[:8]}` | {v['total']:.3f} | {v['level']} | "
         f"{v.get('spread_n')} | {v.get('spread_mean')} | "
         f"{v.get('spread_sd')} | ⚠ |")
emit()

# ---- 3. 交叉：两层是否独立 ----
emit("## 3. 两层交叉（关键：看是否互补）")
emit()
emit("| 组合 | 篇数 | 说明 |")
emit("| --- | ---: | --- |")
both = [k for k in flagged if notes_a[k]["level"] == "high"]
only_l1 = [k for k in flagged if notes_a[k]["level"] != "high"]
only_l2 = [k for k in has_sd
           if not notes_a[k]["spread_flag"] and notes_a[k]["level"] == "high"]
neither = [k for k in has_sd
           if not notes_a[k]["spread_flag"] and notes_a[k]["level"] != "high"]
emit(f"| L1=high + L2告警 | {len(both)} | 内容可疑 **且** 评论区整齐 |")
emit(f"| 仅 L2 告警 | {len(only_l1)} | 内容判低风险，但评论区整齐 |")
emit(f"| 仅 L1=high | {len(only_l2)} | 内容可疑，但评论区自然 |")
emit(f"| 都无 | {len(neither)} | |")
emit()
if only_l1:
    emit("### 仅 L2 告警（Layer 2 的独立贡献）")
    emit()
    emit("这些是 Layer 1 抓不到、但评论区结构可疑的：")
    emit()
    for k in only_l1:
        v = notes_a[k]
        emit(f"- `{k[:8]}` total={v['total']:.3f} ({v['level']}) "
             f"SD={v.get('spread_sd')} 均长={v.get('spread_mean')}")
    emit()
if both:
    emit("### 两层同时告警（互证，可信度最高）")
    emit()
    for k in both:
        v = notes_a[k]
        emit(f"- `{k[:8]}` total={v['total']:.3f} SD={v.get('spread_sd')}")
    emit()

# ---- 4. 准确率对比 ----
emit("## 4. 准确率是否变化")
emit()
HUMAN = ROOT / "out" / "my_judgments.json"
if HUMAN.is_file():
    my = json.loads(HUMAN.read_text(encoding="utf-8"))["judgments"]
    ids = [k for k in my if k in notes_a and k in notes_b]
    if ids:
        lv_b = "high"
        agree_b = sum(1 for k in ids
                      if (notes_b[k]["level"] == lv_b)
                      == (my[k]["label"] == lv_b))
        agree_a = sum(1 for k in ids
                      if (notes_a[k]["level"] == lv_b)
                      == (my[k]["label"] == lv_b))
        n = len(ids)
        emit(f"人工标签可比：**{n}** 条")
        emit()
        emit("| 指标 | 接入前 | 接入后 |")
        emit("| --- | ---: | ---: |")
        emit(f"| 二值一致率 | {agree_b / n * 100:.1f}% | "
             f"{agree_a / n * 100:.1f}% |")
        emit()
        if agree_a == agree_b:
            emit("**一致率未变 —— 符合方案 A 的设计承诺**")
        else:
            emit("**⚠ 一致率变了，需排查**")
emit()

out = ROOT / "out" / "layer2_impact.md"
out.write_text("\n".join(L), encoding="utf-8")
print(f"written: {out}")
# -*- coding: utf-8 -*-
"""新配置（high=0.60 + 3 个新信号）与 gold 的最终对比。"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tools"))

from eval_round1 import LABELS, kappa, prf       # noqa: E402

rows = {r["note_id"][:8]: r
        for r in (json.loads(l) for l in
                  (ROOT / "out" / "scores.jsonl")
                  .read_text(encoding="utf-8").splitlines() if l.strip())}
gold = {k: v for k, v in LABELS.items() if k in rows}

L: list[str] = []
w = L.append
w("# 1~5 改动后的最终对比（新配置 vs AI 判读）+ 451 bug 修复")
w("")
w("配置：`high=0.60` · `low=0.30` · 16 个启用信号（nickname_dup_rate 禁用）")
w(f"运行：`{next(iter(rows.values())).get('run_id')}` · "
  f"`{next(iter(rows.values())).get('config_hash')}`")
w("")

# ---- 三档 / 二值一致 ----
g3 = [gold[k] for k in sorted(gold)]
p3 = [rows[k]["level"] for k in sorted(gold)]
gh = [g == "high" for g in g3]
ph = [p == "high" for p in p3]
a3 = sum(1 for a, b in zip(g3, p3) if a == b) / len(g3)
ah = sum(1 for a, b in zip(gh, ph) if a == b) / len(gh)
kk = kappa(g3, p3)
TP = sum(1 for a, b in zip(gh, ph) if a and b)
FP = sum(1 for a, b in zip(gh, ph) if not a and b)
FN = sum(1 for a, b in zip(gh, ph) if a and not b)
prec, rec, f1 = prf(TP, FP, FN)

w("## 指标（vs 第一轮 default）")
w("")
w("| 指标 | 第一轮（high=0.70） | 本轮（high=0.60） |")
w("|---|---:|---:|")
w(f"| 二值一致率 | 97.5% | **{ah:.1%}** |")
w(f"| 三档一致率 | 75.0% | **{a3:.1%}** |")
w(f"| kappa | 0.560 | **{kk:.3f}** |")
w(f"| 高风险 F1 | 0.923 | **{f1:.3f}** |")
w(f"| 高风险 P / R | 1.000 / 0.857 | **{prec:.3f} / {rec:.3f}** |")
w("")
w("> 阈值 0.60 只在**同一批 40 篇**上调过，属「在考卷上改答案」。")
w("> 换一批数据验证前仍是候选值 —— 但方向是对的（稀释区）。")
w("")

# ---- 混淆 ----
w("## 混淆（gold × 预测）")
w("")
w("| gold \\ 预测 | low | medium | high |")
w("|---|---:|---:|---:|")
for g in ("low", "medium", "high"):
    r = [sum(1 for a, b in zip(g3, p3) if a == g and b == p)
         for p in ("low", "medium", "high")]
    w(f"| **{g}** | {r[0]} | {r[1]} | {r[2]} |")
w("")

# ---- 残余分歧 ----
w("## 残余分歧")
w("")
w("| note | gold | 预测 | total | is_ad | has_risk | exag | cta | 标题 |")
w("|---|---|---|---:|---:|---:|---:|---:|---|")
for k in sorted(gold):
    if rows[k]["level"] == gold[k]:
        continue
    dd = {x["name"]: x["value"]
          for x in (rows[k].get("dimensions") or {}).values()
          if isinstance(x, dict)}
    title = str((rows[k].get("note") or {}).get("title") or "")[:20]
    w(f"| `{k}` | {gold[k]} | {rows[k]['level']} | {rows[k]['total']:.3f} "
      f"| {dd.get('is_ad', '-')} | {dd.get('has_risk', '-')} "
      f"| {dd.get('exaggeration', '-')} | {dd.get('is_cta', '-')} | {title} |")
w("")

# ---- 新信号在真实产物里的表现 ----
w("## 新信号的实际贡献（本轮的信号分布）")
w("")
sig_names = ["tag_count", "structure_markers", "cta_lexicon"]
w("| 信号 | 非缺失 | 非零 | max | 均 |")
w("|---|---:|---:|---:|---:|")
for s in sig_names:
    vs = [float(r["signals"][s]["value"]) for r in rows.values()
          if s in (r.get("signals") or {})
          and not r["signals"][s].get("missing")]
    if vs:
        w(f"| `{s}` | {len(vs)} | {sum(1 for v in vs if v > 0)} | "
          f"{max(vs):.2f} | {sum(vs) / len(vs):.2f} |")
    else:
        w(f"| `{s}` | 0 | 0 | — | — |")
w("")
# 禁用确认
w("## 禁用确认")
w("")
disabled_present = [r["note_id"][:8] for r in rows.values()
                    if "nickname_dup_rate" in (r.get("signals") or {})]
w(f"- `nickname_dup_rate` 出现在产物里的篇数：**{len(disabled_present)}**"
  f"（应为 0）")
w("")

# ---- 语义层健康 ----
sem_fail = sum(1 for r in rows.values() if r.get("semantic_ok") is False)
w("## 语义层健康")
w("")
w(f"- `semantic_ok=false` 的篇数：**{sem_fail}**（应为 0）")
w("")

out = ROOT / "docs" / "JEV2_FINAL_AFTER_CHANGES.md"
out.write_text("\n".join(L), encoding="utf-8")
print(f"wrote {out}")
print(f"二值={ah:.1%} 三档={a3:.1%} kappa={kk:.3f} F1={f1:.3f} "
      f"sem_fail={sem_fail} disabled_leak={len(disabled_present)}")

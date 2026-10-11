# -*- coding: utf-8 -*-
"""验证 1~5 改动：新信号真实分布 + 禁用生效 + 阈值效果。输出写文件。"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tools"))

from eval_round1 import LABELS, auc, kappa, prf          # noqa: E402
from jev2.config import config_hash, load_config          # noqa: E402
from jev2.fuse.engine import EngineConfig, FuseEngine     # noqa: E402
from jev2.loader import load_all                          # noqa: E402
from jev2.signals import (ACTIVE_SIGNALS, ALL_SIGNALS,    # noqa: E402
                          INACTIVE_BY_DEFAULT, SignalContext, SignalSet)

cfg = load_config()
notes, _ = load_all(cfg.paths.data_root)
ss = SignalSet(ctx=SignalContext(min_samples=cfg.signals.min_samples))

L: list[str] = []
w = L.append
w("# 1~5 改动验证")
w("")
w(f"- 注册信号 `ALL_SIGNALS`：{len(ALL_SIGNALS)} 个")
w(f"- 默认启用 `ACTIVE_SIGNALS`：{len(ACTIVE_SIGNALS)} 个")
w(f"- 默认禁用 `INACTIVE_BY_DEFAULT`：{sorted(INACTIVE_BY_DEFAULT)}")
w(f"- config high = {cfg.fuse.high}  low = {cfg.fuse.low}")
w(f"- config_hash = {config_hash(cfg)}")
w("")

# 新信号的真实值分布
NEW = ["tag_count", "structure_markers", "cta_lexicon"]
w("## 新信号在 40 篇上的表现")
w("")
w("| 信号 | 非缺失 | 非零 | min | 中位 | max | 均 |")
w("|---|---:|---:|---:|---:|---:|---:|")
vals: dict[str, list[float]] = {n: [] for n in NEW}
miss: dict[str, int] = {n: 0 for n in NEW}
for n in notes:
    for k, r in ss.compute(n).items():
        if k not in NEW:
            continue
        if r.missing:
            miss[k] += 1
        else:
            vals[k].append(r.value)
for k in NEW:
    vs = vals[k]
    if vs:
        s = sorted(vs)
        w(f"| `{k}` | {len(vs)} | {sum(1 for v in vs if v > 0)} | {min(vs):.2f} "
          f"| {s[len(s) // 2]:.2f} | {max(vs):.2f} | {sum(vs) / len(vs):.2f} |")
    else:
        w(f"| `{k}` | 0 | 0 | — | — | — | — |")
w("")

# 单信号 AUC（用 gold 复核）
rows = {r["note_id"][:8]: r
        for r in (json.loads(l) for l in
                  (ROOT / "out" / "scores.jsonl")
                  .read_text(encoding="utf-8").splitlines() if l.strip())}
gold = {k: v for k, v in LABELS.items() if k in rows}
ghi = {k: gold[k] == "high" for k in gold}
gmed = {k: gold[k] in ("high", "medium") for k in gold}
per: dict[str, list] = {}
for n in notes:
    nid8 = n.note_id[:8]
    if nid8 not in gold:
        continue
    for k, r in ss.compute(n).items():
        if k in NEW and not r.missing:
            per.setdefault(k, []).append((r.value, ghi[nid8], gmed[nid8]))

w("## 新信号 AUC 复核（应与原型一致）")
w("")
w("| 信号 | AUC(vs high) | AUC(vs high+medium) |")
w("|---|---:|---:|")
for k in NEW:
    pts = per.get(k, [])
    if not pts:
        w(f"| `{k}` | — | — |")
        continue
    a1 = auc([v for v, a, _ in pts if a], [v for v, a, _ in pts if not a])
    a2 = auc([v for v, _, b in pts if b], [v for v, _, b in pts if not b])
    w(f"| `{k}` | {a1:.3f} | {a2:.3f} |")
w("")

# 阈值 0.60 的效果（用已存的 scores.jsonl 离线算，含 veto）
def dims_of(row):
    d = {}
    for x in (row.get("dimensions") or {}).values():
        if isinstance(x, dict):
            d[x["name"]] = float(x.get("value") or 0)
    return d


W0 = {"has_risk": 0.35, "exaggeration": 0.30, "is_ad": 0.25, "is_cta": 0.10}


def total_with_veto(dd):
    if dd.get("is_ad", 0) >= 0.85:
        return 1.0
    acc = ws = 0.0
    for k, x in W0.items():
        if k in dd:
            acc += dd[k] * x
            ws += x
    return acc / ws if ws else 0.0


for ht in (0.70, 0.60):
    p3, phi, g3 = [], [], []
    for k in sorted(gold):
        t = total_with_veto(dims_of(rows[k]))
        lv = "high" if t >= ht else ("low" if t <= 0.30 else "medium")
        p3.append(lv)
        phi.append(lv == "high")
        g3.append(gold[k])
    gh = [g == "high" for g in g3]
    a3 = sum(1 for a, b in zip(g3, p3) if a == b) / len(g3)
    ah = sum(1 for a, b in zip(gh, phi) if a == b) / len(gh)
    kk = kappa(g3, p3)
    TP = sum(1 for a, b in zip(gh, phi) if a and b)
    FP = sum(1 for a, b in zip(gh, phi) if not a and b)
    FN = sum(1 for a, b in zip(gh, phi) if a and not b)
    _, _, f1 = prf(TP, FP, FN)
    w(f"- `high={ht:.2f}`：二值 {ah:.1%} · 三档 {a3:.1%} · "
      f"kappa {kk:.3f} · F1 {f1:.3f}")
w("")

out = ROOT / "docs" / "JEV2_CHANGES_VERIFY.md"
out.write_text("\n".join(L), encoding="utf-8")
print(f"wrote {out}")
print(f"signals: all={len(ALL_SIGNALS)} active={len(ACTIVE_SIGNALS)} "
      f"inactive={len(INACTIVE_BY_DEFAULT)}")

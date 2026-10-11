"""离线权重扫描 —— 调 fuse 权重**不用重跑模型**。

为什么免费
----------
``scores.jsonl`` 里存了全部中间值（4 个语义维度 + 19 个信号值），
所以换任何权重组合都只是重新做一次加权平均，**零模型调用**。

用法
----
    python jev2/tools/sweep_signal_weights.py              # 默认扫描
    python jev2/tools/sweep_signal_weights.py --json out.json

⚠️ 结果是在 40 篇自评基准上算的（非真人 ground truth），
   属于「在考卷上改答案」——选出的权重是候选值。
"""
from __future__ import annotations

import argparse
import itertools
import json
import pathlib
import sys

_HERE = pathlib.Path(__file__).resolve()
_ROOT = _HERE.parents[2]
sys.path.insert(0, str(_ROOT / "jev2" / "src"))
sys.path.insert(0, str(_HERE.parent))

from eval_round1 import LABELS, l2_agg  # noqa: E402

from jev2.fuse.rules import SCORING_SIGNALS  # noqa: E402

#: 语义权重（继承 legacy-jev，不在扫描范围内 —— 没有 ground truth 不动它）
W_SEM = {"has_risk": 0.35, "exaggeration": 0.30, "is_ad": 0.25, "is_cta": 0.10}

_BASE_SUM = sum(w for w, _ in SCORING_SIGNALS.values())


def scaled(target: float) -> dict[str, float]:
    """把 SCORING_SIGNALS 的比例等比缩放到总权重 = target。"""
    f = target / _BASE_SUM
    return {k: w * f for k, (w, _) in SCORING_SIGNALS.items()}


def auc(pos: list[float], neg: list[float]) -> float:
    if not pos or not neg:
        return float("nan")
    wins = ties = 0
    for a, b in itertools.product(pos, neg):
        if a > b:
            wins += 1
        elif a == b:
            ties += 1
    return (wins + ties / 2) / (len(pos) * len(neg))


def kappa3(a: list[str], b: list[str]) -> float:
    levels = ("low", "medium", "high")
    n = len(a)
    if not n:
        return float("nan")
    po = sum(1 for x, y in zip(a, b) if x == y) / n
    pe = sum((a.count(lv) / n) * (b.count(lv) / n) for lv in levels)
    return (po - pe) / (1 - pe) if pe < 1 else float("nan")


def fuse(row: dict, *, w_sig: dict[str, float], high: float, low: float,
         veto_t: float = 0.85) -> tuple[float, str, bool]:
    """与引擎同逻辑的离线融合。"""
    dims = {k: float(v["value"])
            for k, v in (row.get("dimensions") or {}).items()
            if isinstance(v, dict) and v.get("value") is not None}
    if dims.get("is_ad", 0.0) >= veto_t:
        return 1.0, "high", True

    num = den = 0.0
    for k, w in W_SEM.items():
        if k in dims:
            num += dims[k] * w
            den += w
    for k, w in w_sig.items():
        s = (row.get("signals") or {}).get(k) or {}
        if isinstance(s, dict) and not s.get("missing") and s.get("value") is not None:
            num += float(s["value"]) * w
            den += w
    total = num / den if den else 0.0
    return total, ("high" if total >= high else
                   "low" if total <= low else "medium"), False


def evaluate(rows: dict, *, w_sig: dict, high: float,
             low: float) -> dict:
    tp = fp = fn = tn = 0
    ga, pa, flips = [], [], []
    for nid8, gold in LABELS.items():
        row = rows.get(nid8)
        if not row:
            continue
        total, lv, _ = fuse(row, w_sig=w_sig, high=high, low=low)
        g, p = gold == "high", lv == "high"
        tp += g and p
        fp += (not g) and p
        fn += g and (not p)
        tn += (not g) and (not p)
        ga.append(gold)
        pa.append(lv)
        if g and not p:
            flips.append(f"{nid8}(high→{lv}@{total:.3f})")
    n = len(ga)
    prec = tp / (tp + fp) if tp + fp else 0.0
    rec = tp / (tp + fn) if tp + fn else 0.0
    return {
        "n": n, "binary": (tp + tn) / n if n else 0.0,
        "kappa": kappa3(ga, pa), "agree3": sum(
            1 for x, y in zip(ga, pa) if x == y) / n if n else 0.0,
        "f1": 2 * prec * rec / (prec + rec) if prec + rec else 0.0,
        "miss_high": fn, "flips": flips,
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="离线权重扫描（零模型调用）")
    ap.add_argument("--scores", default=str(_ROOT / "jev2" / "out"
                                            / "scores.jsonl"))
    ap.add_argument("--json", help="把结果写成 JSON")
    ap.add_argument("--quick", action="store_true", help="只扫信号总量")
    args = ap.parse_args(argv)

    path = pathlib.Path(args.scores)
    if not path.is_file():
        print(f"[X] 找不到 {path}，先跑 jev2 judge", file=sys.stderr)
        return 2
    rows = {r["note_id"][:8]: r
            for r in (json.loads(l) for l in
                      path.read_text(encoding="utf-8").splitlines()
                      if l.strip())}
    matched = sum(1 for k in LABELS if k in rows)
    print(f"标注 {len(LABELS)} 篇 · 匹配 {matched} 篇 · scores {len(rows)} 行")
    print()

    grid = []
    for target in (0.0, 0.10, 0.15, 0.20, 0.25, 0.30, 0.40, 0.60):
        if args.quick and target not in (0.0, 0.15, 0.20, 0.25, 0.40):
            continue
        for high in (0.55, 0.60, 0.65):
            grid.append((target, high))

    print(f"{'信号总量':>9}{'high':>7}{'二值':>8}{'kappa':>8}"
          f"{'三档':>8}{'F1':>7}{'漏high':>7}")
    print("-" * 56)
    best = None
    results = []
    for target, high in grid:
        r = evaluate(rows, w_sig=scaled(target), high=high, low=0.30)
        results.append({"signal_total": target, "high": high, **r})
        star = ""
        key = (r["binary"], r["kappa"])
        if best is None or key > best[0]:
            best = (key, target, high)
            star = "  ←"
        print(f"{target:>9.2f}{high:>7.2f}{r['binary']:>8.1%}"
              f"{r['kappa']:>8.3f}{r['agree3']:>8.1%}{r['f1']:>7.3f}"
              f"{r['miss_high']:>7}{star}")

    print()
    print(f"最优（按二值→kappa）: 信号总量 {best[1]:.2f} · high {best[2]:.2f}")
    worst = [r for r in results if r["flips"]]
    if worst:
        print()
        print("=== 有漏判的组合（gold=high 被判掉）===")
        for r in worst[:6]:
            print(f"  总量 {r['signal_total']:.2f} high {r['high']:.2f}: "
                  f"{', '.join(r['flips'][:3])}")

    if args.json:
        pathlib.Path(args.json).write_text(
            json.dumps(results, ensure_ascii=False, indent=2),
            encoding="utf-8")
        print(f"\n[saved] {args.json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

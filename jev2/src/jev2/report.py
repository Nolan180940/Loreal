"""报告：把 ``scores.jsonl`` 变成人看得懂的东西。

输出三块
--------
1. **总览** —— 档位分布、分数区间、信号缺失情况
2. **风险清单** —— 按分数排序，附「主要因为什么」
3. **信号明细** —— 每个信号在全体上的分布（判断它有没有区分度）

设计取舍
--------
报告是**只读**的，不触发任何模型调用 —— 调阈值时想反复看结果，
不该每次都花钱重新判定。所以所有中间值（维度分、信号值、规则痕迹）
都存进了 ``scores.jsonl``，报告只做聚合。
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable

from .core.types import Level


def _num(x: Any, default: float = 0.0) -> float:
    try:
        return float(x)
    except (TypeError, ValueError):
        return default


def _quantile(xs: list[float], q: float) -> float:
    if not xs:
        return 0.0
    s = sorted(xs)
    if len(s) == 1:
        return s[0]
    pos = q * (len(s) - 1)
    lo, hi = int(pos), min(int(pos) + 1, len(s) - 1)
    frac = pos - lo
    return s[lo] * (1 - frac) + s[hi] * frac


# --------------------------------------------------------------- 聚合

def summarize(rows: Iterable[dict[str, Any]]) -> dict[str, Any]:
    """整体统计。"""
    rows = list(rows)
    if not rows:
        return {"total": 0}

    totals = [_num(r.get("total")) for r in rows]
    levels: dict[str, int] = {}
    vetoed = 0
    sem_fail = 0
    for r in rows:
        lv = r.get("level", "?")
        levels[lv] = levels.get(lv, 0) + 1
        if r.get("vetoed_by"):
            vetoed += 1
        if r.get("semantic_ok") is False:
            sem_fail += 1

    # 每个语义维度 / 统计信号的分布
    dim_vals: dict[str, list[float]] = {}
    sig_vals: dict[str, list[float]] = {}
    sig_missing: dict[str, int] = {}
    for r in rows:
        for name, d in (r.get("dimensions") or {}).items():
            if isinstance(d, dict) and d.get("value") is not None:
                dim_vals.setdefault(name, []).append(_num(d["value"]))
        for name, s in (r.get("signals") or {}).items():
            if not isinstance(s, dict):
                continue
            if s.get("missing"):
                sig_missing[name] = sig_missing.get(name, 0) + 1
            elif s.get("value") is not None:
                sig_vals.setdefault(name, []).append(_num(s["value"]))

    def dist(vals: dict[str, list[float]]) -> dict[str, dict[str, float]]:
        out = {}
        for k, vs in vals.items():
            out[k] = {
                "n": len(vs),
                "min": min(vs), "p25": _quantile(vs, .25),
                "median": _quantile(vs, .5),
                "p75": _quantile(vs, .75), "max": max(vs),
                "mean": sum(vs) / len(vs),
                "nonzero": sum(1 for v in vs if v > 0),
            }
        return out

    runs = {r.get("run_id") for r in rows if r.get("run_id")}
    hashes = {r.get("config_hash") for r in rows if r.get("config_hash")}
    return {
        "total": len(rows),
        "levels": levels,
        "vetoed": vetoed,
        "semantic_failed": sem_fail,
        "total_stats": {
            "min": min(totals), "p25": _quantile(totals, .25),
            "median": _quantile(totals, .5), "p75": _quantile(totals, .75),
            "max": max(totals), "mean": sum(totals) / len(totals),
        },
        "dimensions": dist(dim_vals),
        "signals": dist(sig_vals),
        "signal_missing": sig_missing,
        "runs": len(runs),
        "config_hashes": sorted(hashes),
        "mixed": len(runs) > 1 or len(hashes) > 1,
    }


# --------------------------------------------------------------- 渲染

def render_markdown(rows: list[dict[str, Any]], *,
                    top: int = 15,
                    title: str = "jev2 判定报告") -> str:
    """渲染成 Markdown。"""
    info = summarize(rows)
    if not info["total"]:
        return f"# {title}\n\n（没有结果）\n"

    L: list[str] = []
    w = L.append

    w(f"# {title}")
    w("")
    w(f"- 共 **{info['total']}** 篇")
    w(f"- 档位："
      + " · ".join(f"{Level(k).label} {v}"
                    for k, v in sorted(info["levels"].items(),
                                       key=lambda x: -Level(x[0]).rank))
      if all(k in ("low", "medium", "high") for k in info["levels"])
      else f"- 档位：{info['levels']}")
    w(f"- 一票否决命中：**{info['vetoed']}** 篇")
    if info["semantic_failed"]:
        w(f"- ⚠️ 语义层失败（结果只含统计信号）：**{info['semantic_failed']}** 篇")
    ts = info["total_stats"]
    w(f"- 总分：min {ts['min']:.3f} · 中位 {ts['median']:.3f} · "
      f"max {ts['max']:.3f} · 均 {ts['mean']:.3f}")
    if info["mixed"]:
        w(f"- ⚠️ **混了 {info['runs']} 次运行 / "
          f"{len(info['config_hashes'])} 个配置** —— "
          f"下面数字跨了不同阈值，比较时要小心")
        w(f"  config_hash: {', '.join('`' + h + '`' for h in info['config_hashes'])}")
    w("")

    # ---- 风险清单 ----
    w(f"## 风险最高的 {top} 篇")
    w("")
    w("| # | note_id | 总分 | 档位 | 主要维度 | 否决 | 标题 |")
    w("|---:|---|---:|---|---|---|---|")
    ordered = sorted(rows, key=lambda r: -_num(r.get("total")))[:top]
    for i, r in enumerate(ordered, 1):
        dims = r.get("dimensions") or {}
        top_dim, top_v = "-", 0.0
        for k, d in dims.items():
            if isinstance(d, dict) and _num(d.get("value")) > top_v:
                top_dim, top_v = k, _num(d.get("value"))
        title_txt = str((r.get("note") or {}).get("title") or "")[:26]
        flag = "✓" if r.get("vetoed_by") else ""
        w(f"| {i} | `{r.get('note_id', '')[:8]}` | {_num(r.get('total')):.3f} | "
          f"{Level(r['level']).label if r.get('level') in ('low','medium','high') else r.get('level')} | "
          f"{top_dim} {top_v:.2f} | {flag} | {title_txt} |")
    w("")

    # ---- 语义维度分布 ----
    if info["dimensions"]:
        w("## 语义维度分布")
        w("")
        w("| 维度 | n | min | p25 | 中位 | p75 | max | 均 | 非零 |")
        w("|---|---:|---:|---:|---:|---:|---:|---:|---:|")
        for k, d in sorted(info["dimensions"].items()):
            w(f"| `{k}` | {d['n']} | {d['min']:.2f} | {d['p25']:.2f} | "
              f"{d['median']:.2f} | {d['p75']:.2f} | {d['max']:.2f} | "
              f"{d['mean']:.2f} | {d['nonzero']} |")
        w("")

    # ---- 统计信号分布 ----
    if info["signals"] or info["signal_missing"]:
        w("## 统计信号分布")
        w("")
        w("> 「非零」= 有多少篇被判出风险。全 0 的信号在当前数据上"
          "没有区分度（要么阈值不对，要么真的都不可疑）。")
        w("")
        w("| 信号 | n | min | 中位 | max | 均 | 非零 | 缺失 |")
        w("|---|---:|---:|---:|---:|---:|---:|---:|")
        for k in sorted(set(info["signals"]) | set(info["signal_missing"])):
            d = info["signals"].get(k)
            miss = info["signal_missing"].get(k, 0)
            if d:
                w(f"| `{k}` | {d['n']} | {d['min']:.2f} | {d['median']:.2f} | "
                  f"{d['max']:.2f} | {d['mean']:.2f} | {d['nonzero']} | {miss} |")
            else:
                w(f"| `{k}` | 0 | — | — | — | — | 0 | {miss} |")
        w("")

    # ---- 单篇 trace ----
    w(f"## 最高分那篇的判定过程")
    w("")
    if ordered:
        r = ordered[0]
        w(f"`{r.get('note_id')}` · total **{_num(r.get('total')):.4f}** · "
          f"{r.get('level_label', r.get('level'))}")
        w("")
        w("| 规则 | 动作 | 值 | 权重 | 贡献 | 说明 |")
        w("|---|---|---:|---:|---:|---|")
        for t in (r.get("trace") or []):
            v = "—" if t.get("value") is None else f"{_num(t['value']):.3f}"
            w(f"| `{t.get('rule')}` | {t.get('action')} | {v} | "
              f"{_num(t.get('weight')):.2f} | {_num(t.get('contribution')):.4f} | "
              f"{str(t.get('reason') or '')[:44]} |")
        w("")
        for n in (r.get("notes") or []):
            w(f"> {n}")
        w("")

    return "\n".join(L) + "\n"


def write_report(rows: list[dict[str, Any]], path: Path, *,
                 top: int = 15,
                 title: str = "jev2 判定报告") -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_markdown(rows, top=top, title=title),
                    encoding="utf-8")
    return path


def render_console(rows: list[dict[str, Any]]) -> str:
    """终端友好的简报（无表格，纯文本）。"""
    info = summarize(rows)
    if not info["total"]:
        return "（没有结果）"
    levels = info["levels"]
    parts = [f"共 {info['total']} 篇"]
    for lv in ("high", "medium", "low"):
        if lv in levels:
            parts.append(f"{Level(lv).label} {levels[lv]}")
    if info["vetoed"]:
        parts.append(f"否决 {info['vetoed']}")
    if info["semantic_failed"]:
        parts.append(f"语义失败 {info['semantic_failed']}")
    ts = info["total_stats"]
    parts.append(f"中位分 {ts['median']:.3f}")
    return " | ".join(parts)


__all__ = ["summarize", "render_markdown", "write_report", "render_console"]

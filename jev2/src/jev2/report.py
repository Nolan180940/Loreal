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

import json
from pathlib import Path
from typing import Any, Iterable

from .core.types import Level


def _num(x: Any, default: float = 0.0) -> float:
    try:
        return float(x)
    except (TypeError, ValueError):
        return default


#: ``redOfficialVerifyType`` 的取值 → 人话。
#: 实测：0 = 无认证（卖家帖/KOL/普通分享都是 0），2 = 品牌官方。
#: 1 大概率是个人黄 V，未实测到 —— 不下结论，只标「其他」。
#: -1 是本项目的约定值，表示**旧数据未采集**（不是「无认证」）。
_VERIFY_LABELS = {
    -1: "未采集（旧数据）",
    0: "无",
    1: "其他认证",
    2: "**品牌官方**",
}


def _verify_label(v: Any) -> str:
    """作者认证类型的可读标签。"""
    try:
        return _VERIFY_LABELS.get(int(v), f"未知({v})")
    except (TypeError, ValueError):
        return "未采集（旧数据）"


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

def render_note_console(row: dict[str, Any]) -> str:
    """单篇的终端简报（一行结论 + 主要依据）。"""
    nid = str(row.get("note_id") or "")
    lv = row.get("level")
    lv_label = (Level(lv).label if lv in ("low", "medium", "high")
                else str(lv))
    parts = [f"{nid[:12]} {_num(row.get('total')):.3f} {lv_label}"]
    if row.get("vetoed_by"):
        parts.append(f"veto:{row['vetoed_by']}")
    dims = row.get("dimensions") or {}
    top = sorted(((k, _num(v.get("value"))) for k, v in dims.items()
                  if isinstance(v, dict)), key=lambda x: -x[1])[:2]
    if top:
        parts.append("主因 " + " ".join(f"{k}={v:.2f}" for k, v in top))
    if row.get("semantic_ok") is False:
        parts.append("⚠️ 语义层失败")
    elif not row.get("model"):
        # 融合权重全部来自语义维度，所以「没跑语义」= 没判定。
        # 不提示的话 0.000 会被读成「内容干净」。
        parts.append("⚠️ 未跑语义层（分数不构成判定）")
    return " | ".join(parts)


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


def render_note_detail(row: dict[str, Any], *,
                       title: str = "") -> str:
    """**单篇**详细报告 —— 一篇一页，含全部中间值。

    与 :func:`render_markdown` 的分工：

    - ``render_markdown``     多篇汇总（分布 + Top 清单 + 抽样 trace）
    - ``render_note_detail``  单篇展开（全维度 + 全信号 + 完整 trace）

    后者是「这一篇凭什么这么判」的完整答案，用于单篇复核与人工抽查。
    """
    nid = str(row.get("note_id") or "")
    note = row.get("note") or {}
    lv = row.get("level")
    lv_label = (Level(lv).label if lv in ("low", "medium", "high")
                else str(lv))
    total = _num(row.get("total"))

    L: list[str] = []
    w = L.append

    w(f"# jev2 单篇判定：`{nid}`")
    w("")
    if title:
        w(f"> {title}")
        w("")

    # ---- 结论 ----
    w("## 结论")
    w("")
    w("| 项 | 值 |")
    w("|---|---|")
    w(f"| 总分 | **{total:.4f}** |")
    w(f"| 档位 | **{lv_label}** |")
    if row.get("vetoed_by"):
        w(f"| 一票否决 | **{row['vetoed_by']}** |")
    w(f"| run_id | `{row.get('run_id', '')}` |")
    w(f"| config_hash | `{row.get('config_hash', '')}` |")
    w(f"| 模型 | `{row.get('model') or '(未启用语义层)'}` |")
    w(f"| 规则集 | `{row.get('rule_set', '')}` |")
    w(f"| 判定时间 | {row.get('scored_at', '')} |")
    w(f"| 耗时 | {row.get('elapsed_ms', '-')} ms |")
    if row.get("semantic_ok") is False:
        w("")
        w(f"> ⚠️ **语义层失败**：{row.get('semantic_error', '')[:120]}")
        w(">")
        w("> 本篇分数**只含统计信号**，偏低是正常的，不代表「内容干净」。")
    elif not row.get("model"):
        # 与「语义层失败」不同的情况：**根本没跑**。
        # 两者都不能当作判定结果，但原因不同，处置也不同。
        w("")
        w("> ⚠️ **未跑语义层**（`--no-semantic`）")
        w(">")
        w("> 融合权重**全部**来自语义维度（`has_risk` / `exaggeration` /"
          " `is_ad` / `is_cta`），")
        w("> 所以本篇分数**不构成判定结果** —— 它只能用来核对统计信号。")
    for n in (row.get("notes") or []):
        w("")
        w(f"> {n}")
    w("")

    # ---- 笔记元信息 ----
    if note:
        w("## 笔记")
        w("")
        w("| 项 | 值 |")
        w("|---|---|")
        w(f"| 标题 | {note.get('title') or '（空）'} |")
        w(f"| 作者 | {note.get('author') or '（空）'} |")
        w(f"| 作者认证 | {_verify_label(note.get('author_verify_type'))} |")
        w(f"| 点赞 | {note.get('liked')} |")
        w(f"| 评论声明 | {note.get('comment_count')} |")
        w(f"| 评论实得 | {note.get('comments_got')} |")
        w(f"| 图片 | {note.get('images')} 张 |")
        w("")
        if note.get("author_is_brand") is True:
            # 不是风险分，是**上下文**：品牌官方号发的帖，
            # 评论区通常是品牌在运营（与自然分享帖的评论结构不可比）。
            w("> ⚠️ **作者是品牌官方号**（`redOfficialVerifyType=2`）。")
            w(">")
            w("> 这是**上下文而非风险分** —— 官方号也可能发不引导购买的科普。")
            w("> 但它解释了评论区为何可能是品牌运营的，")
            w("> 所以「刷评类」统计信号在这类帖上要谨慎解读。")
            w("")

    # ---- 语义维度 ----
    dims = row.get("dimensions") or {}
    if dims:
        w("## 语义维度（jev-1.13）")
        w("")
        w("| 维度 | 风险值 | 置信度 | 题型 |")
        w("|---|---:|---:|---|")
        for name, d in sorted(dims.items(),
                              key=lambda x: -_num((x[1] or {}).get("value"))):
            if not isinstance(d, dict):
                continue
            conf = d.get("confidence")
            w(f"| `{name}` | {_num(d.get('value')):.3f} | "
              f"{'—' if conf is None else f'{_num(conf):.2f}'} | "
              f"{d.get('qtype', '')} |")
        w("")

    # ---- 统计信号（含缺失）----
    sigs = row.get("signals") or {}
    if sigs:
        w("## 统计信号")
        w("")
        present = {k: v for k, v in sigs.items()
                   if isinstance(v, dict) and not v.get("missing")}
        missing = {k: v for k, v in sigs.items()
                   if isinstance(v, dict) and v.get("missing")}
        if present:
            w("| 信号 | 风险值 | n | 详情 |")
            w("|---|---:|---:|---|")
            for name, s in sorted(present.items(),
                                  key=lambda x: -_num(x[1].get("value"))):
                detail = " · ".join(f"{k}={v}" for k, v in
                                    list((s.get("detail") or {}).items())[:4])
                w(f"| `{name}` | {_num(s.get('value')):.3f} | {s.get('n', 0)} | "
                  f"{str(detail)[:70]} |")
            w("")
        if missing:
            w(f"**缺失 {len(missing)} 个**（样本不足或数据源限制，"
              f"未参与打分）：")
            w("")
            for name, s in sorted(missing.items()):
                w(f"- `{name}` —— {s.get('missing_reason') or '未给原因'}")
            w("")

    # ---- 判定过程 ----
    trace = row.get("trace") or []
    if trace:
        w("## 判定过程（规则逐条求值）")
        w("")
        w("| 规则 | 动作 | 值 | 权重 | 贡献 | 说明 |")
        w("|---|---|---:|---:|---:|---|")
        for t in trace:
            v = "—" if t.get("value") is None else f"{_num(t['value']):.3f}"
            w(f"| `{t.get('rule')}` | {t.get('action')} | {v} | "
              f"{_num(t.get('weight')):.2f} | {_num(t.get('contribution')):.4f} | "
              f"{str(t.get('reason') or '')[:52]} |")
        w("")
        w("> 命中 veto 的规则会直接把总分拉满，后续规则不再计入；")
        w("> `flag` 动作只记录不计分（如 L2 统计信号）。")
        w("")

    return "\n".join(L) + "\n"


def write_note_bundle(out_dir: Path, row: dict[str, Any], *,
                      title: str = "") -> dict[str, str]:
    """把**单篇**结果落成 ``<out_dir>/<note_id>/{scores.json, report.md}``。

    Returns
    -------
    dict
        ``{"dir", "scores", "report"}``（绝对路径字符串）

    与汇总产物的分工
    ----------------
    - ``out/scores.jsonl``  全篇汇总（一行一篇，供聚合与对比）
    - ``out/<nid>/scores.json`` 单篇完整详情（供复核这一篇）
    - ``out/<nid>/report.md``   单篇可读报告

    ``scores.json`` 就是 ``scores.jsonl`` 里的那一行（结构完全一致），
    所以两种读法可以互相印证，不会出现两套字段。
    """
    out_dir = Path(out_dir)
    nid = str(row.get("note_id") or "")
    if not nid:
        raise ValueError("row 里没有 note_id，无法建单篇目录")

    d = out_dir / nid
    d.mkdir(parents=True, exist_ok=True)

    scores_path = d / "scores.json"
    scores_path.write_text(
        json.dumps(row, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8")

    report_path = d / "report.md"
    report_path.write_text(render_note_detail(row, title=title),
                           encoding="utf-8")

    return {"dir": str(d), "scores": str(scores_path),
            "report": str(report_path)}


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


__all__ = ["summarize", "render_markdown", "render_note_detail",
           "write_report", "write_note_bundle", "render_console",
           "render_note_console"]

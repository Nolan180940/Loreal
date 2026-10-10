"""命令行入口。

子命令
------
::

    jev2 doctor                      环境自检（key / 数据 / 模型连通）
    jev2 signals [--note ID]         只看统计信号，不调模型
    jev2 judge [--all|--note ID]     跑判定（信号 + 语义 + 融合）
    jev2 report [--top N]            从已有结果出报告
    jev2 rules                       列出当前规则集与权重
    jev2 calibrate                   阈值扫描（需要人工标注）

设计原则：**每个子命令都能单独跑**。
``signals`` 不花钱（零模型调用），``report`` 不花钱（读已有结果），
只有 ``judge`` 会调模型 —— 调阈值时可以反复跑前两个。
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

from . import __version__
from .config import config_hash, load_config, mask, resolve_api_key
from .core.errors import ConfigError, JevError
from .loader import load_all, load_note
from .pipeline.store import ResultStore
from .report import render_console, render_markdown, summarize
from .signals import ALL_SIGNALS, SignalContext, SignalSet, signal_groups


def _force_utf8() -> None:
    """Windows 控制台默认 GBK，遇到 emoji 直接崩。"""
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8", errors="replace")
        except Exception:  # noqa: BLE001
            pass


def _write_out(text: str, path: Path | None) -> None:
    """有 path 就写文件（UTF-8），否则打到终端。

    优先写文件是因为中文 + emoji 在 Windows 控制台必然出问题，
    而报告恰恰全是中文。
    """
    if path:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        print(f"[saved] {path}")
    else:
        print(text)


# --------------------------------------------------------------- 子命令

def cmd_doctor(args: argparse.Namespace) -> int:
    cfg = load_config(path=args.config, require_key=False)
    key = resolve_api_key()

    print("=== jev2 doctor ===")
    print(f"版本            : {__version__}")
    print(f"配置文件        : {args.config or '(自动查找)'}")
    print(f"API key         : {mask(key)}")
    print(f"config_hash     : {config_hash(cfg)}")
    print()

    print("--- 路径 ---")
    print(f"data_root       : {cfg.paths.data_root}  "
          f"{'OK' if cfg.paths.data_root.is_dir() else '不存在'}")
    print(f"out_dir         : {cfg.paths.out_dir}")
    print()

    print("--- 数据 ---")
    notes, bad = load_all(cfg.paths.data_root)
    print(f"笔记            : {len(notes)} 篇（坏数据 {len(bad)}）")
    if notes:
        tot_c = sum(len(n.comments) for n in notes)
        print(f"评论            : {tot_c} 行")
        print(f"作者自评        : {sum(1 for n in notes if n.author_comments)} 篇")
    for p, why in bad[:3]:
        print(f"  [坏] {p.name}: {why[:60]}")
    print()

    print("--- 信号层 ---")
    print(f"已注册          : {len(ALL_SIGNALS)} 个")
    for g, names in signal_groups().items():
        print(f"  [{g}] {', '.join(names)}")
    print()

    print("--- 语义层 ---")
    sem = cfg.semantic
    print(f"启用            : {sem.enabled}")
    print(f"模型            : {sem.model}")
    print(f"端点            : {sem.endpoint}")
    print(f"维度            : {', '.join(sem.dims)}")
    if sem.enabled and key:
        from .semantic.provider import health_check
        hc = health_check(sem, api_key=key)
        print(f"连通性          : {'OK' if hc['ok'] else '失败'}  {hc['detail'][:70]}")
        if hc.get("stats"):
            st = hc["stats"]
            print(f"  探测用量      : {st['input_tokens']} in / "
                  f"{st['output_tokens']} out / ${st['cost_usd']}")
    elif not key:
        print("连通性          : 跳过（没有 key）")
    print()

    print("--- 融合层 ---")
    print(f"规则集          : {cfg.fuse.rule_set}")
    print(f"阈值            : high >= {cfg.fuse.high} · low <= {cfg.fuse.low}")
    print(f"权重            : {cfg.fuse.weights}")
    print(f"一票否决        : {cfg.fuse.veto}")
    print(f"L2 聚合         : {cfg.fuse.l2_aggregate}  "
          f"（信号 {cfg.fuse.l2_signals or '全部'}）")
    return 0


def cmd_signals(args: argparse.Namespace) -> int:
    """只看统计信号 —— 零模型调用。"""
    cfg = load_config(path=args.config)
    ss = SignalSet(active=cfg.signals.active or None,
                   ctx=SignalContext(min_samples=cfg.signals.min_samples))

    if args.note:
        notes = [n for n in [load_note(_find_note(cfg, args.note))]
                 if n is not None]
    else:
        notes, _ = load_all(cfg.paths.data_root)

    L: list[str] = []
    for n in notes:
        L.append(f"## `{n.note_id}` {n.title[:40]}")
        L.append("")
        L.append(f"- 作者 {n.author} · 赞 {n.liked} · 评论声明 "
                 f"{n.comment_count}（实得 {len(n.comments)}）")
        L.append("- 评论 " + str(len(n.comments)) +
                 " 行 = 一级 " + str(len(n.top_comments)) +
                 " + 楼中楼 " + str(len(n.replies)) +
                 " · 作者自评 " + str(len(n.author_comments)))
        L.append("")
        L.append("| 信号 | 风险值 | n | 详情 |")
        L.append("|---|---:|---:|---|")
        for name, r in ss.compute(n).items():
            v = "**缺失**" if r.missing else f"{r.value:.3f}"
            detail = (r.missing_reason if r.missing
                      else " · ".join(f"{k}={x}" for k, x in
                                      list(r.detail.items())[:4]))
            L.append(f"| `{name}` | {v} | {r.n} | {str(detail)[:60]} |")
        L.append("")

    _write_out("\n".join(L), Path(args.out) if args.out else None)
    return 0


def _find_note(cfg: Any, prefix: str) -> Path:
    """按 note_id 前缀找 ``notes.json``。"""
    root = cfg.paths.data_root
    hits = [d for d in root.iterdir()
            if d.is_dir() and d.name.startswith(prefix)]
    if not hits:
        raise ConfigError(f"找不到 note_id 以 {prefix!r} 开头的目录")
    if len(hits) > 1:
        raise ConfigError(
            f"{prefix!r} 匹配到 {len(hits)} 个目录，请给更长的前缀")
    return hits[0] / "notes.json"


def cmd_judge(args: argparse.Namespace) -> int:
    from .pipeline import Pipeline, RunMeta

    cfg = load_config(path=args.config, require_key=not args.no_semantic)
    if args.no_semantic:
        cfg.semantic.enabled = False

    meta = RunMeta.create(config_hash=config_hash(cfg),
                          model=cfg.semantic.model if cfg.semantic.enabled else "",
                          rule_set=cfg.fuse.rule_set)
    pipe = Pipeline(cfg, meta=meta, progress=lambda s: print(s, flush=True))

    if args.note:
        notes = [load_note(_find_note(cfg, args.note))]
    else:
        notes = None      # 让 Pipeline 自己 load_all

    try:
        stats = pipe.run(notes=notes, limit=args.limit,
                         skip_existing=not args.force)
    except JevError as exc:
        print(f"[X] {exc}", file=sys.stderr)
        return 3

    print()
    print(f"完成：{stats['ok']} 判 · {stats['skipped']} 跳过 · "
          f"{stats['failed']} 失败 · 耗时 {stats['elapsed_s']}s")
    if stats["semantic_failed"]:
        print(f"  ⚠️ 语义层失败 {stats['semantic_failed']} 篇"
              "（这些只含统计信号，分数偏低）")
    if stats["model_stats"]:
        ms = stats["model_stats"]
        print(f"  模型：{ms['calls']} 次调用 · "
              f"{ms['input_tokens']} in / {ms['output_tokens']} out · "
              f"${ms['cost_usd']}")
    print(f"  run_id={stats['run_id']}  config_hash={stats['config_hash']}")

    if args.report:
        rows = ResultStore(cfg.paths.out_dir).load()
        print()
        print(render_console(rows))
        if args.report_path:
            from .report import write_report
            print(f"[saved] {write_report(rows, Path(args.report_path))}")
    return 0


def cmd_report(args: argparse.Namespace) -> int:
    cfg = load_config(path=args.config)
    store = ResultStore(cfg.paths.out_dir)
    rows, bad = store.load_checked()
    if not rows:
        print(f"[X] {store.path} 里没有结果。先跑 jev2 judge",
              file=sys.stderr)
        return 2
    if bad:
        print(f"[!] 跳过 {len(bad)} 个坏行", file=sys.stderr)

    info = summarize(rows)
    print(render_console(rows))
    if info.get("mixed"):
        print(f"[!] 结果混了 {info['runs']} 次运行 / "
              f"{len(info['config_hashes'])} 个配置")

    out = Path(args.out) if args.out else (cfg.paths.out_dir / "REPORT.md")
    text = render_markdown(rows, top=args.top)
    _write_out(text, out)
    return 0


def cmd_rules(args: argparse.Namespace) -> int:
    """列出规则集（含被 config 提升的动作）。"""
    from .fuse import FuseEngine
    from .fuse.engine import EngineConfig
    from .fuse.rules import RULE_SETS

    cfg = load_config(path=args.config)
    name = args.rule_set or cfg.fuse.rule_set

    print(f"=== 规则集 {name}（config 权重已应用）===")
    eng = FuseEngine(EngineConfig(
        high=cfg.fuse.high, low=cfg.fuse.low, rule_set=name,
        weights=dict(cfg.fuse.weights), veto=dict(cfg.fuse.veto)))
    for d in eng.describe():
        mark = ("→" if d["declared"] != d["effective"] else " ")
        if d["effective"] == "veto":
            spec = f"t>={d['threshold']:.2f}"
        elif d["effective"] == "contribute":
            spec = f"w={d['weight']:.2f}"
        else:
            spec = "仅记录"
        print(f"{mark} {d['name']:<16} {d['effective']:<11} "
              f"{spec:<9} in={','.join(d['inputs'])}")
        if d["note"]:
            print(f"    {d['note'][:76]}")
    print()
    print(f"所有可用规则集: {', '.join(sorted(RULE_SETS))}")
    print(f"阈值: high >= {cfg.fuse.high} · low <= {cfg.fuse.low}")
    return 0


def cmd_calibrate(args: argparse.Namespace) -> int:
    """阈值扫描：给定标注文件，找使 F1 最大的阈值。

    标注文件格式（JSONL）::

        {"note_id": "6a5c...", "label": "high"}
    """
    import json
    from .report import summarize  # noqa: F401  （保留导入便于扩展）

    cfg = load_config(path=args.config)
    if not args.labels:
        print("需要 --labels 指定标注文件。格式（JSONL）：\n"
              '  {"note_id": "6a5c65d3...", "label": "high"}\n'
              "\n没有 ground truth 就没有校准 —— 这是 legacy-jev 的教训："
              "n<20 时任何权重都是过拟合。", file=sys.stderr)
        return 2

    labels: dict[str, str] = {}
    for line in Path(args.labels).read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        o = json.loads(line)
        if o.get("note_id") and o.get("label"):
            labels[o["note_id"]] = str(o["label"])

    rows = {r["note_id"]: r for r in ResultStore(cfg.paths.out_dir).load()
            if r.get("note_id")}
    paired = [(rows[k], v) for k, v in labels.items() if k in rows]
    print(f"标注 {len(labels)} 条，能在结果里匹配到 {len(paired)} 条")
    if len(paired) < 5:
        print("[X] 匹配太少，校准无意义。至少 10 条，越多越可靠。",
              file=sys.stderr)
        return 2

    print()
    print("| high 阈值 | 高风险 F1 | 精确率 | 召回率 |")
    print("|---:|---:|---:|---:|")
    best = (0.0, -1.0)
    for th in [x / 100 for x in range(30, 100, 5)]:
        tp = fp = fn = 0
        for r, lab in paired:
            pred_high = float(r.get("total") or 0) >= th
            true_high = lab == "high"
            if pred_high and true_high:
                tp += 1
            elif pred_high:
                fp += 1
            elif true_high:
                fn += 1
        prec = tp / (tp + fp) if (tp + fp) else 0.0
        rec = tp / (tp + fn) if (tp + fn) else 0.0
        f1 = 2 * prec * rec / (prec + rec) if (prec + rec) else 0.0
        mark = ""
        if f1 > best[1]:
            best = (th, f1)
            mark = " ←"
        print(f"| {th:.2f} | {f1:.3f} | {prec:.3f} | {rec:.3f} |{mark}")
    print()
    print(f"最佳 high 阈值: **{best[0]:.2f}**（F1={best[1]:.3f}）"
          f"  ← 写进 config.fuse.high")
    return 0


# --------------------------------------------------------------- 入口

def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        prog="jev2",
        description="种草真实性判别：统计信号 + jev-1.13 语义 + 可配置融合",
    )
    ap.add_argument("--version", action="version",
                    version=f"jev2 {__version__}")
    ap.add_argument("--config", help="配置文件路径（默认自动查找）")
    ps = ap.add_subparsers(dest="cmd")

    p = ps.add_parser("doctor", help="环境自检")
    p.set_defaults(func=cmd_doctor)

    p = ps.add_parser("signals", help="只看统计信号（不调模型）")
    p.add_argument("--note", help="只跑某篇（note_id 前缀）")
    p.add_argument("--out", help="输出文件（默认打到终端）")
    p.set_defaults(func=cmd_signals)

    p = ps.add_parser("judge", help="跑判定（会调模型）")
    p.add_argument("--note", help="只跑某篇（note_id 前缀）")
    p.add_argument("--limit", type=int, help="最多跑几篇")
    p.add_argument("--force", action="store_true",
                   help="重跑已有结果的篇（默认跳过）")
    p.add_argument("--no-semantic", action="store_true",
                   help="只用统计信号（不调模型、不需要 key）")
    p.add_argument("--report", action="store_true", help="跑完出简报")
    p.add_argument("--report-path", help="把 Markdown 报告写到该路径")
    p.set_defaults(func=cmd_judge)

    p = ps.add_parser("report", help="从已有结果出报告（不调模型）")
    p.add_argument("--top", type=int, default=15, help="风险清单条数")
    p.add_argument("--out", help="Markdown 输出路径")
    p.set_defaults(func=cmd_report)

    p = ps.add_parser("rules", help="列出规则集与权重")
    p.add_argument("--rule-set", help="看指定规则集（默认用 config 里的）")
    p.set_defaults(func=cmd_rules)

    p = ps.add_parser("calibrate", help="阈值扫描（需人工标注）")
    p.add_argument("--labels", help="标注文件（JSONL）")
    p.set_defaults(func=cmd_calibrate)

    return ap


def main(argv: list[str] | None = None) -> int:
    _force_utf8()
    ap = build_parser()
    args = ap.parse_args(argv)
    if not getattr(args, "cmd", None):
        ap.print_help()
        return 2
    try:
        return int(args.func(args) or 0)
    except ConfigError as exc:
        print(f"[X] 配置错误: {exc}", file=sys.stderr)
        return 2
    except JevError as exc:
        print(f"[X] {type(exc).__name__}: {exc}", file=sys.stderr)
        return 3
    except KeyboardInterrupt:
        print("\n[中断]", file=sys.stderr)
        return 130


__all__ = ["main", "build_parser"]


if __name__ == "__main__":
    raise SystemExit(main())

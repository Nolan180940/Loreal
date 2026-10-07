"""命令行入口。

子命令
------
``doctor``   环境自检（key / 连通性 / 模型可达）
``label``    打标：调用 jev，产出原始维度分
``score``    评分：标签 + 规则引擎 -> 风险判定
``report``   报告：汇总风险分布 + Top 风险清单
``calibrate`` 校准：用带标签数据拟合阈值
``inspect``  查看单条内容的完整判定链路

典型流程::

    jev-guard doctor
    jev-guard label --kind note
    jev-guard score
    jev-guard report --top 15
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .core.config import Config, load_config
from .core.errors import JevGuardError
from .core.models import SubjectKind
from .extractors.reader import iter_note_ids, iter_notes
from .pipeline.batch import run_labeling
from .pipeline.score import score_all, top_risky
from .pipeline.store import LabelStore


# --------------------------------------------------------------- 输出helpers

def _out(obj) -> None:
    """机器可读输出。与人类可读输出分开，方便管道。"""
    print(json.dumps(obj, ensure_ascii=False, indent=2, default=str))


def _table(rows: list[list[str]], headers: list[str]) -> str:
    if not rows:
        return "(空)"
    widths = [max(_w(headers[i]), *(_w(r[i]) for r in rows))
              for i in range(len(headers))]
    sep = "  " + "  ".join("-" * w for w in widths)
    head = "  ".join(headers[i].ljust(widths[i]) for i in range(len(headers)))
    body = "\n".join(
        "  ".join(r[i].ljust(widths[i]) for i in range(len(headers)))
        for r in rows)
    return f"{head}\n{sep}\n{body}"


def _w(s: str) -> int:
    """按显示宽度算，中文算 2 列。"""
    return sum(2 if ord(c) > 0x2E80 else 1 for c in str(s))


# --------------------------------------------------------------- 子命令

def cmd_doctor(args, cfg: Config) -> int:
    from .providers.jev import health_check
    data_ok = Path(cfg.data_root).is_dir()
    n = len(list(iter_note_ids(cfg.data_root))) if data_ok else 0

    info = health_check(cfg)
    _out({
        "api_key": info.get("api_key"),
        "endpoint": info.get("endpoint"),
        "model": info.get("model"),
        "provider_status": info.get("status"),
        "provider_error": info.get("error"),
        "sample_response": info.get("sample"),
        "data_root": str(cfg.data_root),
        "data_exists": data_ok,
        "note_count": n,
        "usage": info.get("stats"),
    })
    return 0 if info.get("status") == "ok" else 1


def cmd_label(args, cfg: Config) -> int:
    kind = SubjectKind(args.kind)
    out_dir = Path(args.out or cfg.out_dir)
    label_path = out_dir / f"labels_{kind.value}.jsonl"

    if kind is SubjectKind.NOTE:
        subjects = list(iter_notes(cfg.data_root))
    else:
        from .extractors.reader import iter_all_subjects
        subjects = [s for s in iter_all_subjects(cfg.data_root,
                                                  with_comments=True)
                    if s.kind == "comment"]

    if args.limit:
        subjects = subjects[:args.limit]

    store = LabelStore(label_path, fsync_every=cfg.checkpoint_every)
    print(f"[label] kind={kind.value}  待处理 {len(subjects)}  "
          f"model={cfg.model}  -> {label_path}", file=sys.stderr)

    def on_progress(i: int, total: int, lb) -> None:
        if i % cfg.checkpoint_every == 0 or i == total:
            top = max(lb.dimensions, key=lambda d: d.value) if lb.dimensions else None
            print(f"  {i}/{total}  {lb.subject_id[:8]} "
                  f"max={top.name}:{top.value:.2f}" if top else f"  {i}/{total}",
                  file=sys.stderr, flush=True)

    res = run_labeling(subjects, cfg, store, kind,
                       on_progress=on_progress, resume=not args.no_resume)
    _out(res.to_dict())
    if res.stopped_by_rate_limit:
        print(f"[!] {res.stop_reason}", file=sys.stderr)
        print(f"    进度已保存（{res.ok} 条）。重跑同一命令会跳过已完成的。",
              file=sys.stderr)
        return 3
    return 0 if res.failed == 0 else 1


def cmd_score(args, cfg: Config) -> int:
    out_dir = Path(args.out or cfg.out_dir)
    paths = {
        SubjectKind.NOTE: out_dir / "labels_note.jsonl",
        SubjectKind.COMMENT: out_dir / "labels_comment.jsonl",
    }
    merged = out_dir / "labels_all.jsonl"
    from .pipeline.store import LabelStore as LS
    all_rows: list[str] = []
    for p in paths.values():
        if p.is_file():
            all_rows.extend(p.read_text(encoding="utf-8").splitlines())
    merged.write_text("\n".join(all_rows) + "\n", encoding="utf-8")

    res = score_all(cfg, merged, out_dir / "scores.jsonl",
                    use_ip_signals=not args.no_ip,
                    reset=args.reset)
    _out(res)
    return 0


def cmd_report(args, cfg: Config) -> int:
    out_dir = Path(args.out or cfg.out_dir)
    scores_path = out_dir / "scores.jsonl"
    if not scores_path.is_file():
        print(f"[!] 没有 {scores_path}，先跑 `jev-guard score`",
              file=sys.stderr)
        return 2

    from .pipeline.store import ResultStore
    rows = ResultStore(scores_path).load()
    notes = [r for r in rows if r.get("kind") == "note"]

    dist = {"high": 0, "medium": 0, "low": 0}
    for r in rows:
        dist[r.get("level", "low")] = dist.get(r.get("level", "low"), 0) + 1

    top = top_risky(scores_path, limit=args.top, kind="note")
    table_rows = []
    for r in top:
        ev = (r.get("evidence") or ["-"])[0].replace("\n", " ")
        table_rows.append([
            r["subject_id"][:8],
            f"{r['total']:.3f}",
            r.get("level_label", ""),
            r.get("top_factor") or "-",
            ev[:40],
        ])

    if args.json:
        _out({"distribution": dist, "top": top})
        return 0

    print(f"\n风险分布（共 {len(rows)} 条）")
    print(f"  高风险 {dist.get('high', 0)}  "
          f"中风险 {dist.get('medium', 0)}  低风险 {dist.get('low', 0)}\n")
    print(f"Top {args.top} 高风险笔记")
    print(_table(table_rows,
                 ["note_id", "总分", "档位", "主因", "证据片段"]))
    return 0


def cmd_inspect(args, cfg: Config) -> int:
    """展示单条内容的完整判定链路 —— 调试和 PPT 取材用。"""
    out_dir = Path(args.out or cfg.out_dir)
    scores_path = out_dir / "scores.jsonl"
    from .pipeline.store import ResultStore
    from .extractors.reader import load_note, load_comments

    hit = next((r for r in ResultStore(scores_path).load()
                if args.subject_id.startswith(r["subject_id"])), None)
    if not hit:
        print(f"[!] 没找到 {args.subject_id}", file=sys.stderr)
        return 2

    nid = hit["subject_id"]
    subj = load_note(cfg.data_root, nid)
    print(f"\n{'=' * 70}")
    print(f"笔记 {nid}")
    print(f"{'=' * 70}")
    if subj:
        print(f"标题: {subj.title}")
        print(f"作者: {subj.author}  赞{subj.liked} 藏{subj.collected} "
              f"评{subj.comment_count} 享{subj.share}  图{subj.image_count}")
        print(f"\n正文:\n{subj.text[:600]}")
    print(f"\n{'-' * 70}")
    print(f"风险总分: {hit['total']:.3f}  ->  {hit.get('level_label')}")
    print(f"主因维度: {hit.get('top_factor')}")
    print(f"\n维度明细:")
    for d in hit.get("dimensions", []):
        bar = "#" * int(d["value"] * 30)
        conf = (f" conf={d['confidence']:.2f}"
                if d.get("confidence") is not None else "")
        print(f"  {d['name']:<14}{d['value']:.3f} {bar}{conf}")
    if hit.get("evidence"):
        print(f"\n命中证据:")
        for e in hit["evidence"]:
            print(f"  - {e}")
    if hit.get("notes"):
        print(f"\n说明:")
        for nt in hit["notes"]:
            print(f"  * {nt}")
    return 0


def cmd_calibrate(args, cfg: Config) -> int:
    """用人工标注校准阈值。

    期望一个 JSON：``[{"subject_id": "...", "label": "high"}, ...]``
    """
    from .core.scoring import RuleEngine
    from .pipeline.score import build_index
    from .pipeline.store import ResultStore

    ann_path = Path(args.annotations)
    if not ann_path.is_file():
        print(f"[!] 标注文件不存在: {ann_path}", file=sys.stderr)
        return 2
    ann = json.loads(ann_path.read_text(encoding="utf-8"))

    out_dir = Path(args.out or cfg.out_dir)
    scores = {r["subject_id"]: r
              for r in ResultStore(out_dir / "scores.jsonl").load()}
    samples: list[tuple[float, bool]] = []
    for a in ann:
        sid = a.get("subject_id")
        r = scores.get(sid)
        if not r:
            continue
        samples.append((float(r["total"]), a.get("label") == "high"))

    if not samples:
        print("[!] 标注与评分结果没有交集，检查 subject_id 是否对齐",
              file=sys.stderr)
        return 2

    res = RuleEngine(cfg.thresholds, cfg.weights).calibrate(samples)
    _out(res)
    if not res.get("converged"):
        print(f"[!] 样本仅 {len(samples)} 条（需 >=20），阈值未更新",
              file=sys.stderr)
    return 0


# --------------------------------------------------------------- parser

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="jev-guard",
        description="小红书内容核验：基于 jev-1.13 的可解释风险判断",
    )
    p.add_argument("--data-root", help="采集数据目录（默认 data）")
    p.add_argument("--out", help="输出目录（默认 out）")
    p.add_argument("--model", help="模型 ID（默认 jev-1.13-free）")
    p.add_argument("--endpoint", help="API 端点")
    sub = p.add_subparsers(dest="cmd", required=True)

    d = sub.add_parser("doctor", help="环境自检")
    d.set_defaults(fn=cmd_doctor)

    lb = sub.add_parser("label", help="调用 jev 打标")
    lb.add_argument("--kind", choices=["note", "comment"], default="note")
    lb.add_argument("--limit", type=int, default=0, help="只处理前 N 条")
    lb.add_argument("--no-resume", action="store_true", help="忽略已有标签重跑")
    lb.set_defaults(fn=cmd_label)

    sc = sub.add_parser("score", help="生成风险评分")
    sc.add_argument("--reset", action="store_true", help="清空已有评分")
    sc.add_argument("--no-ip", action="store_true", help="不叠加 IP 集中度信号")
    sc.set_defaults(fn=cmd_score)

    rp = sub.add_parser("report", help="风险报告")
    rp.add_argument("--top", type=int, default=15)
    rp.add_argument("--json", action="store_true")
    rp.set_defaults(fn=cmd_report)

    ins = sub.add_parser("inspect", help="查看单条判定链路")
    ins.add_argument("subject_id")
    ins.set_defaults(fn=cmd_inspect)

    cal = sub.add_parser("calibrate", help="用标注拟合阈值")
    cal.add_argument("annotations", help="标注 JSON 路径")
    cal.set_defaults(fn=cmd_calibrate)

    return p


def main(argv: list[str] | None = None) -> int:
    # 小红书正文里emoji/生僻字很常见，Windows 控制台默认 GBK 编不了，
    # 打印时会UnicodeEncodeError。强制 stdout/stderr 走 UTF-8 并替换
    # 无法编码的字符（errors="replace"），而不是让整条命令崩掉。
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass

    args = build_parser().parse_args(argv)
    overrides = {
        "data_root": args.data_root,
        "out_dir": args.out,
        "model": args.model,
        "endpoint": args.endpoint,
    }
    try:
        cfg = load_config({k: v for k, v in overrides.items() if v})
        return args.fn(args, cfg)
    except JevGuardError as e:
        print(f"[ERROR] {e}", file=sys.stderr)
        return e.exit_code
    except KeyboardInterrupt:
        print("\n[ABORT] 用户中断，进度已保存", file=sys.stderr)
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
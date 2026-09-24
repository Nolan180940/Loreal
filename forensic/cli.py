# -*- coding: utf-8 -*-
"""统一命令行入口。

用法（项目根目录）：
    python -m forensic.cli analyze  <图片路径> [--jev 0.8] [--out card.json]
    python -m forensic.cli gate     <card.json>
    python -m forensic.cli train
    python -m forensic.cli eval
    python -m forensic.cli jev-smoke
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

try:
    from .fusion import FusionModel
    from .evidence import build_card, save_card
    from .gating import gate_from_card
except ImportError:  # 直接运行时
    from fusion import FusionModel  # type: ignore
    from evidence import build_card, save_card  # type: ignore
    from gating import gate_from_card  # type: ignore


def _cmd_analyze(args: argparse.Namespace) -> int:
    model = FusionModel()

    p_jev = args.jev
    semantic_note = "manual_override" if p_jev is not None else "not_used"
    if p_jev is None and (args.post_text or args.ocr_numbers):
        try:
            from .jev_adapter import combine_signal, semantic_signals
        except ImportError:
            from jev_adapter import combine_signal, semantic_signals  # type: ignore
        sig = semantic_signals(args.post_text or "", args.ocr_numbers)
        if sig:
            p_jev = combine_signal(sig)
            semantic_note = "jev_atomic_signals"
            print(f"[semantic] 原子信号 {sig} → x7={p_jev:.3f}", file=sys.stderr)
        else:
            semantic_note = "jev_unavailable"
            print("[semantic] Jev 不可用（无 key/网络/限流），已自动降级为仅取证侧",
                  file=sys.stderr)

    card = build_card(args.image, model, p_jev=p_jev,
                      save_heatmaps=not args.no_heatmaps)
    card["semantic_source"] = semantic_note
    gate = gate_from_card(card, t1=args.t1, t2=args.t2)
    card["actions"] = gate
    print(json.dumps(card, ensure_ascii=False, indent=2))
    if args.out:
        save_card(card, args.out)
        print(f"\n[saved] {args.out}", file=sys.stderr)
    return 0


def _cmd_gate(args: argparse.Namespace) -> int:
    card = json.loads(Path(args.card).read_text(encoding="utf-8"))
    print(json.dumps(gate_from_card(card, t1=args.t1, t2=args.t2),
                     ensure_ascii=False, indent=2))
    return 0


def _cmd_train(args: argparse.Namespace) -> int:
    from . import train as T
    T.main(reuse_features=bool(getattr(args, "reuse_features", False)))
    return 0


def _cmd_eval(_: argparse.Namespace) -> int:
    from . import evaluate as E
    E.main()
    return 0


def _cmd_jev_smoke(args: argparse.Namespace) -> int:
    from .jev_adapter import smoke_test
    return 0 if smoke_test(n=args.n) else 1


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="forensic", description="图像鉴伪取证模块")
    sub = p.add_subparsers(dest="cmd", required=True)

    a = sub.add_parser("analyze", help="对单图生成证据卡")
    a.add_argument("image")
    a.add_argument("--jev", type=float, default=None,
                   help="手工指定语义侧 Noul 概率(0~1)；不传则尝试自动调用 Jev")
    a.add_argument("--post-text", default=None,
                   help="帖子文本；提供后会调用 Jev 抽取语义原子信号作为 x7")
    a.add_argument("--ocr-numbers", default=None,
                   help="图中可读到的数字/规格（人工输入或后续 OCR 输出），"
                        "用于提问「图内数字与正文是否矛盾」")
    a.add_argument("--out", default=None, help="证据卡 JSON 输出路径")
    a.add_argument("--no-heatmaps", action="store_true")
    a.add_argument("--t1", type=float, default=0.70)
    a.add_argument("--t2", type=float, default=0.70)
    a.set_defaults(func=_cmd_analyze)

    g = sub.add_parser("gate", help="对已有证据卡执行行动门控")
    g.add_argument("card")
    g.add_argument("--t1", type=float, default=0.70)
    g.add_argument("--t2", type=float, default=0.70)
    g.set_defaults(func=_cmd_gate)

    t = sub.add_parser("train", help="标定+特征+训练+阈值")
    t.add_argument("--reuse-features", action="store_true",
                   help="复用已提取的 features.csv（跳过标定与特征提取）")
    t.set_defaults(func=_cmd_train)

    e = sub.add_parser("eval", help="评估并生成报告")
    e.set_defaults(func=_cmd_eval)

    s = sub.add_parser("jev-smoke", help="Jev 通道冒烟测试")
    s.add_argument("--n", type=int, default=10)
    s.set_defaults(func=_cmd_jev_smoke)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())

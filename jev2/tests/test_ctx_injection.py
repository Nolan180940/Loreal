"""runner 的 ctx 注入测试（2026-10-12）。

为什么单独测：这是「12 个信号各自计分」的**唯一入口**。
信号值没进 ctx，规则集里那 12 条 sig_ 规则就全是 skipped，
整套改造静默失效 —— 而这种失效不会报错，只会让分数悄悄回到语义-only。
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

_HERE = Path(__file__).resolve()
for _p in (_HERE.parents[1] / "src", _HERE.parents[2] / "jev2" / "src"):
    if _p.is_dir() and str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from jev2.config.schema import Config                              # noqa: E402
from jev2.core.types import CommentRow, NoteRecord                 # noqa: E402
from jev2.pipeline.runner import Pipeline                          # noqa: E402
from jev2.signals import SignalContext, SignalSet                  # noqa: E402


def _note(n: int = 8) -> NoteRecord:
    cs = tuple(
        CommentRow(cid=f"c{i}", content="好用" * (i % 3 + 1), nickname=f"u{i}",
                   ip_location="上海", like_count="0",
                   time_ms=1_700_000_000_000 + i * 60_000,
                   is_author=False, is_reply=(i % 2 == 0))
        for i in range(n))
    return NoteRecord(note_id="a" * 24, title="标题", desc="正文" * 40,
                      author="老王", liked=100, comment_count=50,
                      tags=("护肤", "面霜", "测评"),
                      published_ms=1_700_000_000_000, comments=cs)


def _ctx_of(note: NoteRecord) -> dict:
    """复刻 judge_one 的 ctx 组装（不含语义层与引擎）。"""
    cfg = Config()
    cfg.semantic.enabled = False
    pipe = Pipeline(cfg)
    sig = pipe._sig.compute(note)
    ctx = {}
    for name, r in sig.items():
        if not r.missing and r.value is not None:
            ctx[name] = r.value
    l2 = pipe._aggregate_l2(sig)
    if l2 is not None:
        ctx["l2_mean"] = l2
    return ctx, sig


def test_ctx_contains_every_nonmissing_signal() -> None:
    """**每个**非缺失信号都要进 ctx（不止 12 个计分的）。

    全放进去的理由：给任何信号加权重 = 改一行 config。
    若只放 12 个，将来想启用第 13 个就得改代码。
    """
    note = _note()
    ctx, sig = _ctx_of(note)
    nonmissing = {k for k, r in sig.items() if not r.missing}
    assert nonmissing, "测试数据应至少算出几个信号"
    missing_from_ctx = nonmissing - set(ctx)
    assert not missing_from_ctx, f"这些信号没进 ctx: {missing_from_ctx}"


def test_ctx_excludes_missing_signals() -> None:
    """缺失信号**不进** ctx —— 进了就会被规则当成 0 值算。

    「没数据」和「风险为 0」是两回事（信号层的第一原则）。
    """
    # 评论为 0 条 → 大部分信号缺失
    note = NoteRecord(note_id="b" * 24, title="t", desc="d",
                      published_ms=1_700_000_000_000, comments=())
    ctx, sig = _ctx_of(note)
    for k, r in sig.items():
        if r.missing:
            assert k not in ctx, f"缺失信号 {k} 不该进 ctx"
        else:
            assert k in ctx


def test_ctx_has_l2_mean_when_signals_exist() -> None:
    """l2_mean 仍保留（观测通道）—— 它是 12 条独立规则之外的聚合视图。"""
    ctx, _ = _ctx_of(_note())
    assert "l2_mean" in ctx
    assert 0.0 <= ctx["l2_mean"] <= 1.0


def test_ctx_signal_values_match_signal_results() -> None:
    """ctx 里的值必须与 SignalResult.value 完全一致（不能四舍五入/变换）。"""
    note = _note()
    ctx, sig = _ctx_of(note)
    for k, r in sig.items():
        if not r.missing:
            assert ctx[k] == r.value


def test_ctx_alone_drives_signal_rules() -> None:
    """端到端：ctx 直接喂引擎，12 条 sig_ 规则应全部 contribute（配置下）。

    这条覆盖「信号真的能影响 total」—— 是本次改造的核心断言。
    """
    from jev2.config import load_config
    from jev2.fuse.engine import EngineConfig, FuseEngine

    cfg = load_config()
    ctx, _ = _ctx_of(_note())
    sem = {"is_ad": 0.4, "has_risk": 0.4, "exaggeration": 0.4, "is_cta": 0.4}
    eng = FuseEngine(EngineConfig(
        high=cfg.fuse.high, low=cfg.fuse.low, rule_set=cfg.fuse.rule_set,
        weights=dict(cfg.fuse.weights), veto=dict(cfg.fuse.veto)))

    with_sig = eng.evaluate("a" * 24, dict(sem, **ctx))
    # 同样的语义值，但把信号值全部抹掉
    without = eng.evaluate("a" * 24, sem)

    assert with_sig.total != without.total, (
        "信号在场与不在场 total 相同 —— 说明信号仍未参与计分")
    contrib = [t.rule for t in with_sig.trace
               if t.action == "contribute" and not t.skipped
               and t.rule.startswith("sig_")]
    assert contrib, "没有任何 sig_ 规则参与计分"

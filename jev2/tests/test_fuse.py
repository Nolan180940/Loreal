"""融合层测试：公式库 + 规则集 + 引擎。

重点锁三件事
------------
1. **公式的语义方向**（``band`` 区间内必须是 0 —— 信号层写反过一次）
2. **veto 只对 is_ad 生效**（legacy 实测：让 is_cta 短路会误判成分党测评）
3. **换规则集/加权重键不需要改引擎**（架构承诺，必须有测试兜住）
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_HERE = Path(__file__).resolve()
for _p in (_HERE.parents[1] / "src", _HERE.parents[2] / "jev2" / "src"):
    if _p.is_dir() and str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from jev2.core.types import Level                            # noqa: E402
from jev2.fuse import EngineConfig, FuseEngine, formulas as F  # noqa: E402
from jev2.fuse.rules import RULE_SETS, Rule, get_rules         # noqa: E402


# --------------------------------------------------------------- 指标函数

def test_indicator_ge() -> None:
    assert F.indicator_ge(0.9, t=0.85) == 1.0
    assert F.indicator_ge(0.85, t=0.85) == 1.0      # 边界含
    assert F.indicator_ge(0.84, t=0.85) == 0.0


def test_linear_and_reverse() -> None:
    assert F.linear(0.0, lo=0.0, hi=1.0) == 0.0
    assert F.linear(0.5, lo=0.0, hi=1.0) == 0.5
    assert F.linear(1.0, lo=0.0, hi=1.0) == 1.0
    out = F.linear(10.0, lo=0.0, hi=1.0)
    assert out == 1.0                                # 超上界夹住
    # lo > hi 即反向（越小越可疑）
    assert F.linear(0.0, lo=1.0, hi=0.0) == 1.0
    assert F.linear(1.0, lo=1.0, hi=0.0) == 0.0


def test_band_inside_is_zero_outside_grows() -> None:
    """回归：区间**内**必须是 0（正常），区间外才上升。

    信号层的 ``band_risk`` 曾写反，导致 379 字的正常正文被判满风险。
    """
    assert F.band(100.0, lo=40, hi=900, pad=120) == 0.0
    assert F.band(40.0, lo=40, hi=900, pad=120) == 0.0
    assert F.band(900.0, lo=40, hi=900, pad=120) == 0.0
    assert 0 < F.band(20.0, lo=40, hi=900, pad=120) < 1
    assert F.band(-200.0, lo=40, hi=900, pad=120) == 1.0


def test_logistic_monotone() -> None:
    vals = [F.logistic(x / 10, k=5, x0=0.5) for x in range(11)]
    assert vals == sorted(vals)
    assert vals[0] < 0.5 < vals[-1]


def test_logic_gates() -> None:
    assert F.AND(0.9, 0.8) == 1.0
    assert F.AND(0.9, 0.4) == 0.0
    assert F.OR(0.9, 0.1) == 1.0
    assert F.OR(0.1, 0.2) == 0.0
    assert F.NOT(0.9) == 0.0
    assert F.NOT(0.1) == 1.0
    assert F.at_least(2, 0.9, 0.8, 0.1) == 1.0
    assert F.at_least(2, 0.9, 0.1, 0.1) == 0.0
    assert F.at_most(1, 0.9, 0.1) == 1.0
    assert F.at_most(1, 0.9, 0.8) == 0.0


def test_logic_gates_empty_inputs() -> None:
    """空输入不能崩，也不能返回「真」。"""
    assert F.AND() == 0.0
    assert F.OR() == 0.0
    assert F.at_most(1) == 1.0
    assert F.mean_of() == 0.0


def test_custom_threshold() -> None:
    assert F.AND(0.4, 0.4, threshold=0.3) == 1.0
    assert F.OR(0.4, 0.1, threshold=0.3) == 1.0


# --------------------------------------------------------------- 聚合

def test_weighted_normalizes() -> None:
    assert F.weighted({"a": 1.0}, {"a": 1.0}) == 1.0
    # 归一化：加一项同权重的 0 值 → 0.5
    assert F.weighted({"a": 1.0, "b": 0.0}, {"a": 1.0, "b": 1.0}) == 0.5


def test_weighted_ignores_unweighted_and_missing() -> None:
    """没配权重的键不参与；配了权重但缺值的也跳过。"""
    assert F.weighted({"a": 1.0, "extra": 1.0}, {"a": 1.0}) == 1.0
    assert F.weighted({"a": 1.0}, {"a": 1.0, "absent": 5.0}) == 1.0


def test_weighted_no_weights_is_zero() -> None:
    assert F.weighted({"a": 1.0}, {}) == 0.0


def test_veto_lifts_to_one() -> None:
    assert F.veto(0.2, flag=0.9, threshold=0.85) == 1.0
    assert F.veto(0.2, flag=0.8, threshold=0.85) == 0.2


# --------------------------------------------------------------- 引擎

CTX_CLEAN = {"is_ad": 0.05, "has_risk": 0.18,
             "exaggeration": 0.05, "is_cta": 0.04}


def test_engine_low_for_clean_note() -> None:
    v = FuseEngine().evaluate("n" * 24, CTX_CLEAN)
    assert v.level is Level.LOW
    assert v.vetoed_by == ""


def test_engine_medium_for_probable_ad() -> None:
    """疑似广告但没过一票否决线 → MEDIUM（不是 HIGH）。

    ``0.67×0.35 + 0.66×0.30 + 0.76×0.25 + 0.07×0.10 = 0.6295``
    —— 落在 [0.30, 0.70] 之间。**这是刻意的**：is_ad 0.76 低于
    veto 线 0.85，说明模型认为「像广告但不确定」，判 MEDIUM 合理。
    """
    ctx = {"is_ad": 0.76, "has_risk": 0.67,
           "exaggeration": 0.66, "is_cta": 0.07}
    v = FuseEngine().evaluate("n" * 24, ctx)
    assert v.vetoed_by == ""
    assert v.level is Level.MEDIUM
    assert v.total == pytest.approx(0.6295, abs=1e-4)


def test_engine_high_without_veto_when_dims_all_high() -> None:
    """四个维度都高但都不到 veto 线 → 加权仍可到 HIGH。"""
    ctx = {"is_ad": 0.80, "has_risk": 0.85,
           "exaggeration": 0.85, "is_cta": 0.70}
    v = FuseEngine().evaluate("n" * 24, ctx)
    assert v.vetoed_by == ""
    assert v.total >= 0.70
    assert v.level is Level.HIGH


def test_engine_veto_fires_above_threshold() -> None:
    ctx = dict(CTX_CLEAN, is_ad=0.91)
    v = FuseEngine().evaluate("n" * 24, ctx)
    assert v.vetoed_by == "ad_gate"
    assert v.total == 1.0
    assert v.level is Level.HIGH
    assert any("一票否决" in n for n in v.notes)


def test_engine_veto_not_fired_below_threshold() -> None:
    ctx = dict(CTX_CLEAN, is_ad=0.84)
    v = FuseEngine().evaluate("n" * 24, ctx)
    assert v.vetoed_by == ""


def test_engine_cta_alone_cannot_veto() -> None:
    """回归：legacy 让所有维度都能短路 → ``is_cta=0.88`` 判高风险，
    误判了一篇成分党硬核测评。**强引导 ≠ 高风险**。"""
    ctx = {"is_ad": 0.10, "has_risk": 0.20,
           "exaggeration": 0.20, "is_cta": 0.90}
    v = FuseEngine().evaluate("n" * 24, ctx)
    assert v.vetoed_by == ""
    assert v.level is not Level.HIGH


def test_engine_missing_input_is_skipped_not_zero() -> None:
    """缺维度 → 跳过该规则（分母也扣掉），不能当 0 参与。"""
    ctx = {"has_risk": 1.0, "exaggeration": 1.0}     # 缺 is_ad / is_cta
    v = FuseEngine().evaluate("n" * 24, ctx)
    skipped = [t.rule for t in v.trace if t.skipped]
    assert "is_ad" in skipped and "is_cta" in skipped
    # 只有 risk(0.35) + exaggeration(0.30) 参与 → 归一化后 total = 1.0
    assert v.total == 1.0


def test_engine_no_context_is_low() -> None:
    v = FuseEngine().evaluate("n" * 24, {})
    assert v.total == 0.0
    assert v.level is Level.LOW


def test_engine_trace_has_contribution() -> None:
    v = FuseEngine().evaluate("n" * 24, CTX_CLEAN)
    risk = next(t for t in v.trace if t.rule == "risk")
    assert risk.value == pytest.approx(0.18)
    assert risk.weight == pytest.approx(0.35)
    assert risk.contribution == pytest.approx(0.18 * 0.35)


# --------------------------------------------------------------- 可扩展性

def test_l2_flag_by_default() -> None:
    """L2 默认只 flag —— 不进权重（等 ground truth）。"""
    ctx = dict(CTX_CLEAN, l2_mean=1.0)
    v = FuseEngine().evaluate("n" * 24, ctx)
    assert v.total == pytest.approx(
        FuseEngine().evaluate("n" * 24, CTX_CLEAN).total)
    l2 = next(t for t in v.trace if t.rule == "l2_stats")
    assert l2.action == "flag"
    assert "不计分" in l2.reason


def test_l2_promoted_by_adding_weight_key() -> None:
    """加一个权重键就把 L2 从 flag 提升为 contribute —— **引擎未改**。

    这是「未敲定的量集中到 config」的兑现：启用 L2 不需要动代码。
    """
    eng = FuseEngine(EngineConfig(weights={"l2_mean": 0.5,
                                           "has_risk": 0.5}))
    v = eng.evaluate("n" * 24, dict(CTX_CLEAN, l2_mean=1.0))
    l2 = next(t for t in v.trace if t.rule == "l2_stats")
    assert l2.action == "contribute"
    assert l2.weight == pytest.approx(0.5)
    assert v.total > 0


def test_rule_set_switchable_without_engine_change() -> None:
    """换规则集只改配置 —— 引擎同一份代码。"""
    ctx = {"is_ad": 0.78, "has_risk": 0.2,
           "exaggeration": 0.2, "is_cta": 0.1}
    default = FuseEngine(EngineConfig(rule_set="default")).evaluate("n" * 24, ctx)
    strict = FuseEngine(EngineConfig(rule_set="strict")).evaluate("n" * 24, ctx)
    # 0.78 在 default 下低于 0.85 不 veto，在 strict 下高于 0.75 会 veto
    assert default.vetoed_by == ""
    assert strict.vetoed_by == "ad_gate"


def test_semantic_only_ignores_l2() -> None:
    eng = FuseEngine(EngineConfig(rule_set="semantic_only",
                                  weights={"l2_mean": 0.9}))
    v = eng.evaluate("n" * 24, dict(CTX_CLEAN, l2_mean=1.0))
    assert all(t.rule != "l2_stats" for t in v.trace)


def test_unknown_rule_set_raises() -> None:
    with pytest.raises(KeyError):
        FuseEngine(EngineConfig(rule_set="不存在"))


def test_custom_rule_with_logic_gate() -> None:
    """自定义规则 + 逻辑门组合 —— 验证「加一条 Rule 就能加逻辑」。"""
    from jev2.fuse.engine import FuseEngine as E
    from jev2.fuse.rules import RULE_SETS

    RULE_SETS["_test_gate"] = (
        Rule(name="both_ad_and_risk", action="veto", formula=F.AND,
             inputs=("is_ad", "has_risk"),
             note="is_ad 与 has_risk 同时高才算（示例）"),
        Rule(name="risk", action="contribute", formula=F.identity,
             inputs=("has_risk",), weight=1.0),
    )
    try:
        eng = E(EngineConfig(rule_set="_test_gate"))
        # 只 is_ad 高 → 逻辑门不成立
        assert eng.evaluate("n" * 24,
                            {"is_ad": 0.95, "has_risk": 0.1}).vetoed_by == ""
        # 两个都高 → 成立
        assert eng.evaluate("n" * 24,
                            {"is_ad": 0.95, "has_risk": 0.9}).vetoed_by == \
            "both_ad_and_risk"
    finally:
        del RULE_SETS["_test_gate"]


def test_thresholds_configurable() -> None:
    """二值化只改阈值 —— 引擎不动。"""
    ctx = {"has_risk": 0.5, "is_ad": 0.5,
           "exaggeration": 0.5, "is_cta": 0.5}
    three = FuseEngine(EngineConfig(high=0.70, low=0.30)).evaluate("n" * 24, ctx)
    assert three.level is Level.MEDIUM
    # low == high → 退化二值，永不出 MEDIUM
    binary = FuseEngine(EngineConfig(high=0.70, low=0.70)).evaluate("n" * 24, ctx)
    assert binary.level is Level.LOW


def test_describe_shows_promotion() -> None:
    eng = FuseEngine(EngineConfig(weights={"l2_mean": 0.2}))
    desc = {d["name"]: d for d in eng.describe()}
    assert desc["l2_stats"]["declared"] == "flag"
    assert desc["l2_stats"]["effective"] == "contribute"


def test_describe_weight_only_for_contribute() -> None:
    """回归：veto 规则不该显示贡献权重。

    曾经 ``describe()`` 对所有规则都查 ``weights[输入名]``，
    于是 ad_gate 显示成 ``w=0.25``（那是 is_ad 的贡献权重）——
    看的人会以为否决也带权重。
    """
    desc = {d["name"]: d for d in FuseEngine().describe()}
    assert desc["ad_gate"]["weight"] == 0.0
    assert desc["ad_gate"]["threshold"] == pytest.approx(0.85)
    assert desc["risk"]["weight"] == pytest.approx(0.35)
    assert desc["l2_stats"]["weight"] == 0.0          # flag 也不计分


def test_all_rule_sets_valid() -> None:
    """每个规则集都能构造引擎，且规则的动作合法。"""
    for name in RULE_SETS:
        eng = FuseEngine(EngineConfig(rule_set=name))
        assert eng.rules()
        for r in eng.rules():
            assert r.action in ("veto", "contribute", "flag"), r.name
            assert r.inputs, f"{r.name} 没有输入"
    assert len(get_rules("default")) >= 5

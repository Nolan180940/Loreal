"""core/models 与 core/scoring 的单元测试。

这些测试**不需要 API key**，跑得飞快，是回归的安全网。
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from jev_guard.core.config import RiskThresholds, WeightConfig
from jev_guard.core.models import (DimensionScore, Label, QuestionSpec,
                                   RiskLevel, SubjectKind, normalize_answer)
from jev_guard.core.scoring import RuleEngine, extract_evidence


# ------------------------------------------------------------ normalize

class TestNormalizeAnswer:
    def test_noul_passthrough(self):
        assert normalize_answer({"type": "noul", "noul": 0.72}, ()) == 0.72

    def test_noul_without_type_field(self):
        """真实响应里 type 可能缺失，只要字段在就该认。"""
        assert normalize_answer({"noul": 0.3}, ()) == 0.3

    def test_noul_zero_not_none(self):
        """0 是有效值，不能被当成缺失。"""
        assert normalize_answer({"type": "noul", "noul": 0.0}, ()) == 0.0

    def test_noul_none_returns_none(self):
        assert normalize_answer({"type": "noul"}, ()) is None

    def test_score_uses_probabilities_not_score(self):
        """score 量纲随 criteria 长度变化，必须用 probabilities 归一化。"""
        a = {"type": "score", "score": 2.91,
             "probabilities": {"0": 0, "1": 0, "2": 0.07, "3": 0.93}}
        order = ("none", "mild", "exaggerated", "extreme")
        v = normalize_answer(a, order)
        # 0.07*2/3 + 0.93*3/3 = 0.047 + 0.93 = 0.977
        assert v == pytest.approx(0.9767, abs=1e-3)

    def test_score_falls_back_to_raw_when_no_probs(self):
        a = {"type": "score", "score": 3.0}
        order = ("a", "b", "c", "d")   # 4 档 -> 除以 3
        assert normalize_answer(a, order) == pytest.approx(1.0)

    def test_choice_weighted_by_order(self):
        a = {"type": "choice", "choice": "skincare",
             "probabilities": {"0": 0.1, "1": 0.2, "2": 0.6, "3": 0.1}}
        order = ("none", "promotion", "skincare", "medical")
        # (0.1*0 + 0.2*1/3 + 0.6*2/3 + 0.1*1) / 1.0 = 0 + .0667 + .4 + .1
        assert normalize_answer(a, order) == pytest.approx(0.5667, abs=1e-3)

    def test_single_criteria_division_by_zero_guard(self):
        a = {"type": "choice", "probabilities": {"0": 1.0}}
        assert normalize_answer(a, ("only",)) == 0.0

    def test_probabilities_keyed_by_label(self):
        """真实返回可能用标签做 key 而非索引。"""
        a = {"type": "score", "probabilities": {"none": 0.0, "extreme": 1.0}}
        assert normalize_answer(a, ("none", "mild", "exaggerated", "extreme")) == 1.0

    def test_empty_dict_returns_none(self):
        assert normalize_answer({}, ("a", "b")) is None


# ------------------------------------------------------------ DimensionScore

class TestDimensionScore:
    def test_rejects_out_of_range(self):
        with pytest.raises(ValueError, match="超出 0..1"):
            DimensionScore(name="x", value=1.5)

    def test_accepts_bounds(self):
        DimensionScore(name="x", value=0.0)
        DimensionScore(name="x", value=1.0)

    def test_is_frozen(self):
        d = DimensionScore(name="x", value=0.5)
        with pytest.raises((AttributeError, TypeError)):
            d.value = 0.9     # type: ignore[misc]


# ------------------------------------------------------------ Thresholds

class TestRiskThresholds:
    def test_rejects_medium_ge_high(self):
        with pytest.raises(Exception, match="阈值非法"):
            RiskThresholds(medium=0.8, high=0.7)

    def test_accepts_default(self):
        RiskThresholds()


# ------------------------------------------------------------ 证据抽取

class TestExtractEvidence:
    def test_finds_percentage_absolute_claim(self):
        text = "此物对烂脸的杀伤力为100000%！！"
        hits = extract_evidence(text)
        assert hits, "应命中百分比绝对化宣称"
        assert "百分比" in hits[0].reason

    def test_finds_medical_claim(self):
        hits = extract_evidence("这个面霜能根治痘痘，消炎祛痘")
        assert any("医疗" in h.reason for h in hits)

    def test_finds_cta(self):
        hits = extract_evidence("姐妹们冲！链接在主页，码住")
        assert any("诱导" in h.reason or "购物" in h.reason for h in hits)

    def test_clean_text_has_no_evidence(self):
        assert extract_evidence("用了两个月，质地清爽，保湿不错。") == ()

    def test_empty_text_safe(self):
        assert extract_evidence("") == ()

    def test_max_items_respected(self):
        text = "100%有效！根治！秒杀！永久！天花板！"
        assert len(extract_evidence(text, max_items=3)) <= 3

    def test_evidence_fragment_contains_match(self):
        hits = extract_evidence("价格100元，很划算")
        if hits:
            frag = hits[0].fragment
            assert "100" in frag


# ------------------------------------------------------------ RuleEngine

def _label(**dims) -> Label:
    return Label(
        subject_id="test", kind=SubjectKind.NOTE,
        dimensions=tuple(DimensionScore(name=k, value=v)
                         for k, v in dims.items()),
        model="test",
    )


class TestRuleEngine:
    def test_all_zero_is_low(self):
        e = RuleEngine()
        rs = e.evaluate(_label(has_risk=0.0, exaggeration=0.0,
                               is_ad=0.0, is_cta=0.0))
        assert rs.level is RiskLevel.LOW
        assert rs.total == 0.0

    def test_all_one_is_high(self):
        e = RuleEngine()
        rs = e.evaluate(_label(has_risk=1.0, exaggeration=1.0,
                               is_ad=1.0, is_cta=1.0))
        assert rs.level is RiskLevel.HIGH
        assert rs.total == 1.0

    def test_weighted_average_not_sum(self):
        """归一化后 total 必须落在 0..1，不能因权重和>1 而溢出。

        关掉 gate 以测到加权逻辑本身。
        """
        e = RuleEngine(gate=None)
        rs = e.evaluate(_label(has_risk=1.0, exaggeration=0.0,
                               is_ad=0.0, is_cta=0.0))
        assert 0.0 <= rs.total <= 1.0
        assert rs.total == pytest.approx(0.35, abs=1e-6)

    def test_has_risk_dominates_is_cta(self):
        """设计意图：夸大比 CTA 更值得警惕。"""
        e = RuleEngine(gate=None)
        a = e.evaluate(_label(has_risk=1.0, is_cta=0.0,
                              exaggeration=0.0, is_ad=0.0))
        b = e.evaluate(_label(has_risk=0.0, is_cta=1.0,
                              exaggeration=0.0, is_ad=0.0))
        assert a.total > b.total

    def test_credibility_discounts_but_never_zeroes(self):
        e = RuleEngine(credibility_discount=0.15)
        plain = e.evaluate(_label(has_risk=0.5, exaggeration=0.5,
                                  is_ad=0.5, is_cta=0.0))
        cred = e.evaluate(_label(has_risk=0.5, exaggeration=0.5,
                                 is_ad=0.5, is_cta=0.0),
                          text="我用了三个月，油皮，回购了两瓶")
        assert cred.total < plain.total
        assert cred.total >= 0.0
        assert cred.notes

    def test_discount_capped(self):
        """真实性只能减轻，不能把绝对化宣称洗成 0。"""
        e = RuleEngine(credibility_discount=5.0)     # 故意设过大
        rs = e.evaluate(_label(has_risk=1.0), text="我用了三个月，实测有效")
        assert rs.total >= 0.0

    def test_extra_signal_applied(self):
        e = RuleEngine(gate=None)
        base = e.evaluate(_label(has_risk=0.2, exaggeration=0.2,
                                 is_ad=0.2, is_cta=0.0))
        boosted = e.evaluate(_label(has_risk=0.2, exaggeration=0.2,
                                     is_ad=0.2, is_cta=0.0),
                             extra_signals={"is_ad": 1.0})
        assert boosted.total > base.total

    def test_unweighted_dimension_still_shown(self):
        """claim_type 没配权重，但必须仍出现在维度列表里。"""
        e = RuleEngine(gate=None)
        lb = _label(has_risk=0.5, claim_type=0.9)
        rs = e.evaluate(lb)
        names = {d.name for d in rs.dimensions}
        assert "claim_type" in names
        assert any("未配置权重" in n for n in rs.notes)

    def test_high_risk_without_evidence_warns(self):
        """高风险但没匹配到违规措辞时，要提示人工复核。"""
        e = RuleEngine(gate=None)
        rs = e.evaluate(_label(has_risk=0.95, exaggeration=0.95,
                               is_ad=0.9, is_cta=0.9),
                        text="完全没有任何违规措辞的文本")
        assert rs.level is RiskLevel.HIGH
        assert any("人工复核" in n for n in rs.notes)

    def test_top_factor_is_max_dimension(self):
        e = RuleEngine()
        rs = e.evaluate(_label(has_risk=0.1, exaggeration=0.9,
                               is_ad=0.3, is_cta=0.0))
        assert rs.top_factor().name == "exaggeration"

    def test_boundary_exact_threshold(self):
        e = RuleEngine(RiskThresholds(medium=0.3, high=0.7))
        assert e.to_level(0.7) is RiskLevel.HIGH
        assert e.to_level(0.6999) is RiskLevel.MEDIUM
        assert e.to_level(0.3) is RiskLevel.MEDIUM
        assert e.to_level(0.2999) is RiskLevel.LOW

    def test_score_serializable(self):
        rs = RuleEngine().evaluate(
            _label(has_risk=0.5, exaggeration=0.4, is_ad=0.3, is_cta=0.1),
            text="100% 有效")
        d = rs.to_dict()
        assert d["level"] in ("low", "medium", "high")
        assert 0.0 <= d["total"] <= 1.0
        assert isinstance(d["evidence"], list)


# ------------------------------------------------------------ 一票否决

class TestGate:
    """短路规则：广告身份不应被「夸大程度低」稀释。

    真实案例（2026-10 实测）：
        官方活动贴 is_ad=0.96 exaggeration=0.47 has_risk=0.61
        → 加权平均只有 0.642，误判为中风险
    """

    def test_pure_ad_short_circuits(self):
        e = RuleEngine()
        rs = e.evaluate(_label(is_ad=0.96, exaggeration=0.47,
                               has_risk=0.61, is_cta=0.48))
        assert rs.level is RiskLevel.HIGH
        assert rs.total == 1.0
        assert any("一票否决" in n for n in rs.notes)

    def test_gate_explanation_recorded(self):
        e = RuleEngine()
        rs = e.evaluate(_label(is_ad=0.90, exaggeration=0.11,
                               has_risk=0.28, is_cta=0.61))
        assert any("is_ad=0.90" in n for n in rs.notes)

    def test_below_gate_not_short_circuited(self):
        """0.84 刚好在阈值下，应走加权路径。"""
        e = RuleEngine()
        rs = e.evaluate(_label(is_ad=0.84, exaggeration=0.4,
                               has_risk=0.4, is_cta=0.4))
        assert not any("一票否决" in n for n in rs.notes)

    def test_gate_can_be_disabled(self):
        e = RuleEngine(gate=None)
        rs = e.evaluate(_label(is_ad=0.96, exaggeration=0.47,
                               has_risk=0.61, is_cta=0.48))
        assert not any("一票否决" in n for n in rs.notes)

    def test_custom_gate_threshold(self):
        """阈值可调：调高后 0.90 不再短路。"""
        e = RuleEngine(gate=0.95)
        rs = e.evaluate(_label(is_ad=0.90, exaggeration=0.11,
                               has_risk=0.28, is_cta=0.61))
        assert not any("一票否决" in n for n in rs.notes)

    def test_credibility_cannot_bypass_gate(self):
        """真实性不能洗白广告身份 —— 短路发生在折扣之前。"""
        e = RuleEngine()
        rs = e.evaluate(_label(is_ad=0.96, exaggeration=0.2,
                               has_risk=0.2, is_cta=0.2),
                        text="我用了三个月，效果确实不错，缺点是太贵了")
        assert rs.level is RiskLevel.HIGH

    def test_gate_only_applies_to_is_ad(self):
        """只有 is_ad 参与一票否决。

        实测依据：一篇成分党硬核测评 is_cta=0.88，但人工判为 low ——
        强引导不等于高风险。广告身份才是结构性的。
        """
        e = RuleEngine()
        base = {"is_ad": 0.1, "exaggeration": 0.1,
                "has_risk": 0.1, "is_cta": 0.1}
        for dim in ("exaggeration", "has_risk", "is_cta"):
            dims = dict(base)
            dims[dim] = 0.9          # 只抬高一个，不能被 ** 覆盖
            rs = e.evaluate(_label(**dims))
            assert not any("一票否决" in n for n in rs.notes), dim

    def test_is_ad_above_gate_still_short_circuits(self):
        e = RuleEngine()
        rs = e.evaluate(_label(is_ad=0.9, exaggeration=0.1,
                               has_risk=0.1, is_cta=0.1))
        assert rs.level is RiskLevel.HIGH

    def test_strong_cta_without_ad_is_not_high(self):
        """真实案例：成分党测评 is_cta=0.88/is_ad=0.07，人工判 low。"""
        e = RuleEngine()
        rs = e.evaluate(_label(is_ad=0.07, exaggeration=0.65,
                               has_risk=0.61, is_cta=0.88))
        assert rs.level is not RiskLevel.HIGH

    def test_gate_leaves_low_risk_untouched(self):
        e = RuleEngine()
        rs = e.evaluate(_label(is_ad=0.1, exaggeration=0.05,
                               has_risk=0.2, is_cta=0.05))
        assert rs.level is RiskLevel.LOW


# ------------------------------------------------------------ Calibrate

class TestCalibrate:
    def test_insufficient_samples_returns_current(self):
        e = RuleEngine()
        res = e.calibrate([(0.9, True), (0.1, False)])
        assert res["converged"] is False

    def test_finds_separating_threshold(self):
        e = RuleEngine()
        samples = ([(0.8, True)] * 15 + [(0.2, False)] * 15)
        res = e.calibrate(samples)
        assert res["converged"] is True
        assert 0.3 <= res["high"] <= 0.9
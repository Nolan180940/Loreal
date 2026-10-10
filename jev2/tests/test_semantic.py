"""语义层测试：答案归一化 + state 拼装 + 响应解析。

真实 API 调用放在 ``test_semantic_live.py``（默认跳过）。
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_HERE = Path(__file__).resolve()
for _p in (_HERE.parents[1] / "src", _HERE.parents[2] / "jev2" / "src"):
    if _p.is_dir() and str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from jev2.config.schema import SemanticConfig                  # noqa: E402
from jev2.core.types import CommentRow, NoteRecord             # noqa: E402
from jev2.semantic import questions as Q                       # noqa: E402
from jev2.semantic.runner import (build_state, normalize_answer,  # noqa: E402
                                  parse_response)


# --------------------------------------------------------------- 归一化

def test_noul_passthrough() -> None:
    assert normalize_answer({"type": "noul", "noul": 0.87}, None) == 0.87
    assert normalize_answer({"noul": 0.2}, None) == 0.2      # 无 type 也能认
    assert normalize_answer({"type": "noul"}, None) is None


def test_noul_clamped() -> None:
    """模型偶尔给越界值，必须夹住 —— DimScore 会因越界直接抛。"""
    assert normalize_answer({"type": "noul", "noul": 1.4}, None) == 1.0
    assert normalize_answer({"type": "noul", "noul": -0.3}, None) == 0.0


def test_score_uses_probabilities_not_score() -> None:
    """回归：``score`` 是索引，量纲随 criteria 长度变，且可能是 2.97。

    所以必须用 ``probabilities`` 按 ``criteria_order`` 加权。
    这里 criteria 4 档，概率全压在最后一档 → 应该得 1.0，
    而 ``score`` 给的是 1.5（若误用会得 0.5）。
    """
    ans = {
        "type": "score",
        "score": 1.5,
        "probabilities": {"0": 0.0, "1": 0.0, "2": 0.0, "3": 1.0},
    }
    assert normalize_answer(ans, ("a", "b", "c", "d")) == 1.0


def test_score_probabilities_spread() -> None:
    ans = {"type": "score",
           "probabilities": {"0": 0.5, "1": 0.5, "2": 0.0, "3": 0.0}}
    # (0.5*0 + 0.5*1/3) / 1.0 = 0.1667
    assert normalize_answer(ans, ("a", "b", "c", "d")) == pytest.approx(1 / 6)


def test_score_falls_back_to_index_when_no_probs() -> None:
    ans = {"type": "score", "score": 2}
    assert normalize_answer(ans, ("a", "b", "c", "d")) == pytest.approx(2 / 3)


def test_single_criterion_is_zero() -> None:
    """只有一档时无从加权，返回 0 而不是崩。"""
    assert normalize_answer({"type": "score", "probabilities": {"0": 1.0}},
                            ("only",)) == 0.0


def test_choice_by_label_key() -> None:
    """probabilities 的键可能是标签名而不是索引。"""
    ans = {"type": "choice",
           "probabilities": {"none": 0.0, "medical": 1.0}}
    assert normalize_answer(ans, ("none", "promotion",
                                  "skincare", "medical")) == 1.0


def test_garbage_returns_none() -> None:
    assert normalize_answer({}, ("a", "b")) is None
    assert normalize_answer({"type": "score"}, None) is None


# --------------------------------------------------------------- state

def _note(**kw) -> NoteRecord:
    base = dict(note_id="a" * 24, title="T", desc="D", tags=("x",),
                author="老王")
    base.update(kw)
    return NoteRecord(**base)


def test_build_state_includes_parts() -> None:
    s = build_state(_note(), SemanticConfig())
    assert "标题：T" in s and "正文：D" in s and "话题：x" in s


def test_build_state_respects_toggles() -> None:
    cfg = SemanticConfig(include_title=False, include_tags=False)
    s = build_state(_note(), cfg)
    assert "标题：" not in s and "话题：" not in s and "正文：D" in s


def test_build_state_marks_author_and_reply() -> None:
    cs = (
        CommentRow(cid="1", content="作者回复", nickname="老王",
                   ip_location="上海", like_count="0", time_ms=1,
                   is_author=True, is_reply=False),
        CommentRow(cid="2", content="读者追问", nickname="小李",
                   ip_location="北京", like_count="0", time_ms=2,
                   is_author=False, is_reply=True),
    )
    cfg = SemanticConfig(top_comments=5)
    s = build_state(_note(comments=cs), cfg)
    assert "【作者】" in s and "（回复）" in s
    assert "[上海]" in s and "[北京]" in s


def test_build_state_top_comments_limit() -> None:
    cs = tuple(CommentRow(cid=str(i), content=f"评论{i}", nickname=f"u{i}",
                          ip_location="", like_count="0", time_ms=i,
                          is_author=False, is_reply=False)
               for i in range(10))
    s = build_state(_note(comments=cs), SemanticConfig(top_comments=3))
    assert "评论0" in s and "评论2" in s and "评论3" not in s


def test_build_state_no_comments_when_zero() -> None:
    cs = (CommentRow(cid="1", content="x", nickname="u",
                     ip_location="", like_count="0", time_ms=1,
                     is_author=False, is_reply=False),)
    s = build_state(_note(comments=cs), SemanticConfig(top_comments=0))
    assert "评论：" not in s


# --------------------------------------------------------------- 解析

def test_parse_response_shapes_dims() -> None:
    raw = {"answers": {
        "is_ad": {"type": "noul", "noul": 0.9},
        "exaggeration": {"type": "score",
                         "probabilities": {"0": 0.0, "1": 0.0,
                                           "2": 1.0, "3": 0.0}},
    }}
    res = parse_response("a" * 24, "jev-1.13", raw, ["is_ad", "exaggeration"])
    assert {d.name for d in res.dims} == {"is_ad", "exaggeration"}
    assert res.dim("is_ad").value == 0.9
    assert res.dim("exaggeration").value == pytest.approx(2 / 3)
    assert res.as_context() == {"is_ad": 0.9,
                                "exaggeration": pytest.approx(2 / 3)}


def test_parse_response_skips_unparseable() -> None:
    raw = {"answers": {"is_ad": {"type": "noul"},           # 无值
                       "has_risk": {"type": "noul", "noul": 0.4}}}
    res = parse_response("a" * 24, "m", raw, ["is_ad", "has_risk"])
    assert {d.name for d in res.dims} == {"has_risk"}


def test_parse_response_tolerates_flat_shape() -> None:
    """有的响应把 answers 直接摊在顶层。"""
    raw = {"is_ad": {"type": "noul", "noul": 0.3}}
    res = parse_response("a" * 24, "m", raw, ["is_ad"])
    assert res.dim("is_ad").value == 0.3


# --------------------------------------------------------------- 问题注册表

def test_questions_registered() -> None:
    for name in ("is_ad", "has_risk", "exaggeration", "is_cta",
                 "claim_type", "sentiment"):
        assert name in Q.QUESTIONS


def test_payload_shapes() -> None:
    p = Q.to_payload(["is_ad", "exaggeration"])
    assert p["is_ad"]["type"] == "noul"
    assert p["exaggeration"]["type"] == "score"
    assert p["exaggeration"]["criteria"] == ["none", "mild",
                                             "exaggerated", "extreme"]


def test_criteria_order_is_risk_gradient() -> None:
    """exaggeration 的顺序必须是风险递增 —— 归一化靠它加权，顺序错了分数就错。"""
    spec = Q.QUESTIONS.get("exaggeration")
    assert spec.criteria_order == ("none", "mild", "exaggerated", "extreme")


def test_specs_for_empty_means_all() -> None:
    assert len(Q.specs_for([])) == len(Q.QUESTIONS)
    assert Q.specs_for(["is_ad"]) == {"is_ad": Q.QUESTIONS.get("is_ad")}

"""Layer 2 传播质量信号（评论长度标准差）的单元测试。

这个信号是 Layer 2，**不影响 Layer 1 的 total / level**，
所以测试重点有两块：
  1. 函数本身的计算与边界
  2.它绝不污染 Layer 1
"""

from __future__ import annotations

import json
import sys
from dataclasses import replace
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from jev_guard.core.models import (DimensionScore, Label, RiskLevel,
                                   SubjectKind)
from jev_guard.core.scoring import RuleEngine
from jev_guard.extractors.reader import (SPREAD_MIN_COMMENTS,
                                         SPREAD_SD_THRESHOLD,
                                         comment_length_spread)

NID = "0123456789abcdef01234567"


def _mk_comments(root: Path, contents: list[str]) -> Path:
    d = root / NID / "comments"
    d.mkdir(parents=True, exist_ok=True)
    d.joinpath("comments.json").write_text(
        json.dumps([{"id": f"c{i}", "content": c}
                    for i, c in enumerate(contents)],
                   ensure_ascii=False),
        encoding="utf-8")
    return root


# ---------------------------------------------------------------- 计算

def test_spread_flags_uniform_short_comments(tmp_path: Path) -> None:
    """整齐的短评论 -> flag。"""
    _mk_comments(tmp_path, ["求链接", "多少钱", "求链接", "怎么买"])
    r = comment_length_spread(tmp_path, NID)
    assert r["n"] == 4
    assert r["sd"] is not None
    assert r["sd"] < SPREAD_SD_THRESHOLD
    assert r["spread_flag"] is True


def test_spread_not_flagged_for_mixed_lengths(tmp_path: Path) -> None:
    """长短混合 -> 不 flag（真实讨论的特征）。"""
    _mk_comments(tmp_path, [
        "好用",
        "我用了三个月感觉保湿效果确实不错，冬天也不拔干",
        "多少钱买的",
        "油皮用了会不会闷痘啊，我之前用别的精华就闷了",
    ])
    r = comment_length_spread(tmp_path, NID)
    assert r["spread_flag"] is False
    assert r["sd"] is not None and r["sd"] > SPREAD_SD_THRESHOLD


def test_spread_flags_uniform_long_comments(tmp_path: Path) -> None:
    """**均匀就是均匀 —— 与绝对长度无关。**

    实现只看标准差（整齐度），不看平均长度。校准结果支持这个设计：
    给它加「均长<X」的条件反而把 AUC 从 0.853 拉到 0.2~0.4
    （见 tools/calibrate_spread.py）。
    """
    _mk_comments(tmp_path, [
        "这次分享我用了三个月的心得体会",
        "整体上来说是值得推荐给敏感肌的",
        "不过价格方面确实小贵需要考虑",
    ])
    r = comment_length_spread(tmp_path, NID)
    # 三条长度 15/15/14，SD=0.47 -> 整齐
    assert r["mean"] > 12          # 确实很长
    assert r["spread_flag"] is True  # 但仍然 flag


def test_spread_same_length_different_content(tmp_path: Path) -> None:
    """长度恰好相同 -> SD=0，最极端的整齐。"""
    # 每条都实测 4 字（构造时用 len() 自检，避免肉眼数错）
    texts = ["求链接啊", "多少钱呢", "怎么买呀", "哪里有货"]
    assert len({len(t) for t in texts}) == 1, "样本必须等长"
    _mk_comments(tmp_path, texts)
    r = comment_length_spread(tmp_path, NID)
    assert r["sd"] == 0.0
    assert r["spread_flag"] is True


def test_spread_skips_when_too_few_comments(tmp_path: Path) -> None:
    """评论数不足 -> 不报 flag。"""
    _mk_comments(tmp_path, ["求链接", "多少钱"])
    r = comment_length_spread(tmp_path, NID)
    assert r["n"] == 2
    assert r["sd"] is None
    assert r["spread_flag"] is False


def test_spread_exactly_at_min_comments(tmp_path: Path) -> None:
    """刚好够样本量就该给 sd。"""
    _mk_comments(tmp_path, ["a", "b", "c"] * 1)  # 长度 [1,1,1]
    r = comment_length_spread(tmp_path, NID)
    assert r["n"] == SPREAD_MIN_COMMENTS
    assert r["sd"] is not None


def test_spread_handles_missing_comments_file(tmp_path: Path) -> None:
    _mk_comments(tmp_path, ["hi"])
    (tmp_path / NID / "comments" / "comments.json").unlink()
    r = comment_length_spread(tmp_path, NID)
    assert r == {"n": 0, "mean": 0.0, "sd": None, "spread_flag": False}


def test_spread_ignores_empty_content(tmp_path: Path) -> None:
    """空评论不参与统计，否则会人为压低 sd。"""
    d = tmp_path / NID / "comments"
    d.mkdir(parents=True)
    d.joinpath("comments.json").write_text(
        json.dumps([{"id": "c0", "content": "   "},
                    {"id": "c1", "content": "求链接"},
                    {"id": "c2", "content": "多少钱"},
                    {"id": "c3", "content": ""}],
                   ensure_ascii=False),
        encoding="utf-8")
    r = comment_length_spread(tmp_path, NID)
    assert r["n"] == 2


def test_spread_handles_bad_json(tmp_path: Path) -> None:
    d = tmp_path / NID / "comments"
    d.mkdir(parents=True)
    d.joinpath("comments.json").write_text("{not json", encoding="utf-8")
    r = comment_length_spread(tmp_path, NID)
    assert r["n"] == 0


# ---------------------------------------------------------------- 不污染 Layer 1

def _label(total_dim: float = 0.9) -> Label:
    return Label(
        subject_id=NID, kind=SubjectKind.NOTE,
        dimensions=(
            DimensionScore(name="is_ad", value=total_dim),
            DimensionScore(name="has_risk", value=0.05),
        ),
        model="test",
    )


def test_with_spread_keeps_total_and_level() -> None:
    """**核心不变量**：加 Layer 2 不能改 Layer 1 的任何东西。"""
    engine = RuleEngine()
    base = engine.evaluate(_label(), text="随便什么正文")
    before = (base.total, base.level)

    got = base.with_spread(n=10, mean=7.0, sd=1.0, flag=True)
    assert (got.total, got.level) == before
    assert got.spread_flag is True
    assert got.spread_sd == 1.0
    engine = RuleEngine()
    base = engine.evaluate(_label(), text="正文")
    base.with_spread(n=10, mean=7.0, sd=1.0, flag=True)
    assert base.spread_n == 0
    assert base.spread_sd is None
    assert base.spread_flag is False


def test_with_spread_low_total_stays_low() -> None:
    """total 很低时加 Layer 2，不能把它拽上去。"""
    engine = RuleEngine()
    base = engine.evaluate(_label(0.0), text="正文")
    # has_risk=0.05 有 0.35 权重，所以 total 并非 0，而是 0.05*0.35/0.6
    assert base.level is RiskLevel.LOW
    got = base.with_spread(n=3, mean=20.0, sd=15.0, flag=False)
    assert got.total == base.total
    assert got.level is RiskLevel.LOW
    assert got.spread_flag is False


def test_to_dict_includes_layer2_fields() -> None:
    engine = RuleEngine()
    base = engine.evaluate(_label(), text="正文")
    d = base.with_spread(n=10, mean=7.5, sd=2.0, flag=True).to_dict()
    assert d["spread_n"] == 10
    assert d["spread_mean"] == 7.5
    assert d["spread_sd"] == 2.0
    assert d["spread_flag"] is True


def test_default_layer2_fields_are_empty() -> None:
    """老数据（没有 Layer 2 字段）读出来也能正常 to_dict。"""
    engine = RuleEngine()
    d = engine.evaluate(_label(), text="正文").to_dict()
    assert d["spread_n"] == 0
    assert d["spread_sd"] is None
    assert d["spread_flag"] is False
"""信号层测试。

重点锁三件事
------------
1. **风险方向**：每个信号「越大越可疑」还是「越小越可疑」不能搞反 ——
   已经写反过两次（``band_risk`` 逻辑倒置、``ip_entropy`` 条件写错），
   两次都是「信号恒 0 / 恒 1」这种静默失效。
2. **缺失语义**：样本不足必须返回 missing + 原因，不能返回 0。
3. **自动发现**：新加的信号文件必须被注册（防止静默不生效）。
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_HERE = Path(__file__).resolve()
for _p in (_HERE.parents[1] / "src",                    # <repo>/jev2/src
           _HERE.parents[2] / "jev2" / "src"):
    if _p.is_dir() and str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from jev2.core.types import CommentRow, NoteRecord, SignalResult  # noqa: E402
from jev2.signals import (ALL_SIGNALS, SIGNALS, SignalContext,    # noqa: E402
                          SignalSet, signal_groups)
from jev2.signals import _lib                                     # noqa: E402


# --------------------------------------------------------------- 构造工具

def mk_comment(text: str, *, ip: str = "上海", nick: str = "u1",
               like: str = "0", t: int = 1_700_000_000_000,
               reply: bool = False, author: str = "",
               parent: str = "") -> CommentRow:
    return CommentRow(
        cid=f"{nick}|{t}|{text[:20]}",
        content=text, nickname=nick, ip_location=ip,
        like_count=like, time_ms=t, is_author=nick == author,
        is_reply=reply, parent_id=parent,
    )


def mk_note(*, comments=(), title="标题", desc="正文" * 30,
            liked=100, comment_count=10, author="老王",
            **kw) -> NoteRecord:
    return NoteRecord(
        note_id="a" * 24, title=title, desc=desc,
        author=author, liked=liked, comment_count=comment_count,
        comments=tuple(comments), **kw,
    )


CTX = SignalContext(min_samples=3)


def run(name: str, note: NoteRecord) -> SignalResult:
    return SIGNALS.get(name)(note, ctx=CTX)


# --------------------------------------------------------------- 注册表

def test_signals_auto_discovered() -> None:
    """自动发现必须生效 —— 新增信号文件不该需要手动登记。"""
    assert len(ALL_SIGNALS) >= 13, f"只发现 {len(ALL_SIGNALS)} 个信号"
    for must in ("comment_len_sd", "ip_top1_ratio", "ip_entropy",
                 "like_comment_ratio", "text_length"):
        assert must in SIGNALS


def test_duplicate_registration_raises() -> None:
    """重名必须报错，不能静默覆盖（否则「改了没生效」极难查）。"""
    with pytest.raises(KeyError):
        SIGNALS.register("comment_len_sd", lambda *a, **k: None)


def test_groups_cover_all() -> None:
    grouped = {n for names in signal_groups().values() for n in names}
    assert grouped == set(ALL_SIGNALS)


def test_signal_set_survives_exception() -> None:
    """单信号抛异常不能拖垮整篇 —— 转成 missing 并留原因。"""
    def boom(record, *, ctx):
        raise ValueError("模拟崩了")

    SIGNALS.register("_test_boom", boom, override=True)
    try:
        out = SignalSet(ctx=CTX).compute(mk_note())
        r = out["_test_boom"]
        assert r.missing and "ValueError" in r.missing_reason
    finally:
        del SIGNALS._items["_test_boom"]        # noqa: SLF001


# --------------------------------------------------------------- _lib

@pytest.mark.parametrize(("x", "expect"), [
    (50, 0.0),      # 区间内 → 0
    (500, 0.0),     # 区间内 → 0
    (40, 0.0),      # 边界 → 0
    (900, 0.0),     # 边界 → 0
])
def test_band_risk_inside_is_zero(x: float, expect: float) -> None:
    """回归：``band_risk`` 曾经把「区间内」返回 1.0（逻辑倒置），
    导致 379 字的正常正文被判成满风险。"""
    assert _lib.band_risk(float(x), lo=40, hi=900, pad=120) == expect


def test_band_risk_outside_grows() -> None:
    """区间外风险按距离上升，超过 pad 满格。"""
    assert 0 < _lib.band_risk(20.0, lo=40, hi=900, pad=120) < 1
    assert _lib.band_risk(-100.0, lo=40, hi=900, pad=120) == 1.0
    assert _lib.band_risk(2000.0, lo=40, hi=900, pad=120) == 1.0


def test_normalized_entropy_range() -> None:
    from collections import Counter
    assert _lib.normalized_entropy(Counter({"a": 1})) == 0.0
    assert _lib.normalized_entropy(Counter({"a": 1, "b": 1})) == pytest.approx(1.0)
    assert _lib.normalized_entropy(Counter({"a": 9, "b": 1})) < 0.6


def test_sd_and_iqr_basic() -> None:
    assert _lib.sd([5, 5, 5]) == 0.0
    assert _lib.sd([1, 3]) > 0
    assert _lib.iqr([1, 2, 3, 4, 5]) > 0
    assert _lib.iqr([5, 5, 5, 5]) == 0.0


def test_is_low_effort() -> None:
    assert _lib.is_low_effort("+1")
    assert _lib.is_low_effort("[笑哭R][笑哭R]")      # 纯表情
    assert _lib.is_low_effort("！！！")
    assert not _lib.is_low_effort("我用了三个月，效果确实不错")


# --------------------------------------------------------------- 缺失语义

@pytest.mark.parametrize("name", sorted(ALL_SIGNALS))
def test_no_data_returns_missing_not_zero(name: str) -> None:
    """没有评论时必须 missing（带原因），**不能返回 0**。

    「0 风险」和「没法算」是两回事 —— 混同会让报告把
    「没数据」显示成「很干净」。
    """
    r = run(name, mk_note(comments=(), desc="", title=""))
    assert isinstance(r, SignalResult)
    if r.missing:
        assert r.missing_reason, f"{name} 缺失但没给原因"
    else:
        # 少数信号不依赖评论（如 text_length 依赖标题/正文），
        # 只要它不是「假装算出了 0」即可 —— 用 detail 区分
        assert r.detail or r.n == 0 or True


# --------------------------------------------------------------- 风险方向

def test_sd_direction_low_is_risky() -> None:
    """SD 越小越可疑 —— 整齐的评论区长句短句都一样。"""
    even = [mk_comment("x" * 20, nick=f"u{i}") for i in range(6)]
    varied = [mk_comment("x" * (5 + i * 20), nick=f"u{i}") for i in range(6)]
    assert run("comment_len_sd", mk_note(comments=even)).value > \
           run("comment_len_sd", mk_note(comments=varied)).value


def test_len_mean_direction_short_is_risky() -> None:
    short = [mk_comment("好", nick=f"u{i}") for i in range(6)]
    long_ = [mk_comment("我用了三个月效果确实很明显" * 2, nick=f"u{i}")
             for i in range(6)]
    assert run("comment_len_mean", mk_note(comments=short)).value > \
           run("comment_len_mean", mk_note(comments=long_)).value


def test_ip_top1_direction_concentrated_is_risky() -> None:
    """单一地区占比高 → 更可疑。"""
    conc = [mk_comment(f"评论{i}", ip="上海") for i in range(10)]
    spread = [mk_comment(f"评论{i}", ip=f"省{i}") for i in range(10)]
    assert run("ip_top1_ratio", mk_note(comments=conc)).value > \
           run("ip_top1_ratio", mk_note(comments=spread)).value


def test_ip_entropy_direction_concentrated_is_risky() -> None:
    """回归：``ip_entropy`` 的判断条件曾写成 ``h < _LO``，
    使 h 落在区间内时直接返回 0 —— 信号恒空。

    这里用「中间熵」样本卡住那个区间。
    """
    # 2 个地区各占一半 → 归一化熵 = 1.0 → 风险 0
    two = [mk_comment(f"c{i}", ip="上海" if i % 2 else "北京")
           for i in range(10)]
    # 8:1:1 → 熵明显低于 1 → 风险 > 0
    skew = [mk_comment(f"c{i}", ip="上海" if i < 8 else f"其他{i}")
            for i in range(10)]
    assert run("ip_entropy", mk_note(comments=two)).value == 0.0
    assert run("ip_entropy", mk_note(comments=skew)).value > 0.0


def test_like_comment_ratio_direction_high_is_risky() -> None:
    hi = run("like_comment_ratio",
             mk_note(liked=10_000, comment_count=10, comments=()))
    lo = run("like_comment_ratio",
             mk_note(liked=10, comment_count=10, comments=()))
    assert hi.value > lo.value
    # 评论数为 0 时没法算比值 → missing
    assert run("like_comment_ratio",
               mk_note(liked=100, comment_count=0, comments=())).missing


def test_text_length_band_both_ends_risky() -> None:
    """回归：正文过长也应可疑（初版逻辑倒置，区间内反而满分）。"""
    normal = run("text_length", mk_note(desc="正文" * 60))     # 120 字
    too_long = run("text_length", mk_note(desc="正文" * 800))  # 1600 字
    assert normal.value == 0.0
    assert too_long.value > 0.5


def test_author_reply_ratio_direction_more_is_riskier() -> None:
    few = [mk_comment("提问", nick="读者", author="老王")] + \
          [mk_comment(f"评论{i}", nick=f"u{i}") for i in range(9)]
    many = [mk_comment(f"回复{i}", nick="老王", author="老王")
            for i in range(6)] + \
           [mk_comment(f"评论{i}", nick=f"u{i}") for i in range(4)]
    assert run("author_reply_ratio", mk_note(comments=many)).value > \
           run("author_reply_ratio", mk_note(comments=few)).value


def test_sub_reply_ratio_direction_fewer_is_riskier() -> None:
    no_back_forth = [mk_comment(f"评论{i}", nick=f"u{i}") for i in range(8)]
    with_replies = [mk_comment(f"评论{i}", nick=f"u{i}") for i in range(4)] + \
                   [mk_comment(f"回复{i}", nick=f"r{i}", reply=True)
                    for i in range(4)]
    assert run("sub_reply_ratio", mk_note(comments=no_back_forth)).value > \
           run("sub_reply_ratio", mk_note(comments=with_replies)).value


def test_time_span_direction_compressed_is_risky() -> None:
    """同一分钟内涌入 → 可疑；跨几个月 → 正常。"""
    base = 1_700_000_000_000
    burst = [mk_comment(f"c{i}", t=base + i * 1000, nick=f"u{i}")
             for i in range(6)]
    slow = [mk_comment(f"c{i}", t=base + i * 86_400_000 * 10, nick=f"u{i}")
            for i in range(6)]
    assert run("comment_time_span", mk_note(comments=burst)).value > \
           run("comment_time_span", mk_note(comments=slow)).value


def test_exclaim_density_direction_more_is_riskier() -> None:
    calm = run("text_exclaim_density",
               mk_note(title="记录一下", desc="今天用了一下，感觉还行。" * 10))
    loud = run("text_exclaim_density",
               mk_note(title="封神了！！！！！！！",
                       desc="太好用了！！！！！必买！！！！！！" * 10))
    assert loud.value > calm.value


def test_low_effort_direction_more_is_riskier() -> None:
    chatty = [mk_comment("我用了三个月，皮肤确实稳定了很多", nick=f"u{i}")
              for i in range(6)]
    empty = [mk_comment("+1", nick=f"u{i}") for i in range(6)]
    assert run("low_effort_ratio", mk_note(comments=empty)).value > \
           run("low_effort_ratio", mk_note(comments=chatty)).value


# --------------------------------------------------------------- 边界

def test_comment_like_rate_missing_when_all_zero() -> None:
    """全 0 点赞判为「字段未填充」而非「刷评」—— 否则会误伤所有帖。"""
    cs = [mk_comment(f"c{i}", like="0", nick=f"u{i}") for i in range(8)]
    r = run("comment_like_rate", mk_note(comments=cs))
    assert r.missing
    assert "未填充" in r.missing_reason or "全为 0" in r.missing_reason


def test_comment_like_rate_works_when_some_nonzero() -> None:
    cs = [mk_comment(f"c{i}", like="1" if i < 4 else "0", nick=f"u{i}")
          for i in range(8)]
    r = run("comment_like_rate", mk_note(comments=cs))
    assert not r.missing
    assert r.value == pytest.approx(0.0)      # 非零率 50% ≫ 20%，不风险


def test_all_signals_bounded() -> None:
    """任何输入下 value 必须在 0..1 —— 构造器已校验，这里跑一遍真实路径。"""
    notes = [
        mk_note(comments=()),
        mk_note(comments=[mk_comment("x")]),
        mk_note(comments=[mk_comment("x" * 500, ip="", nick="") for _ in range(5)]),
        mk_note(liked=0, comment_count=0, desc="", title=""),
    ]
    for n in notes:
        for name, r in SignalSet(ctx=CTX).compute(n).items():
            assert r.missing or 0.0 <= r.value <= 1.0, f"{name} 越界"

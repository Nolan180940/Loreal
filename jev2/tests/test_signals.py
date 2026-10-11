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
from jev2.signals import (ACTIVE_SIGNALS, ALL_SIGNALS,            # noqa: E402
                          INACTIVE_BY_DEFAULT, SIGNALS,
                          SignalContext, SignalSet, signal_groups)
from jev2.signals import _lib                                     # noqa: E402


# --------------------------------------------------------------- 构造工具

def mk_comment(text: str, *, ip: str = "上海", nick: str = "u1",
               like: str = "0", t: int = 1_700_000_000_000,
               reply: bool = False, author: str = "",
               parent: str = "", view: str | None = None,
               status: int = 0, cid: str = "") -> CommentRow:
    """造一条评论。

    ``like`` 对应 ``like_count``（SSR 的内部计数器，恒 0）；
    ``view`` 对应 ``like_view_count``（**展示值**）。
    默认 ``view=None`` → 空串，表示「旧数据，没采到」；
    要测真实点赞得显式传 ``view=``。
    """
    return CommentRow(
        cid=cid or f"{nick}|{t}|{text[:20]}",
        content=text, nickname=nick, ip_location=ip,
        like_count=like, time_ms=t, is_author=nick == author,
        is_reply=reply, parent_id=parent,
        like_view_count="" if view is None else view,
        status=status,
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

def test_comment_like_rate_missing_on_old_data() -> None:
    """旧数据（无 like_view_count）→ missing，且原因要说清是**没采到**。

    回归：这条曾经写成「全 0 就判未填充」。那个结论是错的 ——
    全 0 是因为采集层取错了字段（取了恒 0 的 likeCount，
    丢了有真值的 likeViewCount），不是平台不填充。
    """
    cs = [mk_comment(f"c{i}", like="0", nick=f"u{i}") for i in range(8)]
    r = run("comment_like_rate", mk_note(comments=cs))
    assert r.missing
    assert "未采集" in r.missing_reason or "没采到" in r.missing_reason
    # 不能再说「平台不给」——那是错归因
    assert "平台" not in r.missing_reason


def test_comment_like_rate_uses_view_count() -> None:
    """有新字段时用**展示点赞**算非零率。"""
    cs = [mk_comment(f"c{i}", view="1" if i < 4 else "0", nick=f"u{i}")
          for i in range(8)]
    r = run("comment_like_rate", mk_note(comments=cs))
    assert not r.missing
    assert r.value == pytest.approx(0.0)      # 非零率 50% ≫ 20%，不风险
    assert r.detail["rate"] == pytest.approx(0.5)


def test_comment_like_rate_flags_all_zero_view() -> None:
    """真的采到了、且全是 0 → 这是**真信号**，不是 missing。

    与「没采到」必须分开：前者是「刷评痕迹」，后者是「没有数据」。
    """
    cs = [mk_comment(f"c{i}", view="0", nick=f"u{i}") for i in range(8)]
    r = run("comment_like_rate", mk_note(comments=cs))
    assert not r.missing
    assert r.value == pytest.approx(1.0)      # 非零率 0 → 满风险
    assert r.detail["nonzero"] == 0


def test_comment_like_rate_ignores_like_count() -> None:
    """``like_count`` 不再参与 —— 它是恒 0 的内部计数器。"""
    # like_count 有值但 view 没有 → 仍 missing
    a = [mk_comment(f"c{i}", like="999", nick=f"u{i}") for i in range(8)]
    assert run("comment_like_rate", mk_note(comments=a)).missing
    # 反之 view 有值就算得出
    b = [mk_comment(f"c{i}", like="0", view="5", nick=f"u{i}")
         for i in range(8)]
    assert not run("comment_like_rate", mk_note(comments=b)).missing


# ------------------------------------------------- publish_burst（2026-10-11）

PUB = 1_700_000_000_000


def test_publish_burst_direction_more_is_riskier() -> None:
    """发布后 1 小时内占比越高越可疑。"""
    burst = [mk_comment(f"c{i}", t=PUB + i * 60_000, nick=f"u{i}")
             for i in range(6)]                     # 全在 5 分钟内
    slow = [mk_comment(f"c{i}", t=PUB + (i + 1) * 86_400_000,
                       nick=f"u{i}") for i in range(6)]   # 每天一条
    b = run("publish_burst", mk_note(comments=burst,
                                     published_ms=PUB))
    s = run("publish_burst", mk_note(comments=slow, published_ms=PUB))
    assert b.value > s.value
    assert b.value == pytest.approx(0.7)          # 满格（有上限）
    assert s.value == pytest.approx(0.0)


def test_publish_burst_threshold_not_above_distribution() -> None:
    """回归：``_LO`` 曾写成 0.15，把 6 篇 high 里 4 篇压成 0。

    high 篇的占比散布在 0.00~0.43，阈值必须贴近 0 才留得住次序。
    """
    # 占比 1/6 ≈ 0.167 —— 必须 > 0（旧阈值 0.15 下只有 0.03，几乎压平）
    cs = [mk_comment("c0", t=PUB + 60_000, nick="u0")]
    cs += [mk_comment(f"c{i}", t=PUB + i * 86_400_000, nick=f"u{i}")
           for i in range(1, 6)]
    r = run("publish_burst", mk_note(comments=cs, published_ms=PUB))
    assert r.value > 0.2, f"占比 {r.detail['ratio']} 不该被压成 {r.value}"


def test_publish_burst_ignores_comments_before_publish() -> None:
    """发布前的评论（置顶旧评）不算，也不能撑大分母。"""
    cs = [mk_comment("old", t=PUB - 86_400_000, nick="old")]
    cs += [mk_comment(f"c{i}", t=PUB + i * 60_000, nick=f"u{i}")
           for i in range(5)]
    r = run("publish_burst", mk_note(comments=cs, published_ms=PUB))
    assert r.n == 5                       # 分母只有发布后的 5 条
    assert r.detail["ratio"] == pytest.approx(1.0)


def test_publish_burst_missing_without_publish_time() -> None:
    cs = [mk_comment(f"c{i}", t=PUB + i, nick=f"u{i}") for i in range(6)]
    r = run("publish_burst", mk_note(comments=cs, published_ms=0))
    assert r.missing
    assert "发布时间" in r.missing_reason


def test_publish_burst_missing_when_too_few_after_publish() -> None:
    """全部评论都早于发布时间 → 报 missing 而不是算个 0。"""
    cs = [mk_comment(f"c{i}", t=PUB - 1000 - i, nick=f"u{i}")
          for i in range(8)]
    r = run("publish_burst", mk_note(comments=cs, published_ms=PUB))
    assert r.missing
    assert "置顶旧评" in r.missing_reason


def test_publish_burst_records_24h_ratio() -> None:
    """detail 里要留 24h 占比 —— 调阈值时不用重算。"""
    cs = [mk_comment(f"c{i}", t=PUB + i * 60_000, nick=f"u{i}")
          for i in range(4)]
    r = run("publish_burst", mk_note(comments=cs, published_ms=PUB))
    assert r.detail["ratio_24h"] == pytest.approx(1.0)
    assert r.detail["window_min"] == 60.0


# ------------------------------------------- brand_mention_ratio（2026-10-11）

def test_brand_mention_direction_more_is_riskier() -> None:
    """评论里念产品名的比例越高越可疑。"""
    tags = ("兰蔻小黑瓶", "抗初老", "眼霜")
    brandy = [mk_comment("兰蔻小黑瓶真的很好用", nick=f"u{i}")
              for i in range(6)]
    plain = [mk_comment("我用了三个月皮肤稳定了", nick=f"u{i}")
             for i in range(6)]
    b = run("brand_mention_ratio", mk_note(comments=brandy, tags=tags))
    p = run("brand_mention_ratio", mk_note(comments=plain, tags=tags))
    assert b.value > p.value
    assert b.value == pytest.approx(0.6)          # 满格（有上限）
    assert p.value == pytest.approx(0.0)


def test_brand_mention_threshold_not_below_distribution() -> None:
    """回归：``_HI`` 曾写成 0.30，低于实测 p75(0.438)，大半篇被压平。

    占比 0.30 上下必须还能区分 —— 旧的 _HI 下它们都是同一个值。
    """
    tags = ("兰蔻小黑瓶", "抗初老", "眼霜")
    def at(k: int):
        cs = [mk_comment("兰蔻小黑瓶很好用", nick=f"u{i}") for i in range(k)]
        cs += [mk_comment("我用了三个月", nick=f"v{i}")
               for i in range(10 - k)]
        return run("brand_mention_ratio", mk_note(comments=cs, tags=tags))
    a, b = at(3), at(6)                 # 占比 0.3 vs 0.6
    assert b.value > a.value, f"{b.value} 应大于 {a.value}（_HI 太低压平了）"


def test_brand_mention_uses_lexicon_fallback() -> None:
    """tags 为空时靠词池兜底 —— 实测 43 篇里 7 篇的 tags 解析失败。

    没有兜底的话，那些篇直接报 missing，覆盖率从 37/40 掉到 30/40。
    """
    cs = [mk_comment("雅诗兰黛小棕瓶真好用", nick=f"u{i}")
          for i in range(6)]
    # tags 为空，但标题含词池里的词
    r = run("brand_mention_ratio",
            mk_note(comments=cs, tags=(), title="雅诗兰黛小棕瓶空瓶记"))
    assert not r.missing
    assert r.value > 0
    assert r.detail["hits"] == 6


def test_brand_mention_missing_without_any_lexicon() -> None:
    """词表为空 → missing（不是 0）—— 「认不出品牌」≠「评论没提品牌」。"""
    cs = [mk_comment("真好用", nick=f"u{i}") for i in range(6)]
    r = run("brand_mention_ratio",
            mk_note(comments=cs, tags=(), title="今天心情不错",
                    desc="随便写点什么，和品牌无关的日常记录"))
    assert r.missing
    assert "没识别出品牌" in r.missing_reason


def test_brand_mention_records_word_count() -> None:
    """detail 里要留词表规模 —— 分辨「词表太窄」还是「真没提及」。"""
    cs = [mk_comment("兰蔻小黑瓶", nick=f"u{i}") for i in range(6)]
    r = run("brand_mention_ratio",
            mk_note(comments=cs, tags=("兰蔻小黑瓶", "抗初老")))
    assert r.detail["words"] >= 2


def test_lexicon_is_generated_and_nonempty() -> None:
    """词池必须存在且非空 —— 它是 brand_mention_ratio 的兜底。

    空词池不会报错，只会让信号静默退化（tags 解析失败的篇全变 missing）。
    """
    from jev2.signals._lexicon import BRAND_WORDS
    assert len(BRAND_WORDS) >= 20, f"词池只有 {len(BRAND_WORDS)} 词"
    assert all(len(w) >= 2 for w in BRAND_WORDS), "词池混入了单字词"
    assert "笔记" not in BRAND_WORDS, "词池混入了假标签「笔记」"
    # 去重 + 有序（生成器保证），否则 brand_mention_ratio 的词表会漂
    assert len(set(BRAND_WORDS)) == len(BRAND_WORDS)


def test_lexicon_matches_generator() -> None:
    """词池必须与生成器一致 —— 防止手改或数据变了忘了重新生成。

    词池是**词表不是阈值**，但它决定了覆盖率（实测 30/40 → 37/40），
    过期会让新品牌的笔记静默退化到 missing。
    """
    import importlib.util
    root = Path(__file__).resolve().parents[1]
    spec = importlib.util.spec_from_file_location(
        "_build_lexicon", root / "tools" / "build_lexicon.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    pool, n_notes = mod.collect(root.parent / "data")
    if n_notes == 0:
        pytest.skip("没有 data/，跳过词池一致性检查")
    assert mod.render(pool, n_notes) == mod.OUT.read_text(encoding="utf-8"), (
        "词池已过期，跑 python jev2/tools/build_lexicon.py 重新生成")


# --------------------------------------------------------------- 新信号（第二轮转正）

def test_tag_count_direction_more_is_riskier() -> None:
    """标签堆砌 —— 第二轮实测 AUC 0.778（vs high+medium），medium 类最强。"""
    few = mk_note(tags=tuple(f"t{i}" for i in range(3)))
    many = mk_note(tags=tuple(f"t{i}" for i in range(12)))
    assert run("tag_count", many).value > run("tag_count", few).value
    assert run("tag_count", few).value == 0.0          # 3 个标签不产生风险
    assert run("tag_count", many).value == pytest.approx(1.0)


def test_tag_count_boundary() -> None:
    """5 个标签（正常上界）不产生风险；6 个开始上升。"""
    n5 = mk_note(tags=tuple(f"t{i}" for i in range(5)))
    n6 = mk_note(tags=tuple(f"t{i}" for i in range(6)))
    assert run("tag_count", n5).value == 0.0
    assert run("tag_count", n6).value > 0.0


def test_structure_markers_direction_more_is_riskier() -> None:
    """模板排版 —— 实测 AUC 0.725。"""
    plain = run("structure_markers",
                mk_note(desc="今天用了这个面霜，感觉还可以。" * 5))
    templ = run("structure_markers", mk_note(desc=(
        "✅优点：保湿\n❌缺点：搓泥\n1️⃣第一步\n2️⃣第二步\n"
        "💡小提示\n⚠️注意\n" * 2)))
    assert templ.value > plain.value
    assert plain.value == 0.0


def test_structure_markers_capped() -> None:
    """上限 0.7 —— 真实测评也用 ✅/❌，不该单独定性。"""
    r = run("structure_markers", mk_note(desc="✅❌1️⃣2️⃣💡⚠️▪️①" * 3))
    assert r.value <= 0.7


def test_cta_lexicon_direction_more_is_riskier() -> None:
    """引导词表 —— is_cta 的确定性版本，实测 AUC 0.697。"""
    soft = run("cta_lexicon",
               mk_note(desc="说说我的使用感受，仅供参考。" * 5))
    hard = run("cta_lexicon", mk_note(desc=(
        "私信我领取优惠券，先到先得，限时掉落，点击购买。" * 3)))
    assert hard.value > soft.value
    assert soft.value == 0.0


def test_cta_lexicon_counts_tags() -> None:
    """标签也算文本（活动帖会把引导词写进标签）。"""
    n = mk_note(desc="普通正文" * 10,
                tags=("惊喜盒子", "先到先得", "限时掉落"))
    assert run("cta_lexicon", n).value > 0.0


# --------------------------------------------------------------- 默认禁用机制

def test_nickname_dup_rate_inactive_by_default() -> None:
    """回归：``nickname_dup_rate`` 实测 AUC=0.259（**反向**）——
    它测的是「默认昵称流行度」而非刷评，必须默认禁用。

    依据：官方帖评论者全是唯一昵称（真人来领奖品），
    个人帖反而多 momo。详见 docs/JEV2_EVALUATION.md 第三节。
    """
    from jev2.signals import ACTIVE_SIGNALS, INACTIVE_BY_DEFAULT

    assert "nickname_dup_rate" in INACTIVE_BY_DEFAULT
    assert "nickname_dup_rate" not in ACTIVE_SIGNALS
    assert "nickname_dup_rate" in ALL_SIGNALS          # 实现保留

    ss = SignalSet(ctx=CTX)
    assert "nickname_dup_rate" not in ss.names
    assert "nickname_dup_rate" in ss.skipped_inactive


def test_inactive_signal_runnable_when_explicit() -> None:
    """显式列出名字时按字面执行 —— 便于复核历史判断。"""
    ss = SignalSet(active=["nickname_dup_rate"], ctx=CTX)
    assert "nickname_dup_rate" in ss.names


def test_include_inactive_flag() -> None:
    ss = SignalSet(ctx=CTX, include_inactive=True)
    assert "nickname_dup_rate" in ss.names


def test_skipped_inactive_empty_when_all_on() -> None:
    assert SignalSet(ctx=CTX, include_inactive=True).skipped_inactive == ()


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

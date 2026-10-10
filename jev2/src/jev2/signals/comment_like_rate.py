"""评论点赞非零率。

直觉
----
真实讨论会有「顶上去」行为 —— 有用的评论被别人点赞。
刷评账号之间不会互相点赞（成本高且无意义），所以刷评帖的
评论点赞容易集体为 0。

⚠️ 当前数据的限制（实测 498/498 全为 "0"）
----------------------------------------
匿名态 SSR 拿到的 ``like_count`` **全部是 0** —— 不是「真的都没人赞」，
而是这个字段在第一屏内联数据里没被填充。

所以本信号目前**恒定返回 missing**，title 里写清楚原因。
保留它的价值：等换数据源（登录态/评论分页）后自动生效，
不需要改任何调用方 —— 注册表已经把它挂上了。
"""
from __future__ import annotations

from ..core.types import NoteRecord, SignalResult
from ._lib import safe_div
from .base import SignalContext, signal

NAME = "comment_like_rate"

#: 全 0 时判定为「字段未填充」而不是「真的没人赞」。
#: 判据：0 条非零 AND 评论数 >= 5（5 条以上评论全 0 赞不符合真实分布）。
_MIN_COMMENTS_FOR_JUDGEMENT = 5


@signal(NAME, group="comments")
def compute(record: NoteRecord, *, ctx: SignalContext) -> SignalResult:
    comments = record.comments
    n = len(comments)
    if n < _MIN_COMMENTS_FOR_JUDGEMENT:
        return SignalResult.missing_(NAME, f"评论 {n} 条 < "
                                          f"{_MIN_COMMENTS_FOR_JUDGEMENT}")

    nonzero = 0
    for c in comments:
        s = (c.like_count or "").strip()
        if s and s not in ("0", "-", ""):
            nonzero += 1

    if nonzero == 0:
        # 关键判断：全 0 更可能是采集侧限制，不是内容特征。
        # 拿它当「刷评」证据会误伤所有帖。
        return SignalResult.missing_(
            NAME,
            f"{n} 条评论点赞全为 0 —— 疑似匿名态未填充该字段，"
            "不作为刷评证据",
            n=n,
        )

    rate = safe_div(float(nonzero), float(n))
    # 越高越正常 → 风险取反：非零率 0.2 以下算可疑
    risk = max(0.0, 1.0 - rate / 0.2) if rate < 0.2 else 0.0
    return SignalResult.ok(NAME, min(risk, 1.0), n=n,
                           nonzero=nonzero, rate=round(rate, 3))

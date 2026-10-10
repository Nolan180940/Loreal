"""评论时间跨度 —— 是否集中在短时间内刷出来。

直觉
----
真实帖子的评论是**随时间慢慢积累**的（几天到几个月）。
刷评是一次性灌入，时间戳高度集中。

⚠️ 重要限制：数据里只有**第一屏内联的评论**
------------------------------------------------
匿名态每篇只给 5 条一级评论 + 其下楼中楼行，所以这个「跨度」测的是
**这一小撮评论内部**的分散程度，不是整个评论区的活跃曲线。

后果：一条真实热帖的前 5 条评论也可能集中在几分钟内
（都是刚发出来时涌进来的）。所以这个信号的**假阳性风险高**，
风险上限被压到 0.6，不让它单独把人推向高风险。

实测（40 篇，2026-10-11）
-------------------------
``span_minutes``: min 887 · p10 4012 · 中位 51821 · p90 171893

→ 阈值按**天**定：

- < 1000 分钟（约 17 小时） → 可疑（集中灌入）
- > 20000 分钟（约 14 天） → 正常

（初版拍脑袋写成 2~120 分钟，实测这条数据里**没有一个落到区间内**，
全返回 0 —— 这就是为什么阀值必须用数据定。）

风险方向
--------
**跨度越小越可疑**（按分钟计算，对数压缩）。
"""
from __future__ import annotations

import math

from ..core.types import NoteRecord, SignalResult
from ._lib import clamp01
from .base import SignalContext, signal

NAME = "comment_time_span"

#: 跨度低于 _LO_MIN 分钟算可疑，超过 _HI_MIN 分钟风险 0。
#: 实测分位数：p10=4012 · 中位=51821（见模块 docstring）。
_LO_MIN = 1_000.0
_HI_MIN = 20_000.0

#: 因为只测首屏评论，风险上限压到 0.6（见模块 docstring）。
_MAX_RISK = 0.6


@signal(NAME, group="comments")
def compute(record: NoteRecord, *, ctx: SignalContext) -> SignalResult:
    ts = sorted(c.time_ms for c in record.comments if c.time_ms > 0)
    n = len(ts)
    if n < ctx.min_samples:
        return SignalResult.missing_(NAME, f"有时间的评论 {n} 条 < "
                                          f"{ctx.min_samples}", n=n)

    span_min = (ts[-1] - ts[0]) / 60_000.0
    if span_min >= _HI_MIN:
        risk = 0.0
    else:
        # 对数刻度：1 分钟与 60 分钟的差别比 60 与 120 的差别重要得多
        lo, hi = math.log1p(_LO_MIN), math.log1p(_HI_MIN)
        cur = math.log1p(max(span_min, 0.0))
        risk = clamp01((hi - cur) / (hi - lo)) * _MAX_RISK
    return SignalResult.ok(
        NAME, risk, n=n,
        span_minutes=round(span_min, 1),
        first_ms=ts[0], last_ms=ts[-1],
    )


__all__ = ["compute", "NAME"]

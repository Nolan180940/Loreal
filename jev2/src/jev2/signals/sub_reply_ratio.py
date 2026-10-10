"""楼中楼占比 —— 有没有「来回」。

直觉
----
真实讨论的特征是**来回对话**：有人问、有人答、第三个人插话，形成楼中楼。
打卡式评论区（广告贴）只有平铺的一级评论，各说各话没有互动。

所以「楼中楼 / 总评论数」低 = 讨论稀薄。

实测（40 篇）
-------------
496 行里 318 是楼中楼（64% 行数占比），但那是**行数**；
按帖看差异很大：有的帖几乎全是楼中楼，有的一条都没有。

风险方向
--------
**占比越低越可疑**。但要注意：评论数很少时这个比值不稳
（3 条里 0 条楼中楼很常见），所以样本下限给到 5。
"""
from __future__ import annotations

from ..core.types import NoteRecord, SignalResult
from ._lib import clamp01, safe_div
from .base import SignalContext, signal

NAME = "sub_reply_ratio"

#: 样本下限比其它信号高 —— 比值类信号在小样本上噪声大。
_MIN = 5

_LO = 0.05    # 低于此值风险满格（几乎没有来回）
_HI = 0.35    # 高于此值风险 0


@signal(NAME, group="comments")
def compute(record: NoteRecord, *, ctx: SignalContext) -> SignalResult:
    n = len(record.comments)
    if n < max(ctx.min_samples, _MIN):
        return SignalResult.missing_(
            NAME, f"评论 {n} 条 < {_MIN}，比值不稳", n=n)

    ratio = safe_div(float(len(record.replies)), float(n))
    risk = clamp01((_HI - ratio) / (_HI - _LO)) if ratio < _HI else 0.0
    return SignalResult.ok(NAME, risk, n=n,
                           replies=len(record.replies),
                           ratio=round(ratio, 3))


__all__ = ["compute", "NAME"]

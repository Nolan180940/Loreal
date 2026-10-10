"""点赞 / 评论比 —— 只买赞不买评的痕迹。

直觉
----
真实 UGC 的赞与评论大致同阶（几百赞 ≈ 几十评论）。
比值异常高说明传播靠「刷赞」而非真实互动 —— 评论要真人打字，贵；
赞可以批量买，便宜。

实测（40 篇）
-------------
比值 min 0.3 · p25 1.3 · 中位 3.2 · p75 9.5 · p90 20.7 · max 58.3

→ 半饱和点取 25（≈ p90~p95），这样中位数只得 0.11 风险，
高比值那几篇才能拉到 0.5 以上。

风险方向
--------
**越高越可疑**：``saturate`` 把无上界的比值压到 0..1。
"""
from __future__ import annotations

from ..core.types import NoteRecord, SignalResult
from ._lib import safe_div, saturate
from .base import SignalContext, signal

NAME = "like_comment_ratio"

#: 半饱和点。比值 = 25 时风险 0.5；= 75 时 0.75。
_HALF_SAT = 25.0


@signal(NAME, group="engagement")
def compute(record: NoteRecord, *, ctx: SignalContext) -> SignalResult:
    if record.comment_count <= 0:
        return SignalResult.missing_(NAME, "评论数为 0，比值无意义")

    ratio = safe_div(float(record.liked), float(record.comment_count))
    return SignalResult.ok(
        NAME, saturate(ratio, k=_HALF_SAT), n=1,
        ratio=round(ratio, 2),
        liked=record.liked,
        comment_count=record.comment_count,
    )

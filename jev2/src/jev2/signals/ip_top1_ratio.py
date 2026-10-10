"""评论 IP 属地 top1 占比 —— 地域集中度。

直觉
----
真实 UGC 的读者来自各地，IP 分布分散；刷量工作室的账号池
常集中在少数地区（或同一机房出口），表现为单一地区占比异常高。

实测（40 篇）
-------------
top1 占比 15% ~ 29%（中位约 25%）。所以 0.40 是明显的异常线。

风险方向
--------
**越高越可疑**。阈值给在 0.40 起算，到 0.70 满。
"""
from __future__ import annotations

from collections import Counter

from ..core.types import NoteRecord, SignalResult
from ._lib import clamp01, top1_ratio
from .base import SignalContext, signal

NAME = "ip_top1_ratio"

#: 起算点与满值点。低于起算点给 0（不制造噪声）。
_LO = 0.40
_HI = 0.70


@signal(NAME, group="comments")
def compute(record: NoteRecord, *, ctx: SignalContext) -> SignalResult:
    ips = [c.ip_location.strip() for c in record.comments if c.ip_location.strip()]
    n = len(ips)
    if n < ctx.min_samples:
        return SignalResult.missing_(NAME, f"有 IP 的评论 {n} 条 < "
                                          f"{ctx.min_samples}", n=n)

    counter = Counter(ips)
    ratio = top1_ratio(counter)
    risk = clamp01((ratio - _LO) / (_HI - _LO)) if ratio > _LO else 0.0
    return SignalResult.ok(
        NAME, risk, n=n,
        top1=round(ratio, 3),
        top1_ip=counter.most_common(1)[0][0],
        distinct=len(counter),
    )

"""作者自评占比 —— 运营型 vs 分享型。

直觉
----
品牌方/代运营发的帖子，作者会**主动回复**维持热度（每个问题都答、
每条夸奖都谢）。真实用户发完就走是常态。

实测（40 篇）
-------------
**26/40 篇**作者出现在评论里（1~7 条）。所以这个信号的覆盖率高，
是可以用的。

注意
----
SSR 的 ``is_author`` 恒为 False，所以 loader 用
「评论者昵称 == 作者昵称」兜底推导（见 loader 注释）。

风险方向
--------
**占比越高越可疑**，但要区分两种情况：

- 作者回 1~2 条（答疑）→ 正常
- 作者回很多条（运营维护）→ 可疑

所以起算点给在 0.25，不是「有一条就算」。
"""
from __future__ import annotations

from ..core.types import NoteRecord, SignalResult
from ._lib import clamp01, safe_div
from .base import SignalContext, signal

NAME = "author_reply_ratio"

_LO = 0.25    # 低于此值风险 0（答疑型）
_HI = 0.50    # 高于此值风险满格（高频维护）。实测 max=0.5，正好封顶


@signal(NAME, group="comments")
def compute(record: NoteRecord, *, ctx: SignalContext) -> SignalResult:
    n = len(record.comments)
    if n < ctx.min_samples:
        return SignalResult.missing_(NAME, f"评论 {n} 条 < "
                                          f"{ctx.min_samples}", n=n)
    if not record.author:
        return SignalResult.missing_(NAME, "笔记没有作者昵称，无法判定自评")

    k = len(record.author_comments)
    ratio = safe_div(float(k), float(n))
    risk = clamp01((ratio - _LO) / (_HI - _LO)) if ratio > _LO else 0.0
    return SignalResult.ok(NAME, risk, n=n,
                           author_comments=k, ratio=round(ratio, 3))


__all__ = ["compute", "NAME"]

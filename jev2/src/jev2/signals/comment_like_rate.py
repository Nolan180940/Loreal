"""评论点赞非零率。

直觉
----
真实讨论会有「顶上去」行为 —— 有用的评论被别人点赞。
刷评账号之间不会互相点赞（成本高且无意义），所以刷评帖的
评论点赞容易集体为 0。

⚠️ 踩过的坑：字段取错了，不是平台不给（2026-10-11 修正）
------------------------------------------------------
本信号曾长期「恒定返回 missing」，原因写的是「匿名态未填充该字段」。
**那个结论是错的。**

SSR 的评论对象里有**两个**点赞字段：

======================  ==========================================
``likeCount``           内部计数器，实测 **543/543 恒为 0**
``likeViewCount``       **展示给用户看的点赞数**，有真值
                        （实测 310 / 56 / 24 / 29 / 32 …）
======================  ==========================================

采集层早先只取了 ``likeCount``，于是下游看到「全 0」，
误判成「平台不填充」。修法是把 ``likeViewCount`` 也采下来
（``CommentRow.like_view_count``），本信号优先读它。

旧数据（2026-10-11 之前采的）没有 ``like_view_count``，
仍然返回 missing —— 但原因变成「这篇没采到点赞」，
而不是「平台不给」。**重抓一次就自动生效**，不需要改任何调用方。

阈值
----
非零率 < 0.2 起算风险，0 满格。0.2 的依据：真实讨论帖里
「被赞过的评论」占比通常在 0.3~0.6（长评/神评容易被顶），
全 0 或极低才是异常。
"""
from __future__ import annotations

from ..core.types import NoteRecord, SignalResult
from ._lib import safe_div
from .base import SignalContext, signal

NAME = "comment_like_rate"

#: 样本下限：评论太少时「非零率」的粒度太粗（3 条里 0 条赞很常见）。
_MIN_COMMENTS_FOR_JUDGEMENT = 5

#: 非零率低于这个值开始计风险（真实讨论帖通常 0.3~0.6）。
_RATE_LO = 0.2


@signal(NAME, group="comments")
def compute(record: NoteRecord, *, ctx: SignalContext) -> SignalResult:
    comments = record.comments
    n = len(comments)
    if n < _MIN_COMMENTS_FOR_JUDGEMENT:
        return SignalResult.missing_(NAME, f"评论 {n} 条 < "
                                          f"{_MIN_COMMENTS_FOR_JUDGEMENT}")

    # 先问「采到了没有」—— 没采到和「没人赞」是两回事，
    # 混同会误伤所有帖（这就是当初恒 missing 的教训）。
    if not record.has_view_likes:
        return SignalResult.missing_(
            NAME,
            f"{n} 条评论都没有 like_view_count —— 本篇未采集展示点赞数"
            "（2026-10-11 前的旧数据格式）。重抓一次即可生效，"
            "不作为刷评证据",
            n=n,
        )

    have = [c for c in comments if c.has_view_like]
    nonzero = sum(1 for c in have
                  if (c.like_view_count or "").strip() not in ("0", "-", ""))
    rate = safe_div(float(nonzero), float(len(have)))

    # 越高越正常 → 风险取反：非零率低于 _RATE_LO 时线性上升
    risk = max(0.0, 1.0 - rate / _RATE_LO) if rate < _RATE_LO else 0.0
    return SignalResult.ok(NAME, min(risk, 1.0), n=n,
                           nonzero=nonzero, rate=round(rate, 3),
                           with_data=len(have))

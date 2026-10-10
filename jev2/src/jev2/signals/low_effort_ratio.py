"""低信息量评论占比 —— 打卡区的比例。

直觉
----
真实讨论区会有成段的使用体验，也会有一些「+1」「好看」这类短回复 ——
后者正常，但**占比过高**就说明这个评论区是打卡区而不是讨论区。

与 ``comment_len_mean`` 的区别
------------------------------
均长会被一两条长评拉高，掩盖「10 条短评 + 1 条长评」的结构。
这个信号直接数**低信息量**的条数占比，对分布形状更敏感。

「低信息量」的定义见 ``_lib.is_low_effort``：去掉 ``[表情]`` 与标点后
没有实义字符，或长度 ≤ 8。

风险方向
--------
**占比越高越可疑**。
"""
from __future__ import annotations

from ..core.types import NoteRecord, SignalResult
from ._lib import clamp01, is_low_effort, safe_div
from .base import SignalContext, signal

NAME = "low_effort_ratio"

_LO = 0.30
_HI = 0.75


@signal(NAME, group="comments")
def compute(record: NoteRecord, *, ctx: SignalContext) -> SignalResult:
    n = len(record.comments)
    if n < ctx.min_samples:
        return SignalResult.missing_(
            NAME, f"评论 {n} 条 < {ctx.min_samples}", n=n)

    low = sum(1 for c in record.comments if is_low_effort(c.content))
    ratio = safe_div(float(low), float(n))
    risk = clamp01((ratio - _LO) / (_HI - _LO)) if ratio > _LO else 0.0
    return SignalResult.ok(NAME, risk, n=n,
                           low_effort=low, ratio=round(ratio, 3))


__all__ = ["compute", "NAME"]

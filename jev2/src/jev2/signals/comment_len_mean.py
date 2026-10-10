"""评论平均长度 —— 打卡区 vs 讨论区的分辨。

直觉
----
两类可疑评论区都会拉低均长：

- **广告贴**：评论区是打卡区，「求链接」「多少钱」
- **刷评**：模板短句

而真实测评帖的评论区会有成段的使用体验。

与 ``comment_len_sd`` 的区别
----------------------------
这是**水平**指标，那是**离散度**指标。两者独立：
短而齐（刷评）、短而乱（真实但冷淡）、长而齐（模板长文，最可疑）。

风险方向
--------
**越短越可疑**。

实测（40 篇）
-------------
均长 min 5.8 · p25 12.3 · 中位 18.1 · p90 34.1 · max 42.4。

⚠️ 初版把 _HI 定在 40，而中位数才 18.1 —— 导致一半以上的笔记
被算出 0.5 以上的风险值，噪声很大。现按 p25/p75 重定。
"""
from __future__ import annotations

from ..core.types import NoteRecord, SignalResult
from ._lib import clamp01, lens_of
from .base import SignalContext, signal

NAME = "comment_len_mean"

_LO = 9.0     # 低于此值风险满格（≈ 实测 p10 = 9.1）
_HI = 24.0    # 高于此值风险 0（≈ 实测 p75 = 24.6）


@signal(NAME, group="comments")
def compute(record: NoteRecord, *, ctx: SignalContext) -> SignalResult:
    ls = lens_of(record.comments)
    n = len(ls)
    if n < ctx.min_samples:
        return SignalResult.missing_(
            NAME, f"评论 {n} 条 < {ctx.min_samples}", n=n)

    m = sum(ls) / n
    risk = clamp01((_HI - m) / (_HI - _LO)) if m < _HI else 0.0
    return SignalResult.ok(NAME, risk, n=n, mean=round(m, 1))


__all__ = ["compute", "NAME"]

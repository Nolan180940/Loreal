"""评论长度 IQR（四分位距）—— 抗离群的离散度。

为什么在 SD 之外还要 IQR
------------------------
标准差对离群极敏感：一条 500 字的详细长评就能把 SD 拉高，
让「本来整齐」的刷评帖显得正常。

IQR 只看中间 50% 的数据，一个极端值动不了它。

- SD 大、IQR 小 → 有个别长评，但主体整齐（**可能是刷评 + 少数真人**）
- SD 大、IQR 大 → 真的长短不一（正常讨论）

所以两者一起看比单看 SD 更有分辨力。

风险方向
--------
**IQR 越小越可疑**。实测正常帖 IQR 约 15~50。
"""
from __future__ import annotations

from ..core.types import NoteRecord, SignalResult
from ._lib import clamp01, iqr, lens_of
from .base import SignalContext, signal

NAME = "comment_len_iqr"

_LO = 4.0     # 低于此值风险满格
_HI = 20.0    # 高于此值风险 0


@signal(NAME, group="comments")
def compute(record: NoteRecord, *, ctx: SignalContext) -> SignalResult:
    ls = lens_of(record.comments)
    # IQR 需要至少 4 个点才有意义（Q1/Q3 各要两个样本）
    if len(ls) < max(ctx.min_samples, 4):
        return SignalResult.missing_(
            NAME, f"评论 {len(ls)} 条 < 4，IQR 无意义", n=len(ls))

    value = iqr(ls)
    risk = clamp01((_HI - value) / (_HI - _LO)) if value < _HI else 0.0
    return SignalResult.ok(NAME, risk, n=len(ls), iqr=round(value, 2))


__all__ = ["compute", "NAME"]

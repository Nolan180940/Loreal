"""评论 IP 熵（归一化）—— 地域多样性的另一面。

与 ``ip_top1_ratio`` 的关系
--------------------------
两者都测「集中度」，但性质不同：

- ``top1_ratio`` 只看**最大那一类**。若一个帖有 5 个地区、其中两个各占 30%，
  top1 只有 0.30 看着正常，但分布其实很不均匀。
- ``entropy`` 看**整体分布形状**，能抓住「两三个地区主导」这种情况。

保留两个而不是二选一，是因为它们对不同类型的集中敏感。
融合层可以给不同权重（现在都没进权重，见 config）。

风险方向
--------
**熵越低越可疑**（0 = 全集中一地，1 = 完全均匀）。
所以风险 = 1 - 归一化熵。

实测（40 篇）
-------------
归一化熵集中在 **0.70 ~ 1.00**（p10 = 0.9，中位 0.9，最小 0.7）。

⚠️ 初版把区间定成 0.60~0.85，而实际数据几乎全在 0.85 以上 ——
结果信号恒为 0（废的）。现区间按实测分位数重定。
"""
from __future__ import annotations

from collections import Counter

from ..core.types import NoteRecord, SignalResult
from ._lib import clamp01, normalized_entropy
from .base import SignalContext, signal

NAME = "ip_entropy"

#: 低于 _LO 算可疑起点，_HI 以下满风险。
#: 实测：min 0.70 · p10 0.90 · 中位 0.90。
_LO = 0.78    # 低于此值风险满格
_HI = 0.92    # 高于此值风险 0
#: 归一化熵的取值范围很窄（实测 0.70~1.00），所以这段区间的
#: 线性映射对微小差异很敏感 —— 这是刻意的：熵本来就都接近 1，
#: 真正有区分度的是「差一点点」的那部分。


@signal(NAME, group="comments")
def compute(record: NoteRecord, *, ctx: SignalContext) -> SignalResult:
    ips = [c.ip_location.strip() for c in record.comments if c.ip_location.strip()]
    n = len(ips)
    if n < max(ctx.min_samples, 3):
        return SignalResult.missing_(NAME, f"有 IP 的评论 {n} 条不足", n=n)

    counter = Counter(ips)
    if len(counter) < 2:
        # 全部同一个 IP —— 极度异常，直接顶格
        return SignalResult.ok(NAME, 1.0, n=n, distinct=1,
                               entropy=0.0, note="全部同一地区")

    h = normalized_entropy(counter)
    # ⚠️ 方向：熵**越低越可疑**。所以是 (high-h)/(high-low)，
    #    且判断条件用 _HI 不是 _LO ——（初版写成 `if h < _LO`，
    #    于是 h 在 [_LO, _HI] 区间内直接返回 0，信号恒空）。
    risk = clamp01((_HI - h) / (_HI - _LO)) if h < _HI else 0.0
    return SignalResult.ok(NAME, risk, n=n,
                           entropy=round(h, 4), distinct=len(counter))


__all__ = ["compute", "NAME"]

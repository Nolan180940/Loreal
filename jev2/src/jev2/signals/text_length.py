"""正文长度 —— 过短是广告卡片，过长是软文。

直觉
----
**两个极端**都可疑，中间才正常：

- **过短**（< 40 字）：纯话题标签或无实质内容，典型的活动打卡贴
- **过长**（> 900 字）：软文特征，真实用户分享很少写这么长

所以用 :func:`~._lib.band_risk`：区间内风险 0，越往外越高。

实测（40 篇）
-------------
``desc`` 长度 20 ~ 700 字，中位约 150 —— 全部落在正常区间内，
所以这个信号在**当前数据上几乎不触发**。这是预期行为：
它是为「活动贴/长软文」准备的，而这批数据里那两类占比不高。
"""
from __future__ import annotations

from ..core.types import NoteRecord, SignalResult
from ._lib import band_risk
from .base import SignalContext, signal

NAME = "text_length"

#: 正常区间（含）。区间外按 _PAD 线性上升，超过 _PAD 满风险。
_LO = 40.0
_HI = 900.0
_PAD = 120.0


@signal(NAME, group="text")
def compute(record: NoteRecord, *, ctx: SignalContext) -> SignalResult:
    n = len(record.desc)
    if n < 20 and len(record.title) < 10:
        return SignalResult.missing_(NAME, "标题与正文都太短，无法判定")

    # 用 desc 长度（不含标签），标签不计入「正文长度」
    risk = band_risk(float(n), lo=_LO, hi=_HI, pad=_PAD)
    return SignalResult.ok(NAME, risk, n=n,
                           desc_len=n, title_len=len(record.title))


__all__ = ["compute", "NAME"]

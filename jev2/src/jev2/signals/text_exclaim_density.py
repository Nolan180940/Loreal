"""正文感叹号密度 —— 夸大文案的排版特征。

直觉
----
夸大文案爱用大量感叹号与强调标点（"！！！！！""封神了！！！"）。
这是廉价的情绪强化，真实分享很少这样排版。

⚠️ 弱信号：广告文案可以写得很克制，真实用户也可能很激动。
所以风险上限压到 0.5，只作为辅助证据。

风险方向
--------
**密度越高越可疑**。按「每 100 字的感叹号数」算，避免长文被误伤。
"""
from __future__ import annotations

import re

from ..core.types import NoteRecord, SignalResult
from ._lib import clamp01
from .base import SignalContext, signal

NAME = "text_exclaim_density"

#: 中英文感叹号与连续重复的强调
_EXCLAIM = re.compile(r"[!！]")

_LO = 0.6     # 每 100 字 0.6 个以下 → 0
_HI = 3.0     # 每 100 字 3 个以上 → 满
_MAX_RISK = 0.5


@signal(NAME, group="text")
def compute(record: NoteRecord, *, ctx: SignalContext) -> SignalResult:
    text = f"{record.title}\n{record.desc}".strip()
    n = len(text)
    if n < 20:
        return SignalResult.missing_(NAME, f"正文仅 {n} 字，密度不可靠", n=n)

    k = len(_EXCLAIM.findall(text))
    density = k / n * 100.0
    risk = clamp01((density - _LO) / (_HI - _LO)) * _MAX_RISK if density > _LO else 0.0
    return SignalResult.ok(
        NAME, risk, n=n,
        exclaims=k, density_per_100=round(density, 2),
    )


__all__ = ["compute", "NAME"]

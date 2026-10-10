"""评论者昵称重复率 —— 账号池痕迹。

直觉
----
刷量工作室的账号池有限，同一批账号会在多个帖子里出现。
但**单篇帖子内部**昵称重复是另一回事：正常评论区偶尔会有同名用户
（小红书的 momo 群体就是典型 —— 大量用户用默认昵称 "momo"）。

所以这个信号**天然有假阳性**：
实测数据里 "momo" 系昵称大量存在且是真实用户。

风险方向
--------
重复率越高越可疑，但上限压到 0.5（因为 momo 现象）。

实测（40 篇）
-------------
``rate``: min 0 · p25 0.2 · 中位 0.3 · p75 0.4 · max 0.6

⚠️ 初版把 _LO 定在 0.10，而中位数就是 0.3 —— 一半以上的帖都被
算成「有刷评痕迹」。原因是**小红书默认昵称泛滥**（除 momo 外
还有大量符号昵称、颜文字昵称）。现把起算点提到 p50~p75 之间。
"""
from __future__ import annotations

from collections import Counter

from ..core.types import NoteRecord, SignalResult
from ._lib import clamp01, safe_div
from .base import SignalContext, signal

NAME = "nickname_dup_rate"

_LO = 0.35
_HI = 0.55
_MAX_RISK = 0.5      # 默认昵称泛滥 → 不让它单独定性

#: 这些昵称是平台默认名，不参与「重复」判定。
#: 小红书的 momo 是默认昵称，大量真实用户在用。
_DEFAULT_NICKS = {"momo", "MOMO", "momo（护肤版）", "已注销", "用户已注销"}


@signal(NAME, group="comments")
def compute(record: NoteRecord, *, ctx: SignalContext) -> SignalResult:
    names = [c.nickname.strip() for c in record.comments
             if c.nickname.strip() and c.nickname.strip() not in _DEFAULT_NICKS]
    n = len(names)
    if n < max(ctx.min_samples, 5):
        return SignalResult.missing_(
            NAME, f"有效昵称 {n} 条 < 5，重复率不稳", n=n)

    counter = Counter(names)
    dup = sum(v - 1 for v in counter.values() if v > 1)
    rate = safe_div(float(dup), float(n))
    risk = clamp01((rate - _LO) / (_HI - _LO)) * _MAX_RISK if rate > _LO else 0.0
    return SignalResult.ok(
        NAME, risk, n=n,
        duplicate_rows=dup,
        rate=round(rate, 3),
        repeated={k: v for k, v in counter.items() if v > 1} or {},
    )


__all__ = ["compute", "NAME"]

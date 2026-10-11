"""评论者昵称重复率 —— **已实测反向，禁止进权重**。

⚠️ 本信号在当前数据上方向是相反的
----------------------------------
第一轮评估实测 AUC = **0.259**（vs 是否高风险）—— 也就是说
「昵称重复率高」反而**更可能是真实帖**。

复盘原因（看官方活动帖就懂）：

- **官方活动帖**（`6ab6a30e` 等）：评论者全是唯一昵称 ——
  因为都是真实用户来领奖品的，每人一个号
- **个人真实帖**：反而一堆 momo（小红书默认昵称）与符号昵称用户

所以这个信号实际测的是「**默认昵称流行度**」，不是「刷评」。

处置
----
1. **保留实现** —— 换数据源（登录态 / 评论分页 / 更多帖子）后
   可能有用，删了就没法复核
2. **默认禁用** —— 见 ``config.toml`` 的 ``signals.active``
   与 ``signals.INACTIVE_BY_DEFAULT``
3. docstring 留痕 —— 免得后来者（或未来的我）又想「加个昵称重复率吧」

原设计意图（保留供参考）
-----------------------
刷量工作室的账号池有限，同一批账号会在多个帖子里出现。
但**单篇帖子内部**昵称重复是另一回事 —— 小红书有大量用户用
默认昵称与符号昵称，天然造成假阳性。

实测（40 篇）
-------------
``rate``: min 0 · p25 0.2 · 中位 0.3 · p75 0.4 · max 0.6
（阈值曾按这个分布校准过，但方向验证推翻了它）
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
        # 明确标注：本信号实测反向，不要据此判风险
        caveat="实测 AUC=0.259（反向），禁止进权重",
    )


__all__ = ["compute", "NAME"]

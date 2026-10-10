"""评论长度标准差 —— 模板化/刷评最直接的痕迹。

直觉
----
要伪造「参差不齐」比伪造「整齐」难得多：
刷评模板产出的评论长度高度一致（"求链接""多少钱""+1"）。
真实讨论天然有长有短（"我用了三个月…" vs "好用"）。

**标准差比均值可靠**：均值短不代表可疑（活动贴评论区天然短），
但标准差小意味着「整齐得不像人写的」。

实测依据
--------
legacy-jev 在 42 篇上测过：对人工判读的 high vs 其他，
AUC = 0.853（``tools/validate_signals.py``），是所有候选信号里最强的。

风险方向
--------
**SD 越小越可疑**。阈值 SD < 7.0 判「整齐得不自然」。
"""
from __future__ import annotations

from ..core.types import NoteRecord, SignalResult
from ._lib import lens_of, sd
from .base import SignalContext, signal

NAME = "comment_len_sd"

#: 阈值来自 legacy-jev 的实测校准（人工 high 的 5 篇里 4 篇 SD ≤ 6.1，
#: 人工 low 的 14 篇里 13 篇 SD ≥ 8.6，取 7 落在两组之间）。
_SUSPICIOUS = 7.0
#: 到这个值风险满格。低于它线性上升。
_FULL = 2.0


@signal(NAME, group="comments")
def compute(record: NoteRecord, *, ctx: SignalContext) -> SignalResult:
    ls = lens_of(record.comments)
    n = len(ls)
    if n < ctx.min_samples:
        return SignalResult.missing_(
            NAME, f"评论 {n} 条 < {ctx.min_samples}，SD 不可靠", n=n)

    value = sd(ls)
    # SD 越小越可疑：< _FULL 满格，>= _SUSPICIOUS 为 0
    if value >= _SUSPICIOUS:
        risk = 0.0
    else:
        risk = min(1.0, (_SUSPICIOUS - value) / (_SUSPICIOUS - _FULL))
    return SignalResult.ok(
        NAME, risk, n=n,
        sd=round(value, 2),
        mean=round(sum(ls) / n, 1),
        min_len=int(min(ls)),
        max_len=int(max(ls)),
    )

"""引导词词表 —— ``is_cta`` 的确定性版本。

为什么需要它
------------
语义层的 ``is_cta``（AUC 0.784）是**概率判断**，会漏掉措辞含蓄的引导。
词表是**确定性**的：出现「私信/橱窗/下单/优惠券/点击领取」这类词，
就是引导，没有"可能"。

两者互补：
- 规则漏判时（含蓄措辞）→ 语义层接住
- 语义层给低分时（词表命中）→ 这里发现

所以它作为**独立信号**存在，而不是塞进语义层。

实测（40 篇，2026-10-11）
-------------------------
AUC = **0.697**（vs high）—— 可用。官方活动帖（`6ab6a30e`/`6abca4c9`）
词表命中密集（「先到先得」「掉落」「领取」），是它们最明显的文本特征。

风险方向
--------
**密度越高越可疑**。按每百字算，避免长文被误伤。
"""
from __future__ import annotations

from ..core.types import NoteRecord, SignalResult
from ._lib import clamp01
from .base import SignalContext, signal

NAME = "cta_lexicon"

#: 引导词。按「强/弱」分两档 —— 强的单次命中就有意义，
#: 弱的（如「活动」）需要累积。
_STRONG: tuple[str, ...] = (
    "私信", "私我", "评论区扣", "扣1", "扣一", "橱窗", "下单",
    "优惠券", "领券", "领取", "先到先得", "限时", "掉落", "抽奖",
    "返现", "团购", "拼单", "链接在", "点我", "点击购买",
)
_WEAK: tuple[str, ...] = (
    "链接", "店铺", "优惠", "折扣", "搜索", "点击", "参与", "活动",
    "码", "券",
)

#: 加权后的密度阈值（每百字）。
_LO = 0.8
_HI = 4.0
#: 上限：真实用户分享折扣信息也会命中（如「哪个平台买的」），
#: 所以不让它单独定性。
_MAX_RISK = 0.85


@signal(NAME, group="text")
def compute(record: NoteRecord, *, ctx: SignalContext) -> SignalResult:
    text = f"{record.title}\n{record.desc}\n{' '.join(record.tags)}"
    L = len(text)
    if L < 20:
        return SignalResult.missing_(NAME, "文本太短，密度不可靠")

    strong = [w for w in _STRONG if w in text]
    weak = [w for w in _WEAK if w in text]
    # 强词算 2 分、弱词算 1 分，避免「链接」这种常见词拉高判定
    score = len(strong) * 2 + len(weak)
    density = score / L * 100.0

    risk = clamp01((density - _LO) / (_HI - _LO)) * _MAX_RISK \
        if density > _LO else 0.0
    return SignalResult.ok(
        NAME, risk, n=score,
        density_per_100=round(density, 2),
        strong=strong[:5],
        weak=weak[:5],
    )

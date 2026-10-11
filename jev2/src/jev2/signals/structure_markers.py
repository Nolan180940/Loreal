"""结构化排版标记 —— 软文模板的排版指纹。

直觉
----
真实用户写分享是**流水账**（想到哪写到哪），而软文/营销文案
会按模板排版，留下大量装饰性符号：

- ``✅`` / ``❌`` 优缺点清单
- ``1️⃣ 2️⃣ 3️⃣`` 编号步骤
- ``💡`` / ``⚠️`` 提示块
- ``▪️`` 列表符号

这些符号本身没有语义，但「有没有用模板排版」是强信号 ——
它意味着作者（或代笔）在**按营销 SOP 生产内容**。

实测（40 篇，2026-10-11）
-------------------------
AUC = **0.725**（vs high）—— 可用。

局限
----
真实测评也会用 ✅/❌ 列优缺点（实测有几篇 such），所以
**风险上限压到 0.7**，不单独定性。它的价值在于与 `tag_count`
组合成逻辑门（堆标签 + 模板排版 = 典型软文骨架）。

风险方向
--------
**标记越多越可疑**。
"""
from __future__ import annotations

from ..core.types import NoteRecord, SignalResult
from ._lib import clamp01
from .base import SignalContext, signal

NAME = "structure_markers"

#: 模板排版符号。只收「几乎只出现在营销文案里」的那批 ——
#: 常见中英文标点不算（真实用户也用）。
_MARKERS: tuple[str, ...] = (
    "✅", "❌", "1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣",
    "💡", "⚠️", "▪️", "①", "②", "③", "④", "⑤",
    "👉", "🔬", "📌", "🎯", "🌟",
)

#: 命中 2 个起算（1 个可能是巧合），到 6 个满格。
_LO = 2
_HI = 6
#: 上限：真实测评也用 ✅/❌，不单独定性。
_MAX_RISK = 0.7


@signal(NAME, group="text")
def compute(record: NoteRecord, *, ctx: SignalContext) -> SignalResult:
    text = f"{record.title}\n{record.desc}"
    if len(text) < 20:
        return SignalResult.missing_(NAME, "正文太短，排版特征不可靠")

    hits = [m for m in _MARKERS if m in text]
    k = len(hits)
    risk = clamp01((k - _LO) / (_HI - _LO)) * _MAX_RISK if k >= _LO else 0.0
    return SignalResult.ok(
        NAME, risk, n=k,
        marker_count=k,
        markers=hits[:6],
    )

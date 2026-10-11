"""话题标签堆砌 —— SEO 农场 / 活动贴的排版特征。

直觉
----
真实分享会打几个贴切的标签（3~5 个）。而两类可疑内容会**堆标签**：

- **SEO 农场贴**：正文几乎为空，靠一堆标签吃搜索流量
  （实测 `6aabad77`：正文只有标签、0 条评论、10 个标签）
- **campaign 参与贴**：平台活动要求带指定话题，会打一长串

所以「标签数」本身就是结构信号，不需要读内容。

实测（40 篇，2026-10-11）
-------------------------
| 分组 | 标签数中位 |
|---|---|
| gold = high + medium | 明显偏高 |
| gold = low | 3~5 |

AUC：**0.778**（vs high+medium）—— 是 medium 类（软广灰区）最强的
单个统计信号，比评论长度家族还强。

为什么它擅长 medium
--------------------
medium 那批（疑似软广）文本写得很"干净"，光看文字判不出来；
但它们的**排版习惯**藏不住 —— 标签数量是最难伪装的元数据之一。

风险方向
--------
**标签越多越可疑**。起算点给在 5（正常帖的中位上界），
到 12 满格。
"""
from __future__ import annotations

from ..core.types import NoteRecord, SignalResult
from ._lib import clamp01
from .base import SignalContext, signal

NAME = "tag_count"

#: 正常帖的标签数中位上界。低于此值不产生风险。
_LO = 5.0
#: 到这个数量风险满格。
_HI = 12.0


@signal(NAME, group="text")
def compute(record: NoteRecord, *, ctx: SignalContext) -> SignalResult:
    n = len(record.tags)
    risk = clamp01((n - _LO) / (_HI - _LO)) if n > _LO else 0.0
    return SignalResult.ok(
        NAME, risk, n=n,
        tag_count=n,
        tags=record.tags[:6],
        desc_len=len(record.desc),
    )

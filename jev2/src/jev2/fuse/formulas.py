"""融合层的**公式库** —— 只算数，不做决策。

分工
----
- ``formulas.py``（本文件）  纯函数：输入数字 → 输出数字
- ``rules.py``              声明式规则：引用本文件的函数
- ``engine.py``             求值引擎：跑规则、出裁决

**决策逻辑一行都不在这里。** 这里只有「数学怎么算」。

为什么要拆出来
--------------
1. 公式可以被单独测试 —— 不用构造 NoteRecord，给数字就行
2. 换决策逻辑不用碰引擎，改 ``rules.py`` 的规则数据即可
3. 一个公式能被多条规则复用（``indicator_ge`` 现在只被 veto 用，
   将来可能被某条 contribute 规则用）

两类函数
--------
**指标函数（indicator functions）**：把原始值映射成 0..1 的风险值。
  ``indicator_ge`` / ``linear`` / ``logistic`` / ``band`` / ``identity``

**逻辑门（logic gates）**：把多个 0..1 值合成一个。
  ``AND`` / ``OR`` / ``NOT`` / ``at_least`` / ``weighted``

逻辑门的阈值统一用 **0.5** 作「真/假」的分界 —— 这不是随便定的：
所有输入都是 0..1 的风险值，0.5 是唯一无偏的分界点。
要改判据就传 ``threshold``，别改默认值（改了会让所有调用方一起变）。
"""

from __future__ import annotations

import math
from typing import Any

__all__ = [
    "clamp01", "safe_div",
    # 指标函数
    "identity", "indicator_ge", "indicator_le", "indicator_band",
    "linear", "linear_desc", "logistic", "band",
    # 逻辑门
    "AND", "OR", "NOT", "at_least", "at_most", "mean_of",
    # 聚合
    "weighted", "veto",
]


def clamp01(x: float) -> float:
    return 0.0 if x < 0 else (1.0 if x > 1 else float(x))


def safe_div(a: float, b: float, *, default: float = 0.0) -> float:
    return a / b if b else default


# --------------------------------------------------------------- 指标函数

def identity(x: float, **_: Any) -> float:
    """原样返回（夹到 0..1）。用于「值本身已经是风险分」的维度。"""
    return clamp01(x)


def indicator_ge(x: float, *, t: float = 0.5) -> float:
    """阶跃：``x >= t`` → 1，否则 0。

    ⚠️ 阶跃不可导、对阈值附近极敏感。**只用于一票否决**这种
    「命中就是命中」的场景，不要用来做加权贡献。
    """
    return 1.0 if x >= t else 0.0


def indicator_le(x: float, *, t: float = 0.5) -> float:
    """阶跃：``x <= t`` → 1，否则 0。"""
    return 1.0 if x <= t else 0.0


def indicator_band(x: float, *, lo: float = 0.0, hi: float = 1.0) -> float:
    """阶跃：落在 ``[lo, hi]`` → 1，否则 0。"""
    return 1.0 if lo <= x <= hi else 0.0


def linear(x: float, *, lo: float = 0.0, hi: float = 1.0) -> float:
    """线性映射 0..1：``x <= lo`` → 0，``x >= hi`` → 1。

    ``lo > hi`` 时自动反向（``x`` 越小风险越高）——
    这样同一个函数既能表「越高越可疑」也能表「越低越可疑」，
    不用记两个名字。
    """
    if lo == hi:
        return 1.0 if x >= hi else 0.0
    t = (x - lo) / (hi - lo)
    return clamp01(t)


#: ``linear`` 的显式反向别名（可读性用）。
linear_desc = lambda x, *, lo=0.0, hi=1.0: linear(x, lo=hi, hi=lo)  # noqa: E731


def logistic(x: float, *, k: float = 10.0, x0: float = 0.5) -> float:
    """S 型映射。比 linear 平滑，阈值附近不会突变。

    ``k`` 越大越陡；``x0`` 是 0.5 输出点。
    """
    try:
        return clamp01(1.0 / (1.0 + math.exp(-k * (x - x0))))
    except OverflowError:
        return 0.0 if x < x0 else 1.0


def band(x: float, *, lo: float = 0.0, hi: float = 1.0,
         pad: float = 0.1) -> float:
    """**区间内正常（0），区间外越远越可疑**。

    用于「中等范围才正常」的量（正文长度：太短是广告卡片、太长是软文）。
    与 ``signals._lib.band_risk`` 同构，此处是融合层的镜像，
    便于规则里直接引用而不依赖信号层的内部实现。

    ⚠️ 方向容易写反（信号层就写反过一次）。语义锁定：
    **区间内 → 0**，区间外 → 随距离上升。
    """
    if lo <= x <= hi:
        return 0.0
    if pad <= 0:
        return 1.0
    d = (lo - x) if x < lo else (x - hi)
    return clamp01(d / pad)


# --------------------------------------------------------------- 逻辑门

def _truthy(v: float, threshold: float) -> bool:
    return v >= threshold


def AND(*vals: float, threshold: float = 0.5) -> float:
    """全真才为 1。空输入返回 0（无证据 ≠ 全部成立）。"""
    if not vals:
        return 0.0
    return 1.0 if all(_truthy(v, threshold) for v in vals) else 0.0


def OR(*vals: float, threshold: float = 0.5) -> float:
    """任一为真则为 1。空输入返回 0。"""
    if not vals:
        return 0.0
    return 1.0 if any(_truthy(v, threshold) for v in vals) else 0.0


def NOT(v: float, *, threshold: float = 0.5) -> float:
    """取反。"""
    return 0.0 if _truthy(v, threshold) else 1.0


def at_least(k: int, *vals: float, threshold: float = 0.5) -> float:
    """至少 k 个为真则为 1。

    比 OR/AND 灵活 —— 「两个疑点里中一个」这类判据不用手写计数。
    """
    if k <= 0:
        return 1.0
    if not vals:
        return 0.0
    return 1.0 if sum(1 for v in vals if _truthy(v, threshold)) >= k else 0.0


def at_most(k: int, *vals: float, threshold: float = 0.5) -> float:
    """至多 k 个为真则为 1。"""
    if not vals:
        return 1.0
    return 1.0 if sum(1 for v in vals if _truthy(v, threshold)) <= k else 0.0


def mean_of(*vals: float) -> float:
    """算术平均。空输入返回 0（无证据不产生风险）。"""
    real = [clamp01(v) for v in vals]
    return sum(real) / len(real) if real else 0.0


# --------------------------------------------------------------- 聚合

def weighted(pairs: dict[str, float], weights: dict[str, float], *,
             normalize: bool = True) -> float:
    """加权平均。

    Parameters
    ----------
    pairs
        ``{维度名: 值}``。**只对出现在 weights 里的键计权** ——
        没配权重的维度不参与（这正是「L2 信号先只展示不进权重」的实现：
        config.weights 里不加键，它们就不影响总分）。
    weights
        ``{维度名: 权重}``。
    normalize
        True 时按权重之和归一（这样加一个维度不会凭空抬高总分）。

    ⚠️ 缺失的维度不参与计算，且**不从分母里扣** ——
    因为权重表达的是「这个维度在完整评估中的重要性」，
    不是「在所有可用维度中的占比」。
    """
    acc = 0.0
    wsum = 0.0
    for name, w in weights.items():
        if name not in pairs:
            continue
        acc += clamp01(pairs[name]) * w
        wsum += w
    if wsum <= 0:
        return 0.0
    return clamp01(acc / wsum) if normalize else clamp01(acc)


def veto(score: float, *, flag: float,
         threshold: float = 0.85) -> float:
    """一票否决：命中则总分拉满，否则原样返回。

    legacy-jev 实测依据：加权平均会把纯广告稀释
    （官方活动贴 ``is_ad=0.96`` 被其他维度拉到加权 0.642 → 误判中风险）。
    加 ``is_ad >= 0.85`` 直接判高后，高风险召回 **40% → 100%**。
    """
    return 1.0 if flag >= threshold else clamp01(score)

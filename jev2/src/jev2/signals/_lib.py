"""信号层的共享数学工具。

**只放纯函数**：输入数字，输出数字，不碰 NoteRecord。
这样它们能被单独测试，也保证信号文件只关心「取哪几个数」，
不关心「怎么算」。
"""

from __future__ import annotations

import math
from collections import Counter
from typing import Any, Sequence

from ..core.types import CommentRow

# --------------------------------------------------------------- 基础统计


def safe_div(a: float, b: float, *, default: float = 0.0) -> float:
    """安全除法。分母为 0 时给 ``default``，不抛异常。

    信号层处处要除（评论数、点赞数都可能为 0），每处都写 if 太吵。
    """
    try:
        return a / b if b else default
    except (TypeError, ZeroDivisionError):
        return default


def mean(xs: Sequence[float]) -> float:
    return sum(xs) / len(xs) if xs else 0.0


def sd(xs: Sequence[float], *, sample: bool = False) -> float:
    """标准差。

    ``sample=True`` 用 ``n-1``（样本标准差）。默认用总体标准差 ——
    这里算的是「这一篇的评论区」而非从更大总体抽样，
    所以总体形式更合适。
    """
    n = len(xs)
    if n < 2:
        return 0.0
    m = mean(xs)
    var = sum((x - m) ** 2 for x in xs) / (n - 1 if sample else n)
    return math.sqrt(var)


def quantile(xs: Sequence[float], q: float) -> float:
    """线性插值分位数（``q`` 取 0..1）。

    不依赖 numpy —— 项目只用标准库。
    """
    if not xs:
        return 0.0
    s = sorted(xs)
    if len(s) == 1:
        return s[0]
    pos = q * (len(s) - 1)
    lo = math.floor(pos)
    hi = math.ceil(pos)
    if lo == hi:
        return s[int(pos)]
    frac = pos - lo
    return s[lo] * (1 - frac) + s[hi] * frac


def iqr(xs: Sequence[float]) -> float:
    """四分位距 Q3-Q1。比标准差更抗离群（一条 500 字长评不会毁掉它）。"""
    if len(xs) < 2:
        return 0.0
    return quantile(xs, 0.75) - quantile(xs, 0.25)


def median(xs: Sequence[float]) -> float:
    return quantile(xs, 0.5)


def entropy(counter: Counter) -> float:
    """香农熵（nats）。分布越均匀熵越大。"""
    total = sum(counter.values())
    if total <= 0:
        return 0.0
    acc = 0.0
    for v in counter.values():
        if v <= 0:
            continue
        p = v / total
        acc -= p * math.log(p)
    return acc


def normalized_entropy(counter: Counter) -> float:
    """熵归一化到 0..1（除以 ``ln(类别数)``）。

    为什么必须归一：一个只有 2 个 IP 的帖和一个有 20 个 IP 的帖，
    原始熵不可比。归一后「1 = 完全均匀，0 = 全集中在一类」是同一个尺度。
    """
    k = len(counter)
    if k <= 1:
        return 0.0
    return entropy(counter) / math.log(k)


def top1_ratio(counter: Counter) -> float:
    """最高频类别的占比。"""
    total = sum(counter.values())
    if total <= 0:
        return 0.0
    return counter.most_common(1)[0][1] / total


# --------------------------------------------------------------- 归一化

def clamp01(x: float) -> float:
    return 0.0 if x < 0 else (1.0 if x > 1 else float(x))


def saturate(x: float, *, k: float = 1.0) -> float:
    """把非负值压到 0..1：``x/(x+k)``。

    用途：把「越大越可疑」的原始量变成 0..1 且无上界问题。
    ``k`` 是半饱和点（``x=k`` 时输出 0.5）。
    """
    x = max(float(x), 0.0)
    return clamp01(x / (x + k)) if (x + k) > 0 else 0.0


def band_risk(x: float, *, lo: float, hi: float,
              pad: float) -> float:
    """「越接近 [lo, hi] 区间越**正常**」的风险值。

    用途：某些量在**中等范围**才正常（如正文长度 —— 太短是广告卡片、
    太长是软文，中间才是正常分享）。

    返回值
    ------
    - 落在 ``[lo, hi]`` 内 → **0**（正常）
    - 落在区间外 → 按距离线性上升，超过 ``pad`` 达到 **1.0**

    ⚠️ 曾经写反过（区间内返回 1.0），导致 ``text_length`` 把 379 字的
    正常正文判成满风险。所以这里配了单测锁死方向。
    """
    if lo <= x <= hi:
        return 0.0
    if pad <= 0:
        return 1.0
    d = (lo - x) if x < lo else (x - hi)
    return clamp01(d / pad)


# --------------------------------------------------------------- 评论视图

def lens_of(comments: Sequence[CommentRow],
            *, replies: bool | None = None) -> list[float]:
    """评论正文长度列表。

    ``replies``：``True`` 只要楼中楼、``False`` 只要一级、``None`` 全要。
    """
    return [float(len(c.content)) for c in comments
            if (replies is None or c.is_reply == replies)]


def content_weights(comments: Sequence[CommentRow]) -> list[float]:
    """每条评论的「信息量」权重。

    纯 emoji / 表情占位（``[笑哭R]``）的评论几乎不含信息，
    但长度会拉低标准差。所以给它们低权重 —— 具体做法是按长度开方，
    短评的权重被压低但仍非零。
    """
    return [math.sqrt(max(len(c.content), 1)) for c in comments]


def weighted_sd(values: Sequence[float],
                 weights: Sequence[float]) -> float:
    """加权标准差。权重 0 的样本不影响结果。"""
    if len(values) != len(weights) or len(values) < 2:
        return 0.0
    wsum = sum(weights)
    if wsum <= 0:
        return 0.0
    m = sum(v * w for v, w in zip(values, weights)) / wsum
    var = sum(w * (v - m) ** 2 for v, w in zip(values, weights)) / wsum
    return math.sqrt(var)


def is_low_effort(text: str, *, max_len: int = 8) -> bool:
    """低信息量评论：纯表情、纯标点、或极短。

    小红书的 emoji 是 ``[笑哭R]`` 这种文本形式，去掉后只剩标点的
    就是打卡式回复。
    """
    t = text.strip()
    if len(t) <= max_len:
        return True
    # 去掉 [xxx] 形态的表情与常见标点后，还剩多少实义字符
    import re
    stripped = re.sub(r"\[[^\[\]]{1,12}\]", "", t)
    stripped = re.sub(r"[\s，。！？、,.!?~～…—\-]+", "", stripped)
    return len(stripped) == 0


__all__ = [
    "safe_div", "mean", "sd", "quantile", "iqr", "median",
    "entropy", "normalized_entropy", "top1_ratio",
    "clamp01", "saturate", "band_risk",
    "lens_of", "content_weights", "weighted_sd", "is_low_effort",
]

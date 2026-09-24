# -*- coding: utf-8 -*-
"""行动门控：布尔逻辑门只出现在这一层。

分工（不要混淆）：
- 分数层（fusion）：logit 加权融合，概率连续、可解释、权重可学；
- 决策层（本模块）：把连续分数变成「要不要动手」的布尔动作。

为什么这里用逻辑门而不是再加一层加权：
1. 自动打标是高代价动作（误伤博主代价高于漏放），语义上必须「都同意才动手」，
   即 AND；而送人工复核宁可多不可漏，即 OR。这两种语义用布尔表达最清晰、
   行为最可预期，不需要也不应该被学习出来。
2. 布尔层无法表达「证据冲突」，所以冲突必须在上游就落到 🟡 不确定档，
   本层只消费 verdict，不再重新解释连续分数。
"""

from __future__ import annotations

try:
    from .fusion import VERDICT_SUSPICIOUS, VERDICT_UNCERTAIN
except ImportError:
    from fusion import VERDICT_SUSPICIOUS, VERDICT_UNCERTAIN  # type: ignore


def decide(verdict_lr: str, p_lr: float, p_jev: float | None = None,
           tau_lr: float | None = None, tau_jev: float | None = None,
           t1: float = 0.70, t2: float = 0.70) -> dict:
    """返回动作门控结果。

    - auto_flag     自动打标：两者都高才动手（AND，保守）
    - human_review  进人工复核队列：任一可疑即入队（OR，保召回）
    - degraded      Jev 不可用时只依赖取证侧，并显式标记降级
    """
    t1 = tau_lr if tau_lr is not None else t1
    t2 = tau_jev if tau_jev is not None else t2
    lr_hit = p_lr >= t1
    jev_available = p_jev is not None
    jev_hit = (p_jev >= t2) if jev_available else False

    if jev_available:
        auto_flag = bool(lr_hit and jev_hit)
    else:
        # 降级：单侧证据不足以自动打标，只入人工队列
        auto_flag = False

    human_review = bool(lr_hit or jev_hit or verdict_lr == VERDICT_UNCERTAIN)
    return {
        "auto_flag": auto_flag,
        "human_review": human_review,
        "policy": "auto=AND(保守), review=OR(保召回)",
        "thresholds": {"t1_lr": t1, "t2_jev": t2},
        "degraded": not jev_available,
        "explain": _explain(lr_hit, jev_hit, jev_available, verdict_lr),
    }


def _explain(lr_hit: bool, jev_hit: bool, jev_available: bool, verdict: str) -> str:
    if not jev_available:
        return ("语义侧不可用，已降级为仅取证侧判定："
                f"取证分{'过线' if lr_hit else '未过线'}，"
                f"判定档位 {verdict}；单侧证据不触发自动打标。")
    if lr_hit and jev_hit:
        return "取证侧与语义侧同时过线，满足保守门控（AND），可自动打标。"
    if lr_hit != jev_hit:
        return ("两侧证据冲突（一侧过线一侧未过线），不自动打标，"
                "转人工复核。")
    if verdict == VERDICT_UNCERTAIN:
        return ("两侧均未过线，但综合分数落在不确定区间，"
                "按『证据不足』转人工复核。")
    return "两侧均未过线且分数低于不确定区，仅记录。"


def gate_from_card(card: dict, t1: float = 0.70, t2: float = 0.70) -> dict:
    """从证据卡直接得到门控结果（下游 Agent 的便捷入口）。"""
    p_lr = float(card.get("p_suspect", 0.0))
    p_jev = card.get("features", {}).get("x7_jev")
    return decide(verdict_lr=str(card.get("verdict", VERDICT_UNCERTAIN)),
                  p_lr=p_lr,
                  p_jev=(float(p_jev) if p_jev is not None else None),
                  t1=t1, t2=t2)

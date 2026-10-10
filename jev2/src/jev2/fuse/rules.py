"""融合层的**规则集** —— 决策逻辑全在这里，声明式，可换。

一条规则 = 公式 + 参数 + 输入 + 动作
-----------------------------------
::

    Rule(name="ad_gate",
         formula=indicator_ge,          # 用哪个数学公式
         args={"t": 0.85},              # 公式的参数
         inputs=("is_ad",),             # 从 context 取哪些值
         action="veto")                 # 命中后干什么

三种 action
-----------
``veto``
    一票否决：命中直接把总分拉满，不再看其它规则。
    只给 ``is_ad`` 用（理由见下）。
``contribute``
    加权贡献：``value × weight`` 累加进总分。
``flag``
    只记录不参与计分 —— 用于「观察到但还没想好怎么用」的量。
    这是 L2 信号第一版的默认动作。

为什么只有 is_ad 能 veto
------------------------
legacy-jev 踩过这个坑：最初让所有维度都能短路，
结果 ``is_cta=0.88`` 也判高风险，**误判了一篇成分党硬核测评**。

**强引导 ≠ 高风险** —— 真诚推荐也会有强引导。
只有「广告身份」是结构性的。

换规则集
--------
加一个具名规则集（如 ``STRICT_RULES``），在 config 里
``fuse.rule_set = "strict"`` 即可切换。引擎一行不改。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

from . import formulas as F


@dataclass(frozen=True, slots=True)
class Rule:
    """一条声明式规则。"""

    name: str
    action: str                                  # veto | contribute | flag
    #: 公式函数。``None`` = 直接用输入值（等价于 identity）。
    formula: Callable[..., float] | None = None
    #: 公式参数（阈值等）。**这是数据，不是代码**。
    args: dict[str, Any] = field(default_factory=dict)
    #: 从 context 取哪些键。取不到就跳过这条规则（记 skipped）。
    inputs: tuple[str, ...] = ()
    weight: float = 0.0
    #: 人类可读的说明 —— 报告里会打出来，「凭什么这么判」的答案。
    note: str = ""


# --------------------------------------------------------------- 默认规则集

DEFAULT_RULES: tuple[Rule, ...] = (
    # ── 一票否决 ────────────────────────────────────────────────
    Rule(
        name="ad_gate",
        action="veto",
        formula=F.indicator_ge,
        args={"t": 0.85},
        inputs=("is_ad",),
        note=(
            "is_ad ≥ 0.85 一票否决。legacy-jev 实测：加权平均会把纯广告"
            "稀释（官方活动贴 is_ad=0.96 被拉到加权 0.642 → 误判中风险），"
            "加这道门后高风险召回 40% → 100%。"
        ),
    ),

    # ── 语义维度加权（Layer 1）──────────────────────────────────
    Rule(
        name="risk",
        action="contribute",
        formula=F.identity,
        inputs=("has_risk",),
        weight=0.35,
        note="风险用语。权重最高 —— 违规宣称是最硬的信号。",
    ),
    Rule(
        name="exaggeration",
        action="contribute",
        formula=F.identity,
        inputs=("exaggeration",),
        weight=0.30,
        note="夸大程度。",
    ),
    Rule(
        name="is_ad",
        action="contribute",
        formula=F.identity,
        inputs=("is_ad",),
        weight=0.25,
        note="广告身份。未到 0.85 时按权重进总分。",
    ),
    Rule(
        name="is_cta",
        action="contribute",
        formula=F.identity,
        inputs=("is_cta",),
        weight=0.10,
        note=(
            "购买引导。**权重最低且不能 veto** —— 真诚推荐也有强引导，"
            "legacy 实测让它短路会误判成分党测评。"
        ),
    ),

    # ── L2 统计信号（第一版只 flag，不进权重）────────────────────
    #
    # 为什么不进权重：40 篇样本 + 没有 ground truth，任何权重都是过拟合。
    # 想启用就在 config.fuse.weights 里加 "l2_mean" 键 —— 引擎会自动
    # 把下面这条从 flag 提升为 contribute（见 engine._resolve_action）。
    Rule(
        name="l2_stats",
        action="flag",
        formula=F.identity,
        inputs=("l2_mean",),
        weight=0.0,
        note=(
            "统计信号聚合值。**默认只展示不参与计分** —— "
            "等有人工判读的 ground truth 后再给它权重。"
        ),
    ),
)


# --------------------------------------------------------------- 具名规则集

RULE_SETS: dict[str, tuple[Rule, ...]] = {
    "default": DEFAULT_RULES,

    #: 严格版：把 L2 拉进权重，并把 is_cta 的门槛降低。
    #: 用于「宁可错杀」的场景（如批量风控预筛）。
    "strict": (
        Rule(name="ad_gate", action="veto", formula=F.indicator_ge,
             args={"t": 0.75}, inputs=("is_ad",),
             note="严格版：is_ad 门槛从 0.85 降到 0.75"),
        Rule(name="risk", action="contribute", formula=F.identity,
             inputs=("has_risk",), weight=0.35),
        Rule(name="exaggeration", action="contribute", formula=F.identity,
             inputs=("exaggeration",), weight=0.25),
        Rule(name="is_ad", action="contribute", formula=F.identity,
             inputs=("is_ad",), weight=0.25),
        Rule(name="is_cta", action="contribute", formula=F.identity,
             inputs=("is_cta",), weight=0.15),
        Rule(name="l2_stats", action="contribute", formula=F.identity,
             inputs=("l2_mean",), weight=0.20,
             note="严格版：统计信号进权重"),
    ),

    #: 只跑语义层（不看统计信号）。用于和 legacy-jev 对比，
    #: 验证「统计信号到底有没有带来增量」。
    "semantic_only": (
        Rule(name="ad_gate", action="veto", formula=F.indicator_ge,
             args={"t": 0.85}, inputs=("is_ad",),
             note="与 default 相同的一票否决，保证可比"),
        Rule(name="risk", action="contribute", formula=F.identity,
             inputs=("has_risk",), weight=0.35),
        Rule(name="exaggeration", action="contribute", formula=F.identity,
             inputs=("exaggeration",), weight=0.30),
        Rule(name="is_ad", action="contribute", formula=F.identity,
             inputs=("is_ad",), weight=0.25),
        Rule(name="is_cta", action="contribute", formula=F.identity,
             inputs=("is_cta",), weight=0.10),
    ),
}


def get_rules(name: str = "default") -> tuple[Rule, ...]:
    """按名字取规则集。"""
    if name not in RULE_SETS:
        raise KeyError(
            f"未知规则集 {name!r}。可用: {', '.join(sorted(RULE_SETS))}"
        )
    return RULE_SETS[name]


def describe_rules(name: str = "default") -> list[dict[str, Any]]:
    """规则集的可读描述（报告/调试用）。"""
    out = []
    for r in get_rules(name):
        out.append({
            "name": r.name,
            "action": r.action,
            "formula": getattr(r.formula, "__name__", "-") if r.formula else "identity",
            "args": r.args,
            "inputs": list(r.inputs),
            "weight": r.weight,
            "note": r.note,
        })
    return out


__all__ = ["Rule", "DEFAULT_RULES", "RULE_SETS", "get_rules",
           "describe_rules"]

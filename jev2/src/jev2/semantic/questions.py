"""提问模板库 —— **问题也是注册表**。

为什么问题要独立成数据
----------------------
1. **可版本化**：提示词是模型行为的核心变量，必须能 diff、能回滚。
2. **可 A/B**：同一批数据换一套问法跑一遍，比一致性 ——
   legacy-jev 实测「改一句话措辞，一致率 66.7% → 83.3%」。
3. **`criteria_order` 的顺序即风险梯度**：:func:`normalize_answer`
   依赖它把概率加权成 0..1，**顺序错了整个分数就错**。

措辞的三条原则（血泪）
----------------------
- **限定边界**：题干要说明「什么算、什么不算」。``is_ad`` 若不写
  「personal sharing is NOT an advertisement」，真实 UGC 会被大面积误判。
- **互斥穷尽**：choice 的 criteria 要覆盖所有情况，否则概率质量下降。
- **不引导**：题干不要暗示答案倾向。

加一个新维度
------------
1. 在 ``QUESTIONS`` 里加一个 :class:`QuestionSpec`
2. 在 ``config.semantic.dims`` 里加上它的名字
3. 在 ``config.fuse.weights`` 里给它一个权重（想先只观察就跳过这步）

不需要改 runner，也不需要改 provider。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ..core.registry import Registry


@dataclass(frozen=True, slots=True)
class QuestionSpec:
    """一个语义维度的提问定义。"""

    name: str
    qtype: str                    # noul | choice | score
    instructions: str
    #: **顺序即风险递增**（low → high）。normalize_answer 用它加权。
    criteria_order: tuple[str, ...] = ()
    #: choice 专属：每个 criterion 的说明
    criteria_desc: dict[str, str] = field(default_factory=dict)
    label: str = ""               # 人类可读名，报告里用
    note: str = ""                # 定这个措辞的原因（留痕，便于回溯）

    def to_payload(self) -> dict[str, Any]:
        """转成 jev API 的 questions 片段。"""
        if self.qtype == "choice":
            return {
                "type": "choice",
                "instructions": self.instructions,
                "criteria": self.criteria_desc or {k: k
                                                   for k in self.criteria_order},
            }
        if self.qtype == "score":
            return {
                "type": "score",
                "instructions": self.instructions,
                "criteria": list(self.criteria_order),
            }
        return {"type": "noul", "instructions": self.instructions}


#: 问题注册表。与信号共用同一套 Registry 实现。
QUESTIONS: Registry[QuestionSpec] = Registry("question")


def question(name: str, **kw: Any):
    """装饰器写法用不上（QuestionSpec 是数据），这里用直接注册。"""
    raise NotImplementedError("请直接用 QUESTIONS.register(spec.name, spec)")


def register(spec: QuestionSpec) -> QuestionSpec:
    return QUESTIONS.register(spec.name, spec)


# --------------------------------------------------------------- 内置维度
#
# 措辞全部继承 legacy-jev 已 A/B 校准的版本 —— 那是 22 次付费调用换来的，
# 不要凭感觉改。要改就改完再跑一次 A/B（见 docs/JEV2_PLAN.md P6）。

register(QuestionSpec(
    name="is_ad",
    qtype="noul",
    label="商业推广",
    note=(
        "legacy 实测：不写 'personal sharing is NOT an advertisement' "
        "会把真实 UGC 大面积误判为广告。"
    ),
    instructions=(
        "Is this post a commercial advertisement or soft promotion for a "
        "brand or product? Answer true only if it was written to drive "
        "purchases or was sponsored/paid. Personal sharing of a product "
        "the author genuinely used is NOT an advertisement."
    ),
))

register(QuestionSpec(
    name="has_risk",
    qtype="noul",
    label="风险用语",
    note=(
        "措辞经 A/B 校准（legacy tools/ab_has_risk.py，22 次付费调用）：\n"
        "旧措辞把「描述副作用」误判成「疗效宣称」——\n"
        "  '换了之后脸总是干痒刺痛' → 旧 0.50（误判，这是消费者披露）\n"
        "  '这个面霜能治痘消炎'     → 旧 0.60（正确，这是违规宣称）\n"
        "两者语义相反：宣称是保证你治好，描述是披露我过敏了。\n"
        "新措辞显式区分后：真阳性 0.885→0.855 保住，"
        "真阴性 0.437→0.182 修复，零新误判。"
    ),
    instructions=(
        "Does the AUTHOR make a risky PROMISE about the product? "
        "Judge only what the author claims the product will DO.\n"
        "Answer TRUE for: promises to cure, treat, heal, or repair "
        "damaged skin; absolute terms (100%, best, only, guaranteed, "
        "permanent); guaranteed results; claims that override "
        "individual differences.\n"
        "Answer FALSE for: the author describing their OWN negative "
        "experience (irritation, redness, breakouts, dryness they "
        "experienced); quoting someone else's claim in order to "
        "criticize it; listing ingredients and their concentration; "
        "reporting clinical numbers with proper context; ordinary "
        "subjective opinion."
    ),
))

register(QuestionSpec(
    name="exaggeration",
    qtype="score",
    label="夸大程度",
    note="顺序即风险递增，不可随意调整 —— normalize_answer 靠它加权。",
    criteria_order=("none", "mild", "exaggerated", "extreme"),
    instructions=(
        "How exaggerated or overstated are the efficacy claims in this "
        "text? Judge the language used, not whether the product works."
    ),
))

register(QuestionSpec(
    name="is_cta",
    qtype="noul",
    label="购买引导",
    instructions=(
        "Does the text explicitly ask or suggest the reader to take a "
        "purchase-related action such as buying, ordering, clicking a "
        "link, joining a group chat, or using a discount code?"
    ),
))

register(QuestionSpec(
    name="claim_type",
    qtype="choice",
    label="宣称类型",
    note="分类标签，**不进加权** —— 只用于报告分组。",
    criteria_order=("none", "promotion", "skincare", "medical"),
    criteria_desc={
        "none": "No product or efficacy claim at all",
        "promotion": "Promotional content with no efficacy claim",
        "skincare": "Cosmetic or skincare efficacy claims",
        "medical": "Medical or therapeutic claims",
    },
    instructions="What kind of claim does this post make?",
))

register(QuestionSpec(
    name="sentiment",
    qtype="score",
    label="情感倾向",
    note=(
        "可选维度（默认不进 dims）。加它只需在 config.semantic.dims 写上 "
        "名字，再在 fuse.weights 给个权重。"
    ),
    criteria_order=("very_negative", "negative", "neutral",
                    "positive", "very_positive"),
    instructions=(
        "What is the overall sentiment of this text toward the product?"
    ),
))


# --------------------------------------------------------------- 出口

def specs_for(dims: list[str] | tuple[str, ...] | None) -> dict[str, QuestionSpec]:
    """取指定维度的问题定义。``None`` / 空 = 全部。"""
    return QUESTIONS.select(dims)


def to_payload(dims: list[str] | tuple[str, ...] | None) -> dict[str, dict]:
    """转成 API 的 ``questions`` 字段。"""
    return {name: q.to_payload() for name, q in specs_for(dims).items()}


__all__ = ["QuestionSpec", "QUESTIONS", "register",
           "specs_for", "to_payload"]

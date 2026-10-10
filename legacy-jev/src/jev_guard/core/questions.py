"""提问模板库。

为什么把提问抽出来独立管理
--------------------------
1. **可版本化**：提示词是模型行为的核心变量，必须能 diff、能回滚。
2. **可A/B**：同一批数据换一套提问跑一遍，用一致性比较哪种问法更稳定。
3. **criteria 顺序即风险梯度**：:func:`~jev_guard.core.models.normalize_answer`
   依赖它做加权，顺序错���整个分数就错。

提问措辞的原则
--------------
- **限定边界**：题干要说明「什么算、什么不算」。实测 ``is_ad`` 若不写
  "not personal sharing"，真实UGC 会被大量误判为广告。
- **互斥穷尽**：choice 的 criteria 要能覆盖所有情况，否则概率质量下降。
- **不引导**：题干不要暗示答案倾向。
"""

from __future__ import annotations

from ..core.models import QuestionSpec, SubjectKind

# --------------------------------------------------------------- 笔记维度

NOTE_SPECS: dict[str, QuestionSpec] = {
    "is_ad": QuestionSpec(
        name="is_ad",
        qtype="noul",
        label="商业推广",
        instructions=(
            "Is this post a commercial advertisement or soft promotion for a "
            "brand or product? Answer true only if it was written to drive "
            "purchases or was sponsored/paid. Personal sharing of a product "
            "the author genuinely used is NOT an advertisement."
        ),
    ),
    "is_cta": QuestionSpec(
        name="is_cta",
        qtype="noul",
        label="购买引导",
        instructions=(
            "Does the text explicitly ask or suggest the reader to take a "
            "purchase-related action such as buying, ordering, clicking a "
            "link, joining a group chat, or using a discount code?"
        ),
    ),
    "has_risk": QuestionSpec(
        name="has_risk",
        qtype="noul",
        label="风险用语",
        # 措辞经 A/B 实测校准（tools/ab_has_risk.py，付费 jev-1.13）。
        #
        # 旧措辞把「描述产品副作用」误判成「疗效宣称」：
        #   "换了之后脸总是干痒刺痛"           → 旧 0.50（误判）
        #   "这个面霜能治痘消炎"               → 旧 0.60（正确）
        # 两者语义相反：宣称是保证你治好，描述是披露我过敏了。
        #
        # 新措辞显式区分二者，22 次调用实测：
        #   真阳性（绝对化宣称）0.885 → 0.855  保住
        #   真阴性（真实测评）    0.437 → 0.182  修复，且未引入新误判
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
    ),
    "exaggeration": QuestionSpec(
        name="exaggeration",
        qtype="score",
        label="夸大程度",
        # 顺序即风险递增，不可随意调整
        criteria_order=("none", "mild", "exaggerated", "extreme"),
        instructions=(
            "How exaggerated or overstated are the efficacy claims in this "
            "text? Judge the language used, not whether the product works."
        ),
    ),
    "claim_type": QuestionSpec(
        name="claim_type",
        qtype="choice",
        label="宣称类型",
        criteria_order=("none", "promotion", "skincare", "medical"),
        criteria_desc={
            "none": "No product or efficacy claim at all",
            "promotion": "Promotional content with no efficacy claim",
            "skincare": "Cosmetic or skincare efficacy claims",
            "medical": "Medical or therapeutic claims",
        },
        instructions="What kind of claim does this post make?",
    ),
}

#: 参与风险总分的维度（claim_type 是分类标签，不进加权）。
NOTE_WEIGHTED = ("has_risk", "exaggeration", "is_ad", "is_cta")


# --------------------------------------------------------------- 评论维度

COMMENT_SPECS: dict[str, QuestionSpec] = {
    "is_ad": QuestionSpec(
        name="is_ad",
        qtype="noul",
        label="广告引流",
        instructions=(
            "Is this comment an advertisement, spam, or traffic diversion "
            "(link dropping, promo code, brand shilling)?"
        ),
    ),
    "sentiment": QuestionSpec(
        name="sentiment",
        qtype="score",
        label="负面程度",
        criteria_order=("positive", "neutral", "negative", "hostile"),
        instructions=(
            "How negative is this comment toward the product being discussed?"
        ),
        dimension="negativity",
    ),
    "is_useful": QuestionSpec(
        name="is_useful",
        qtype="noul",
        label="真实体验",
        instructions=(
            "Does this comment describe a concrete, genuine personal "
            "experience with the product, including specific details? "
            "Answer false for generic praise, emoji-only, or off-topic."
        ),
    ),
}

COMMENT_WEIGHTED = ("is_ad", "negativity")


SPECS_BY_KIND = {
    SubjectKind.NOTE: NOTE_SPECS,
    SubjectKind.COMMENT: COMMENT_SPECS,
}


def get_specs(kind: SubjectKind) -> dict[str, QuestionSpec]:
    return dict(SPECS_BY_KIND[kind])


def weighted_dims(kind: SubjectKind) -> tuple[str, ...]:
    return NOTE_WEIGHTED if kind is SubjectKind.NOTE else COMMENT_WEIGHTED
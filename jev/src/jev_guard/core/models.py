"""数据模型。

设计原则
--------
1. **不可变**：判定结果一旦生成就不该被改。用 ``frozen=True`` + ``slots=True``。
2. **可序列化**：所有模型都能 ``to_dict()`` 直接落 JSON，不需要自定义 encoder。
3. **显式单位/量纲**：概率都是 0..1，分数都是 0..1，不混用。
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Any


class RiskLevel(str, Enum):
    """风险档位。"""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"

    @property
    def label(self) -> str:
        return {"low": "低风险", "medium": "中风险", "high": "高风险"}[self.value]

    @property
    def rank(self) -> int:
        return {"low": 0, "medium": 1, "high": 2}[self.value]


class SubjectKind(str, Enum):
    """判定对象的类型。"""

    NOTE = "note"
    COMMENT = "comment"


@dataclass(frozen=True, slots=True)
class DimensionScore:
    """单个维度的判定结果。

    ``value`` 是归一化到 0..1 的分数，无论底层是 noul还是 score 都统一到这里。
    ``raw`` 保留模型原始返回，便于调试和二次分析。
    """

    name: str                    # 维度 ID，如 has_risk
    value: float                 # 0..1，越高越危险
    confidence: float | None = None   # 模型自评置信度，仅 choice/score 有
    detail: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not 0.0 <= self.value <= 1.0:
            raise ValueError(
                f"{self.name} 的 value={self.value} 超出 0..1，"
                "归一化逻辑有 bug"
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "value": round(self.value, 4),
            "confidence": (round(self.confidence, 4)
                           if self.confidence is not None else None),
            "detail": self.detail,
        }


@dataclass(frozen=True, slots=True)
class RiskScore:
    """一条内容的综合风险评分。"""

    subject_id: str
    kind: SubjectKind
    total: float                          # 0..1 加权综合分
    level: RiskLevel
    dimensions: tuple[DimensionScore, ...]
    evidence: tuple[str, ...] = ()       # 触发判定的关键片段
    notes: tuple[str, ...] = ()          # 补充说明

    def top_factor(self) -> DimensionScore | None:
        """最高分的维度 —— 用于「主要因为什么被判高风险」。"""
        return max(self.dimensions, key=lambda d: d.value) if self.dimensions else None

    def to_dict(self) -> dict[str, Any]:
        return {
            "subject_id": self.subject_id,
            "kind": self.kind.value,
            "total": round(self.total, 4),
            "level": self.level.value,
            "level_label": self.level.label,
            "dimensions": [d.to_dict() for d in self.dimensions],
            "top_factor": (self.top_factor().name
                           if self.top_factor() else None),
            "evidence": list(self.evidence),
            "notes": list(self.notes),
        }


@dataclass(frozen=True, slots=True)
class QuestionSpec:
    """单个维度的提问定义。

    ``criteria_order`` 是有序标签列表，**顺序即风险递增**。
    归一化时用它把 probabilities 加权成 0..1，所以顺序不能随意排。
    """

    name: str
    qtype: str                # noul | choice | score
    instructions: str
    criteria_order: tuple[str, ...] = ()   # choice/score 用，noul 留空
    criteria_desc: dict[str, str] = field(default_factory=dict)  # choice 用
    dimension: str = ""       # 归一化后归属的维度名，默认等于 name
    label: str = ""           # 人类可读名

    def to_payload(self) -> dict[str, Any]:
        """转成 jev API 的 questions 片段。"""
        if self.qtype == "choice":
            return {"type": "choice", "instructions": self.instructions,
                    "criteria": self.criteria_desc or
                    {k: k for k in self.criteria_order}}
        if self.qtype == "score":
            return {"type": "score", "instructions": self.instructions,
                    "criteria": list(self.criteria_order)}
        return {"type": "noul", "instructions": self.instructions}

    @property
    def dim(self) -> str:
        return self.dimension or self.name


#: 维度名 -> QuestionSpec 的映射。:class:`Label.from_response` 依赖它。
QuestionSpecMap = dict[str, QuestionSpec]


@dataclass(frozen=True, slots=True)
class Label:
    """一条内容上全部维度的原始判定结果（未经阈值/加权处理）。"""

    subject_id: str
    kind: SubjectKind
    dimensions: tuple[DimensionScore, ...]
    model: str
    raw: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "subject_id": self.subject_id,
            "kind": self.kind.value,
            "model": self.model,
            "dimensions": {d.name: d.to_dict() for d in self.dimensions},
            "raw": self.raw,
        }

    @classmethod
    def from_response(
        cls,
        subject_id: str,
        kind: SubjectKind,
        response: dict[str, Any],
        spec: "QuestionSpecMap",
        model: str,
    ) -> "Label":
        """从 jev 原始响应构造。"""
        answers = response.get("answers") or response
        dims: list[DimensionScore] = []
        raw: dict[str, Any] = {}
        for qid, q in spec.items():
            a = answers.get(qid) or {}
            if not isinstance(a, dict):
                continue
            value = normalize_answer(a, q.criteria_order)
            if value is None:
                continue
            dims.append(DimensionScore(
                name=q.dim,
                value=value,
                confidence=(float(a["confidence"])
                            if a.get("confidence") is not None else None),
                detail=_compact_detail(a),
            ))
            raw[qid] = a
        return cls(subject_id=subject_id, kind=kind,
                   dimensions=tuple(dims), model=model, raw=raw)


def normalize_answer(answer: dict[str, Any],
                     criteria_order: tuple[str, ...] | None) -> float | None:
    """把任意题型的返回统一成 0..1。

    - ``noul``  -> 直接用 ``noul`` 字段
    - ``score`` -> **不用 score**，改用 ``probabilities`` 加权平均。

      原因：score 是 0..len(criteria)-1 的连续索引，量纲随 criteria 长度变化，
      且模型可能输出 2.97 这种非整数。probabilities 是归一化概率，更稳定。

    - ``choice``-> 同上，用 probabilities 按 criteria_order 加权。
    """
    qtype = answer.get("type")

    if qtype == "noul" or (qtype is None and "noul" in answer):
        v = answer.get("noul")
        return None if v is None else float(v)

    probs = answer.get("probabilities")
    if isinstance(probs, dict) and probs:
        if not criteria_order:
            # 没有 criteria 参照，只能退化成最大值概率的可信度
            return max(float(v) for v in probs.values())
        n = len(criteria_order)
        if n == 1:
            return 0.0
        acc = 0.0
        wsum = 0.0
        for idx, label in enumerate(criteria_order):
            raw_p = probs.get(str(idx), probs.get(label))
            if raw_p is None:
                continue
            acc += float(raw_p) * (idx / (n - 1))
            wsum += float(raw_p)
        return acc / wsum if wsum > 0 else 0.0

    sc = answer.get("score")
    if sc is not None and criteria_order and len(criteria_order) > 1:
        return min(max(float(sc) / (len(criteria_order) - 1), 0.0), 1.0)

    return None


def _compact_detail(answer: dict[str, Any]) -> dict[str, Any]:
    """只保留有用的诊断字段，避免 raw 无限膨胀。"""
    keep: dict[str, Any] = {}
    for k in ("choice", "legend", "probabilities"):
        if k in answer:
            keep[k] = answer[k]
    return keep
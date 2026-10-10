"""全系统共用的数据类型。

分层契约
--------
每一层只认相邻层的类型，不跨层偷看：

    loader        →  NoteRecord          （数据）
    signals       →  SignalResult        （统计信号）
    semantic      →  DimScore            （语义维度）
    fuse          →  Verdict             （最终裁决）
    store         →  JSONL

三条不可变的约定
----------------
1. **全部 frozen + slots**：判定结果一旦生成不该被改。
   要改就 ``dataclasses.replace`` 出新的，语义明确。
2. **value 一律 0..1**：不管底层是概率、计数还是标准差，
   进 ``SignalResult`` / ``DimScore`` 之前都归一化。
   量纲统一是后面能任意组合公式的前提。
3. **缺失是一等公民**：``value=None`` + ``missing_reason``，
   绝不拿 0 冒充「没有数据」—— 0 是「测出来就是 0」，两回事。
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field, replace
from enum import Enum
from pathlib import Path
from typing import Any


class Level(str, Enum):
    """风险档位。三档（用户确认）。"""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"

    @property
    def label(self) -> str:
        return {"low": "低风险", "medium": "中风险", "high": "高风险"}[self.value]

    @property
    def rank(self) -> int:
        return {"low": 0, "medium": 1, "high": 2}[self.value]


# --------------------------------------------------------------- 数据层

@dataclass(frozen=True, slots=True)
class CommentRow:
    """一条评论（已摊平，楼中楼与一级同构，靠 ``is_reply`` 区分）。"""

    cid: str
    content: str
    nickname: str
    ip_location: str
    like_count: str          # 保持字符串：可能是 "1千+" 这类展示值
    time_ms: int
    is_author: bool          # ⚠️ SSR 恒 False，见 loader 的兜底推导
    is_reply: bool
    parent_id: str = ""      # 仅楼中楼有

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class NoteRecord:
    """一篇笔记的统一视图。

    **loader 是唯一构造它的地方** —— 数据结构变了只改 loader。
    所有信号的输入都是这个类型，因此信号之间不可能对「什么叫一条评论」
    产生分歧。
    """

    note_id: str
    title: str = ""
    desc: str = ""
    tags: tuple[str, ...] = ()
    author: str = ""
    author_id: str = ""

    #: 计数字段统一转 int。``""`` / ``"-1"`` / ``"1.2万"`` 都在这转干净，
    #: 原始值留在 ``raw_counts`` 里备查（"-1 表示平台不公开"这类信息不能丢）。
    liked: int = 0
    collected: int = 0
    comment_count: int = 0
    comment_count_l1: int = 0
    share: int = 0

    published_ms: int = 0
    ip_location: str = ""
    images: tuple[str, ...] = ()
    comments: tuple[CommentRow, ...] = ()

    #: 平台未公开的计数字段名（值缺失 ≠ 值为 0，报告里要能区分）
    raw_counts: dict[str, Any] = field(default_factory=dict)
    source_path: Path | None = None

    # ---- 便捷视图（信号层反复要用）----

    @property
    def top_comments(self) -> tuple[CommentRow, ...]:
        """一级评论。"""
        return tuple(c for c in self.comments if not c.is_reply)

    @property
    def replies(self) -> tuple[CommentRow, ...]:
        """楼中楼。"""
        return tuple(c for c in self.comments if c.is_reply)

    @property
    def text(self) -> str:
        """标题 + 正文 + 标签，拼成送模型的文本（也供文本信号用）。"""
        parts = []
        if self.title:
            parts.append(f"标题：{self.title}")
        if self.desc:
            parts.append(f"正文：{self.desc}")
        if self.tags:
            parts.append(f"话题：{' '.join(self.tags)}")
        return "\n".join(parts)

    @property
    def author_comments(self) -> tuple[CommentRow, ...]:
        """作者自己发的评论（含楼中楼）。

        SSR 的 ``is_author`` 恒为 False，所以 loader 会额外用
        「评论者昵称 == 作者昵称」兜底推导，结果写在这个标志里。
        """
        return tuple(c for c in self.comments if c.is_author)

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["source_path"] = str(self.source_path) if self.source_path else None
        return d


# --------------------------------------------------------------- 信号层

@dataclass(frozen=True, slots=True)
class SignalResult:
    """一个统计信号的计算结果。

    ``value`` 归一化到 0..1（越高越可疑），``None`` 表示**没有数据**。
    两者语义不同，融合时必须区别对待：缺失是跳过，0 是参与。
    """

    name: str
    value: float | None = None
    n: int = 0
    detail: dict[str, Any] = field(default_factory=dict)
    missing_reason: str = ""

    def __post_init__(self) -> None:
        if self.value is not None and not 0.0 <= self.value <= 1.0:
            raise ValueError(
                f"信号 {self.name} 的 value={self.value} 超出 0..1，"
                "归一化逻辑有 bug"
            )

    @property
    def missing(self) -> bool:
        return self.value is None

    @classmethod
    def ok(cls, name: str, value: float, *, n: int = 0,
           **detail: Any) -> "SignalResult":
        return cls(name=name, value=float(value), n=n, detail=detail)

    @classmethod
    def missing_(cls, name: str, reason: str, *,
                 n: int = 0) -> "SignalResult":
        """构造「缺失」结果。

        名字带下划线是因为 ``missing`` 已是属性名，同名会遮蔽。
        """
        return cls(name=name, value=None, n=n, missing_reason=reason)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "value": None if self.value is None else round(self.value, 4),
            "n": self.n,
            "missing": self.missing,
            "missing_reason": self.missing_reason,
            "detail": self.detail,
        }


# --------------------------------------------------------------- 语义层

@dataclass(frozen=True, slots=True)
class DimScore:
    """一个语义维度（jev）的判定。

    与 :class:`SignalResult` 结构相近但**语义不同**：这个来自模型，
    那个来自本地计算。分开放是为了报告里能一眼看出「哪句是人算的、
    哪句是模型说的」。
    """

    name: str
    value: float
    confidence: float | None = None
    qtype: str = ""                    # noul | score | choice
    detail: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not 0.0 <= self.value <= 1.0:
            raise ValueError(
                f"维度 {self.name} 的 value={self.value} 超出 0..1"
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "value": round(self.value, 4),
            "confidence": (round(self.confidence, 4)
                           if self.confidence is not None else None),
            "qtype": self.qtype,
            "detail": self.detail,
        }


@dataclass(frozen=True, slots=True)
class SemanticResult:
    """一篇笔记的语义层结果。"""

    note_id: str
    model: str
    dims: tuple[DimScore, ...]
    raw: dict[str, Any] = field(default_factory=dict)

    def dim(self, name: str) -> DimScore | None:
        return next((d for d in self.dims if d.name == name), None)

    def as_context(self) -> dict[str, float]:
        """摊成 ``{维度名: 值}``，供融合层的公式取用。"""
        return {d.name: d.value for d in self.dims}

    def to_dict(self) -> dict[str, Any]:
        return {
            "note_id": self.note_id,
            "model": self.model,
            "dims": {d.name: d.to_dict() for d in self.dims},
            "raw": self.raw,
        }


# --------------------------------------------------------------- 融合层

@dataclass(frozen=True, slots=True)
class RuleTrace:
    """单条规则的求值痕迹 —— 「凭什么这么判」的答案。"""

    rule: str
    action: str                        # veto | contribute | flag
    value: float | None = None         # 公式输出（None = 输入缺失跳过）
    weight: float = 0.0
    contribution: float = 0.0          # value × weight
    skipped: bool = False
    reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "rule": self.rule,
            "action": self.action,
            "value": None if self.value is None else round(self.value, 4),
            "weight": self.weight,
            "contribution": round(self.contribution, 4),
            "skipped": self.skipped,
            "reason": self.reason,
        }


@dataclass(frozen=True, slots=True)
class Verdict:
    """最终裁决。"""

    note_id: str
    total: float
    level: Level
    dimensions: tuple[DimScore, ...] = ()
    signals: tuple[SignalResult, ...] = ()
    trace: tuple[RuleTrace, ...] = ()
    vetoed_by: str = ""                # 被哪条一票否决规则命中（空=没有）
    notes: tuple[str, ...] = ()

    @property
    def top_dim(self) -> DimScore | None:
        """贡献最大的语义维度 —— 「主要因为什么」。"""
        return max(self.dimensions, key=lambda d: d.value) if self.dimensions else None

    @property
    def top_signal(self) -> SignalResult | None:
        vals = [s for s in self.signals if not s.missing]
        return max(vals, key=lambda s: s.value or 0.0) if vals else None

    def with_notes(self, *extra: str) -> "Verdict":
        return replace(self, notes=self.notes + tuple(extra))

    def to_dict(self) -> dict[str, Any]:
        return {
            "note_id": self.note_id,
            "total": round(self.total, 4),
            "level": self.level.value,
            "level_label": self.level.label,
            "vetoed_by": self.vetoed_by,
            "dimensions": {d.name: d.to_dict() for d in self.dimensions},
            "signals": {s.name: s.to_dict() for s in self.signals},
            "trace": [t.to_dict() for t in self.trace],
            "notes": list(self.notes),
        }


__all__ = [
    "Level", "CommentRow", "NoteRecord",
    "SignalResult", "DimScore", "SemanticResult",
    "RuleTrace", "Verdict",
]

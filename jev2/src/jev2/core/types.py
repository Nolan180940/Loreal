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
    like_count: str          # ⚠️ SSR 的 likeCount，**恒为 "0"**（内部计数器）
    time_ms: int
    is_author: bool          # ⚠️ SSR 恒 False，见 loader 的兜底推导
    is_reply: bool
    parent_id: str = ""      # 楼中楼：挂在哪条一级评论下（用 cid 配对）

    # ---- 2026-10-11 新增（旧数据没有这些键，默认值兼容）----

    #: **展示给用户看的点赞数**。与 ``like_count`` 不同，这个有真值
    #: （实测 310/56/24 这种）。旧数据为空串 —— 那是**没采到**，
    #: 不是「没人赞」，所以信号层要按缺失处理。
    #:
    #: 语义依据：某帖 5373 赞 / 1980 评论，热评的该值只有 310/56/24
    #: 且多条为 0 —— 若是「浏览量」不可能这么低（被展示过就必然有人看）。
    like_view_count: str = ""
    #: 评论状态。实测 ``-2`` = 审核中/仅自己可见（卖家帖 5/5 全是 -2）。
    #: 旧数据恒 0，无法区分「正常」与「未采集」。
    status: int = 0
    #: 楼中楼声明数（可判断楼中楼是否抓全）。
    sub_comment_count: int = 0
    #: 楼中楼回复的直接对象 id（可能是另一条楼中楼 —— 嵌套回复）。
    target_id: str = ""
    #: 平台注册的 AI 账号标记（SSR ``user.aiAgent``）。
    #:
    #: ``None`` = 旧数据未采集；``False`` = 真人；``True`` = 平台注册 AI。
    #: 实测本语料 1822 条全 False/None —— 它抓的是「平台注册的 AI agent」
    #: （官方 AI 助手 / 品牌 AI 客服），**抓不到真人水军**。
    #: 但它是硬标记：True 时无需统计验证，直接当「非真人评论」处理。
    ai_agent: bool | None = None

    @property
    def has_view_like(self) -> bool:
        """这个点赞数是不是**真的采到了**。

        旧数据的 ``like_count`` 恒 "0"、``like_view_count`` 恒空，
        两者都不是真值。信号层必须先问这个属性，
        否则会把「没采到」当成「没人赞」——那正是 `comment_like_rate`
        当初「恒 missing」的成因。
        """
        return bool(self.like_view_count)

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
    #: 作者的官方认证类型（SSR ``user.redOfficialVerifyType``）。
    #:
    #: 实测取值：``0`` = 无认证（卖家帖 / KOL 帖 / 普通分享），
    #: ``2`` = 品牌官方（雅诗兰黛官方活动帖）。
    #: ``-1`` = 旧数据未采集。
    #:
    #: 为什么值钱：**品牌官方号发帖 → is_ad 几乎确定**。
    #: 雅诗兰黛那篇语义层给 is_ad=0.97，这个字段是零成本的交叉验证。
    #: 候选信号（``author_is_brand``），等品牌官方帖样本多了再验证。
    author_verify_type: int = -1
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

    @property
    def has_view_likes(self) -> bool:
        """这一篇的评论点赞数**采到了没有**。

        2026-10-11 之前的 ``data/`` 全是旧格式（``like_count`` 恒 "0"，
        无 ``like_view_count``），此时这个属性是 False ——
        信号层必须据此返回 missing，而不是把「没采到」算成「没人赞」。
        """
        return any(c.has_view_like for c in self.comments)

    @property
    def author_is_brand(self) -> bool | None:
        """作者是不是品牌官方号。

        ``None`` = 旧数据未采集（``author_verify_type == -1``）。
        判据：认证类型非 0 即算（实测 2 = 品牌官方；
        1 大概率是个人黄 V，未实测到 —— 若将来发现 1 是个人认证，
        这里要收窄成 ``== 2``）。
        """
        if self.author_verify_type <= 0:
            return None if self.author_verify_type < 0 else False
        return True

    def comment_by_id(self, cid: str) -> CommentRow | None:
        """按 ``cid`` 找评论。

        有 ``id`` 字段的数据里，楼中楼的 ``parent_id`` 就是一级评论的
        ``cid`` —— 所以这个查找能把回复真的挂回父评论。
        旧数据（cid 是拼出来的）查不到，返回 None。
        """
        if not cid:
            return None
        for c in self.comments:
            if c.cid == cid:
                return c
        return None

    def children_of(self, cid: str) -> tuple[CommentRow, ...]:
        """直接挂在某条评论下的楼中楼。"""
        return tuple(c for c in self.comments if c.parent_id == cid)

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

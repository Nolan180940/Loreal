"""规则引擎：把 jev 的维度分合成最终风险判定。

为什么是「加权求和 + 阈值」而不是分类器
----------------------------------------
1. 无需标注数据。当前 42篇笔记没有任何可信标签（标注表与采集数据对不上）。
2. 可解释。每个维度独立给出，权重显式可调，PPT 里能逐条讲。
3. 可校准。有了标注数据后，只需重拟合 :class:`~jev_guard.core.config.WeightConfig`
   和 :class:`~jev_guard.core.config.RiskThresholds`，代码不用改。

聚合公式::

    total = Σ(weight_i × value_i) / Σ(weight_i)

归一化除以权重和，让total 始终落在 0..1，且改权重不会改变量纲。
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from .config import RiskThresholds, WeightConfig
from .models import DimensionScore, Label, RiskLevel, RiskScore, SubjectKind

# ---------------------------------------------------------------- 证据抽取

#: 命中即作为证据展示的模式。顺序即展示优先级。
#: 这些是中文小红书营销文的高频违规表述，覆盖「绝对化」「医疗暗示」「诱导」三类。
RISK_PATTERNS: tuple[tuple[str, str, str], ...] = (
    # (正则, 维度, 说明)
    (r"\d+\s*%(?!\s*的)|百分之百|百分百", "has_risk", "百分比绝对化宣称"),
    (r"100\s*%|百分之百保证|无添加|零添加|无副作用", "has_risk", "绝对化承诺"),
    (r"(根治|治愈|治疗|疗效|药用|消炎|抗菌|修复受损细胞)", "has_risk", "医疗用语越界"),
    (r"(国家级|全球领先|第一品牌|最好|最强|最佳|唯一|顶级|天花板)", "exaggeration", "最高级用语"),
    (r"(秒杀|立刻见效|一夜|马上|立刻|当天见效|立竿见影)", "exaggeration", "即时见效宣称"),
    (r"(永久|终身|一次见效|永不|彻底去除|完全消除)", "exaggeration", "绝对化效果"),
    (r"(赶紧|冲|剁手|买它|闭眼入|无脑冲|上车|姐妹们冲|码住)", "is_cta", "诱导购买"),
    (r"(链接|购物车|橱窗|点击|下单|直播间|折扣|特价|限时)", "is_cta", "购物引导"),
    (r"(广告|推广|赞助|合作|恰饭|kol|种草位)", "is_ad", "商业身份声明"),
)

#: 命中这些词**降低**风险 —— 真实体验的表达特征。
CREDIBILITY_MARKERS: tuple[tuple[str, str], ...] = (
    (r"(我用了|用了.{0,4}(个月|周|天|年)|空瓶|回购|入手|踩雷|翻车)", "has_risk", "第一人称使用体验"),
    (r"(缺点|不足|不适合|慎入|避雷|别买|智商税)", "exaggeration", "主动指出不足"),
    (r"(油皮|干皮|混合皮|敏感肌|痘痘肌|中性皮)", "has_risk", "明确肤质"),
)

#: 中文分句。保留标点作为证据片段的一部分。
_SENT_SPLIT = re.compile(r"(?<=[。！？!?\n；;])")


@dataclass(frozen=True, slots=True)
class EvidenceHit:
    """一条证据：命中了什么、出现在哪句话、属于哪个维度。"""

    dimension: str
    reason: str
    fragment: str

    def to_dict(self) -> dict[str, str]:
        return {"dimension": self.dimension, "reason": self.reason,
                "fragment": self.fragment}


def extract_evidence(text: str, max_items: int = 5) -> tuple[EvidenceHit, ...]:
    """从正文里抽取可读的证据片段。

    这是「可解释」的关键：模型只给分数，用户需要知道**为什么**。
    这里用正则定位违规表述所在的句子，比让模型自己引用更可靠 ——
    实测 jev 的 ``noul``/``score`` 返回里没有 span 信息。
    """
    if not text:
        return ()
    sentences = [s.strip() for s in _SENT_SPLIT.split(text) if s.strip()]
    hits: list[EvidenceHit] = []

    for sent in sentences:
        for pat, dim, reason in RISK_PATTERNS:
            m = re.search(pat, sent, re.IGNORECASE)
            if not m:
                continue
            # 片段取命中位置前后，控制在 60 字内
            lo = max(0, m.start() - 20)
            hi = min(len(sent), m.end() + 40)
            frag = sent[lo:hi].strip()
            hits.append(EvidenceHit(dim, reason, frag))
            break   # 每句只报第一条，避免刷屏
    return tuple(hits[:max_items])


def extract_credibility(text: str) -> tuple[EvidenceHit, ...]:
    """抽取「降低风险」的信号：真实体验的 linguistic marker。"""
    if not text:
        return ()
    hits: list[EvidenceHit] = []
    for pat, dim, reason in CREDIBILITY_MARKERS:
        m = re.search(pat, text, re.IGNORECASE)
        if not m:
            continue
        lo = max(0, m.start() - 20)
        hi = min(len(text), m.end() + 30)
        hits.append(EvidenceHit(dim, reason, text[lo:hi].strip()))
    return tuple(hits)


# ---------------------------------------------------------------- 规则引擎

@dataclass(frozen=True, slots=True)
class Override:
    """短路规则结果。

    背景（2026-10 实测发现的设计缺陷）
    ----------------------------------
    加权平均会把「纯广告」稀释掉。一篇官方活动贴典型维度：

        is_ad=0.96  exaggeration=0.47  has_risk=0.61  is_cta=0.48

    四项加权后只有 0.642，落在中风险 —— 但它**没有任何夸大宣称**，
    加权平均却因为「夸大程度低」把一个100% 商业广告判成了中等风险。

    这是加权平均的固有缺陷：**它假设各维度独立，但广告身份是
    一票否决式的** —— 无论内容写得多克制，只要它是广告，风险就成立。

    解决：任一维度超过 gate 阈值时直接判定，不参与加权。
    """

    level: RiskLevel
    reason: str


#: 一票否决阈值。超过则直接定档。
#: 0.85 的依据：实测 3 篇官方活动贴 is_ad=0.87~0.96，
#: 而真实 UGC 软广最高只到 0.79，0.85 能干净地分开。
GATE_THRESHOLD = 0.85

#: 只有这些维度参与一票否决。
#:
#: 为什么只给 is_ad：广告身份是**结构性**的 —— 一篇纯广告无论写得多克制，
#: 它仍是广告。而 is_cta 高只说明「在引导购买」，一篇真诚的推荐贴同样会有
#: 强引导（实测一篇成分党硬核测评 is_cta=0.88，但人工判为 low）。
#: has_risk / exaggeration 高通常已经会带动加权总分，不需要短路。
GATE_DIMS = ("is_ad",)


def check_gate(dims: tuple[DimensionScore, ...],
               threshold: float = GATE_THRESHOLD,
               only: tuple[str, ...] = GATE_DIMS) -> Override | None:
    """检查是否触发短路规则。"""
    for d in dims:
        if d.name in only and d.value >= threshold:
            return Override(
                level=RiskLevel.HIGH,
                reason=f"{d.name}={d.value:.2f} ≥ {threshold:.2f}，触发一票否决",
            )
    return None


class RuleEngine:
    """把 :class:`Label` 转成 :class:`RiskScore`。"""

    def __init__(self,
                 thresholds: RiskThresholds | None = None,
                 weights: WeightConfig | None = None,
                 credibility_discount: float = 0.15,
                 gate: float | None = GATE_THRESHOLD) -> None:
        self.t = thresholds or RiskThresholds()
        self.w = weights or WeightConfig()
        # 有第一人称体验 + 主动指出不足时，整体风险下调。
        # 上限 0.15：真实性只能减轻，不能洗白绝对化宣称。
        self.credibility_discount = credibility_discount
        # 短路阈值；设为 None 关闭
        self.gate = gate

    # ---- 主入口 ----
    def evaluate(self,
                 label: Label,
                 text: str = "",
                 extra_signals: dict[str, float] | None = None) -> RiskScore:
        """合成风险分。

        ``extra_signals`` 用于叠加非 jev 的信号（如 IP 集中度），
        键必须与 :class:`WeightConfig` 的字段对齐才会被计入。
        """
        notes: list[str] = []

        # --- 短路：广告身份一票否决 ---
        if self.gate is not None:
            ov = check_gate(label.dimensions, self.gate)
            if ov:
                notes.append(f"一票否决：{ov.reason}")
                notes.append("（广告身份不因内容克制而降低风险）")
                return RiskScore(
                    subject_id=label.subject_id,
                    kind=label.kind,
                    total=1.0,
                    level=ov.level,
                    dimensions=label.dimensions,
                    evidence=(),
                    notes=tuple(notes),
                )

        cred = extract_credibility(text)
        if cred:
            notes.append(
                "检测到第一人称使用体验或主动指出不足，"
                f"风险下调 {self.credibility_discount:.0%}"
            )

        contributions: list[tuple[str, float, float]] = []   # (dim, value, weight)
        for d in label.dimensions:
            w = getattr(self.w, d.name, 0.0)
            if w <= 0:
                # 没有配置权重的维度：仍展示，但不进总分
                notes.append(f"维度 {d.name} 未配置权重，仅展示")
                continue
            v = d.value
            if self.credibility_discount and cred:
                v = max(0.0, v - self.credibility_discount)
            contributions.append((d.name, v, w))

        if extra_signals:
            for k, v in extra_signals.items():
                w = getattr(self.w, k, 0.0)
                if w > 0:
                    contributions.append((k, float(v), w))
                    notes.append(f"叠加信号 {k}={v:.2f}")

        if not contributions:
            total = 0.0
        else:
            num = sum(v * w for _, v, w in contributions)
            den = sum(w for _, _, w in contributions)
            total = num / den if den else 0.0

        level = self.to_level(total)

        ev = extract_evidence(text)
        if not ev and level is RiskLevel.HIGH:
            notes.append(
                "高风险但未匹配到具体违规措辞 —— "
                "可能是隐晦表达，建议人工复核"
            )

        return RiskScore(
            subject_id=label.subject_id,
            kind=label.kind,
            total=round(total, 4),
            level=level,
            dimensions=label.dimensions,
            evidence=tuple(h.fragment for h in ev),
            notes=tuple(notes),
        )

    def to_level(self, total: float) -> RiskLevel:
        if total >= self.t.high:
            return RiskLevel.HIGH
        if total >= self.t.medium:
            return RiskLevel.MEDIUM
        return RiskLevel.LOW

    # ---- 校准 ----
    def calibrate(self, samples: list[tuple[float, bool]]) -> dict[str, float]:
        """用带标签的样本拟合阈值。

        ``samples``: [(total_score, is_high_risk), ...]

        做法：在候选网格上找使 F1 最大的阈值。样本少时退化为返回当前值，
        并在调用方日志里提示样本不足。
        """
        if len(samples) < 20:
            return {"high": self.t.high, "medium": self.t.medium,
                    "n": len(samples), "converged": False}
        grid = [i / 100 for i in range(30, 96, 5)]
        best, best_f1 = self.t.high, -1.0
        for th in grid:
            tp = sum(1 for s, y in samples if s >= th and y)
            fp = sum(1 for s, y in samples if s >= th and not y)
            fn = sum(1 for s, y in samples if s < th and y)
            prec = tp / (tp + fp) if tp + fp else 0.0
            rec = tp / (tp + fn) if tp + fn else 0.0
            f1 = (2 * prec * rec / (prec + rec)) if prec + rec else 0.0
            if f1 > best_f1:
                best_f1, best = f1, th
        return {"high": best, "medium": self.t.medium,
                "n": len(samples), "f1": round(best_f1, 4),
                "converged": True}
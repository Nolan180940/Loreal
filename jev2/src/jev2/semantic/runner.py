"""语义层：把一篇笔记送进 jev-1.13，拿回 N 个维度的分数。

state 拼装
----------
喂什么文本是**数据**（``config.semantic`` 的 include_* / top_comments），
不是写死的。原因：评论有没有帮助、要不要送标题，这类问题只能靠 A/B 回答。

答案归一化
----------
jev 的三种题型返回结构不同，统一在 :func:`normalize_answer` 里处理成 0..1。
**这个函数是从 legacy-jev 原样搬来的**，因为它踩过坑：

- ``noul`` → 直接用 ``noul`` 字段（模型给的 0..1 概率）
- ``score`` → **不用 score，改用 probabilities 加权**。
  原因：``score`` 是 0..len(criteria)-1 的连续索引，量纲随 criteria 长度变，
  且模型会输出 2.97 这种非整数。probabilities 是归一化概率，更稳定。
- ``choice`` → 同 score，按 ``criteria_order`` 加权。
"""

from __future__ import annotations

from typing import Any

from ..config.schema import SemanticConfig
from ..core.errors import ProviderError
from ..core.types import DimScore, NoteRecord, SemanticResult
from . import questions as Q
from .provider import JevProvider


def build_state(record: NoteRecord, cfg: SemanticConfig) -> str:
    """把笔记拼成送模型的文本。

    顺序：标题 → 正文 → 标签 →（可选）若干条评论。

    为什么送评论：评论区常含「作者自评」「其他人质疑」这类信号，
    模型看了能更准地判 is_ad（作者在评论里解释「不是广告」vs
    在评论里发优惠码，两种情况下正文可能一样）。
    """
    parts: list[str] = []
    if cfg.include_title and record.title:
        parts.append(f"标题：{record.title}")
    if cfg.include_desc and record.desc:
        parts.append(f"正文：{record.desc}")
    if cfg.include_tags and record.tags:
        parts.append(f"话题：{' '.join(record.tags)}")

    if cfg.top_comments > 0 and record.comments:
        lines = []
        for c in record.comments[: cfg.top_comments]:
            mark = "【作者】" if c.is_author else ""
            mark += "（回复）" if c.is_reply else ""
            ip = f"[{c.ip_location}]" if c.ip_location else ""
            lines.append(f"  {mark}{c.nickname}{ip}：{c.content}")
        parts.append("评论：\n" + "\n".join(lines))

    return "\n".join(parts)


def normalize_answer(answer: dict[str, Any],
                     criteria_order: tuple[str, ...] | None) -> float | None:
    """把任意题型的返回统一成 0..1。无法解析返回 ``None``。

    **不要改这里的判据顺序** —— 见模块 docstring。
    """
    qtype = answer.get("type")

    # noul：模型直接给概率
    if qtype == "noul" or (qtype is None and "noul" in answer):
        v = answer.get("noul")
        return None if v is None else min(max(float(v), 0.0), 1.0)

    # score / choice：用 probabilities 按 criteria_order 加权
    probs = answer.get("probabilities")
    if isinstance(probs, dict) and probs:
        if not criteria_order:
            # 没有 criteria 参照，退化成「最大概率」当可信度用
            return min(max(float(max(probs.values())), 0.0), 1.0)
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
        return min(max(acc / wsum, 0.0), 1.0) if wsum > 0 else 0.0

    # 兜底：退化的连续 score
    sc = answer.get("score")
    if sc is not None and criteria_order and len(criteria_order) > 1:
        return min(max(float(sc) / (len(criteria_order) - 1), 0.0), 1.0)

    return None


def _compact(answer: dict[str, Any]) -> dict[str, Any]:
    """只留有用的诊断字段，避免 raw 无限膨胀。"""
    return {k: answer[k] for k in ("choice", "legend", "probabilities")
            if k in answer}


def parse_response(note_id: str, model: str, raw: dict[str, Any],
                   dims: list[str]) -> SemanticResult:
    """把 jev 原始响应解析成 :class:`SemanticResult`。"""
    answers = raw.get("answers") if isinstance(raw.get("answers"), dict) else raw
    specs = Q.specs_for(dims)

    out: list[DimScore] = []
    detail_raw: dict[str, Any] = {}
    for qid, spec in specs.items():
        a = answers.get(qid)
        if not isinstance(a, dict):
            continue
        value = normalize_answer(a, spec.criteria_order)
        if value is None:
            continue
        out.append(DimScore(
            name=qid,
            value=value,
            confidence=(float(a["confidence"])
                        if a.get("confidence") is not None else None),
            qtype=spec.qtype,
            detail=_compact(a),
        ))
        detail_raw[qid] = a

    return SemanticResult(note_id=note_id, model=model,
                          dims=tuple(out), raw=detail_raw)


class SemanticRunner:
    """批量跑语义层。"""

    def __init__(self, cfg: SemanticConfig, provider: JevProvider) -> None:
        self._cfg = cfg
        self._p = provider
        self._payload = Q.to_payload(cfg.dims)

    @property
    def provider(self) -> JevProvider:
        return self._p

    def judge(self, record: NoteRecord) -> SemanticResult:
        """判一篇。

        Raises
        ------
        ProviderError
            模型没返回任何可解析的维度 —— 静默返回空结果会让下游
            把「模型挂了」当成「所有维度都是 0」，那是最危险的失败模式。
        """
        state = build_state(record, self._cfg)
        raw = self._p.ask(state, self._payload)
        res = parse_response(record.note_id, self._cfg.model, raw, self._cfg.dims)
        if not res.dims:
            raise ProviderError(
                f"模型返回里没有可解析的维度（期望 {self._cfg.dims}）"
                f"，原始响应键: {sorted(raw)[:8]}"
            )
        return res

    def dims_present(self) -> tuple[str, ...]:
        return tuple(self._payload)


__all__ = ["SemanticRunner", "build_state", "normalize_answer",
           "parse_response"]

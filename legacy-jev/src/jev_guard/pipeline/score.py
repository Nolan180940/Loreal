"""评分流水线：把标签 + 正文 -> 最终风险判定。"""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path
from typing import Any

from ..core.config import Config
from ..core.errors import DataError
from ..core.models import Label, RiskLevel, SubjectKind
from ..core.scoring import RuleEngine
from ..extractors.reader import (Subject, comment_length_spread, iter_note_ids,
                                 load_comments, load_note, note_ip_stats)
from .store import LabelStore, ResultStore


def build_index(labels_path: Path) -> dict[str, Label]:
    """从 JSONL 标签文件重建 ``{subject_id: Label}``。"""
    idx: dict[str, Label] = {}
    if not labels_path.is_file():
        return idx
    with labels_path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            sid = rec.get("subject_id")
            if not sid:
                continue
            dims = []
            for name, d in (rec.get("dimensions") or {}).items():
                try:
                    dims.append(_mk_dim(name, d))
                except (TypeError, ValueError):
                    continue
            kind = SubjectKind(rec.get("kind") or "note")
            idx[sid] = Label(
                subject_id=sid, kind=kind, dimensions=tuple(dims),
                model=rec.get("model", ""), raw=rec.get("raw") or {},
            )
    return idx


def _mk_dim(name: str, d: dict[str, Any]):
    from ..core.models import DimensionScore
    return DimensionScore(
        name=name,
        value=float(d.get("value") or 0.0),
        confidence=(float(d["confidence"])
                    if d.get("confidence") is not None else None),
        detail=d.get("detail") or {},
    )


def score_all(cfg: Config,
               label_path: Path,
               out_path: Path,
               use_ip_signals: bool = True,
               use_spread: bool = True,
               reset: bool = False) -> dict[str, Any]:
    """对所有已打标的笔记评分并落盘。

    评论级的分数也存在同一文件里，用 ``kind`` 字段区分。

    ``use_ip_signals`` / ``use_spread``
        分别是 IP 集中度（借用 is_ad 权重）和 Layer 2 传播质量信号的开关。
        两者都**只影响 notes / Layer 2 字段**，不改变 Layer 1 的 level。
    """
    idx = build_index(label_path)
    if not idx:
        raise DataError(
            f"标签文件为空或不存在: {label_path}\n"
            "先跑 `jev-guard label --kind note`"
        )

    engine = RuleEngine(cfg.thresholds, cfg.weights)
    store = ResultStore(out_path)
    if reset:
        store.reset()

    existing = {r["subject_id"] for r in store.load()}
    counts = {lv: 0 for lv in RiskLevel}
    spread_flagged = 0
    scored = skipped = 0

    # 先处理笔记（能拿到正文做证据抽取 + IP 统计）
    # 注意：iterdir() 给的是 Path，必须先取 .name 再排序。
    # 直接排序 Path 会得到 "a/b/c" 形式的字典序，虽然对同层目录也成立，
    # 但之前误写成对 Path 排序后当字符串用，导致和标签索引匹配不上。
    note_ids = sorted(iter_note_ids(cfg.data_root))
    for nid in note_ids:
        label = idx.get(nid)
        if label is None:
            continue
        if nid in existing:
            skipped += 1
            continue
        subj = load_note(cfg.data_root, nid)
        if subj is None:
            continue
        extra = {}
        if use_ip_signals:
            st = note_ip_stats(cfg.data_root, nid)
            # IP 集中度高 -> 额外风险。用 is_ad 的权重折算成 0..1 信号。
            if st["ip_n"] >= 20 and st["ip_top1_ratio"] > 0.4:
                extra["is_ad"] = round(st["ip_top1_ratio"], 4)
        rs = engine.evaluate(label, text=subj.text_for_model,
                             extra_signals=extra)

        # ---- Layer 2：传播质量（不影响 total / level）----
        # 只对笔记算；评论自身没有"评论区"。
        if use_spread:
            sp = comment_length_spread(cfg.data_root, nid)
            rs = rs.with_spread(
                n=sp["n"], mean=sp["mean"], sd=sp["sd"],
                flag=sp["spread_flag"],
            )
            if sp["spread_flag"]:
                spread_flagged += 1
                rs = replace(
                    rs,
                    notes=rs.notes + (
                        f"评论区长度标准差 {sp['sd']:.1f}（{sp['n']} 条），"
                        f"整齐得不自然 —— 疑似模板化/刷评（不影响内容判定）",
                    ),
                )

        store.save(rs.to_dict())
        counts[rs.level] += 1
        scored += 1

    # 评论
    for nid in note_ids:
        for c in load_comments(cfg.data_root, nid):
            label = idx.get(c.subject_id)
            if label is None or c.subject_id in existing:
                continue
            rs = engine.evaluate(label, text=c.text)
            store.save(rs.to_dict())
            counts[rs.level] += 1
            scored += 1

    return {
        "scored": scored, "skipped": skipped,
        "high": counts[RiskLevel.HIGH],
        "medium": counts[RiskLevel.MEDIUM],
        "low": counts[RiskLevel.LOW],
        "spread_flagged": spread_flagged,
        "out": str(out_path),
        "thresholds": {"high": cfg.thresholds.high,
                       "medium": cfg.thresholds.medium},
    }


def top_risky(out_path: Path, limit: int = 20,
              kind: str = "note") -> list[dict[str, Any]]:
    """读结果文件，返回风险最高的若干条。"""
    rows = [r for r in ResultStore(out_path).load()
            if r.get("kind") == kind]
    rows.sort(key=lambda r: -float(r.get("total") or 0))
    return rows[:limit]
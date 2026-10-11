"""编排：读数据 → 跑信号 → 跑语义 → 融合 → 落盘。

数据流是单向的，每步产出不可变对象::

    loader.load_all()        → list[NoteRecord]
    SignalSet.compute()      → dict[str, SignalResult]
    SemanticRunner.judge()   → SemanticResult
    FuseEngine.evaluate()    → Verdict
    ResultStore.upsert_many()→ scores.jsonl

三种容错策略（按异常类型分）
----------------------------
``DataError``
    单篇数据坏 → 跳过它，继续下一篇。40 篇坏 1 篇不该让报告出不来。
``ProviderError``（不含 AuthError）
    模型调用失败 → 记下来，**该篇跳过语义层**，用纯统计信号出结果
    （``semantic_ok=False`` 标记），不伪装成「语义层是干净的」。
``AuthError``
    凭据无效 → **立刻停止整批**。重试没意义，继续跑只会把
    「所有调用都失败」写成一堆假结果。
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Iterable

from ..config import config_hash
from ..config.schema import Config
from ..core.errors import AuthError, DataError, ProviderError
from ..core.types import NoteRecord, SignalResult, Verdict
from ..fuse.engine import EngineConfig, FuseEngine
from ..loader import load_all
from ..report import write_note_bundle
from ..semantic.provider import JevProvider
from ..semantic.runner import SemanticRunner
from ..signals import SignalContext, SignalSet
from .store import ResultStore, RunMeta

ProgressFn = Callable[[str], None]


def _noop(_: str) -> None:
    pass


@dataclass
class JudgeResult:
    """单篇的完整判定（含所有中间产物）。"""

    note_id: str
    verdict: Verdict
    signals: dict[str, SignalResult] = field(default_factory=dict)
    semantic_ok: bool = True
    semantic_error: str = ""
    elapsed_ms: int = 0

    def to_row(self, *, meta: RunMeta,
               note: NoteRecord | None = None) -> dict[str, Any]:
        """转成 ``scores.jsonl`` 的一行。

        结构：元信息 + 裁决 + 全部中间值。
        **中间值都要留** —— 调阈值时不用重跑模型，看历史行就行。
        """
        d = dict(meta.to_dict())
        d.update(self.verdict.to_dict())
        d["semantic_ok"] = self.semantic_ok
        if self.semantic_error:
            d["semantic_error"] = self.semantic_error
        d["elapsed_ms"] = self.elapsed_ms
        if note is not None:
            d["note"] = {
                "title": note.title,
                "author": note.author,
                # 作者认证：0=无 · 2=品牌官方 · -1=未采集
                # 两个都写 —— 原始值供程序读，布尔值让产物自解释
                # （0/2 的映射规则在代码里，不写布尔值的话
                #   看产物的人不知道 "2" 是什么意思）
                "author_verify_type": note.author_verify_type,
                "author_is_brand": note.author_is_brand,
                "liked": note.liked,
                "comment_count": note.comment_count,
                "comments_got": len(note.comments),
                "images": len(note.images),
            }
        return d


class Pipeline:
    """主流程编排。"""

    def __init__(self, cfg: Config, *, meta: RunMeta | None = None,
                 progress: ProgressFn | None = None) -> None:
        self.cfg = cfg
        self.log = progress or _noop
        self.store = ResultStore(cfg.paths.out_dir, meta=meta)
        self._sig = SignalSet(
            active=cfg.signals.active or None,
            ctx=SignalContext(min_samples=cfg.signals.min_samples),
        )
        self._engine = FuseEngine(EngineConfig(
            high=cfg.fuse.high,
            low=cfg.fuse.low,
            rule_set=cfg.fuse.rule_set,
            weights=dict(cfg.fuse.weights),
            veto=dict(cfg.fuse.veto),
        ))
        self._runner: SemanticRunner | None = None
        self._provider: JevProvider | None = None

    # ------------------------------------------------------------------ 装配

    def _ensure_semantic(self) -> SemanticRunner | None:
        """惰性构造语义层（不在不需要时要求 API key）。"""
        if not self.cfg.semantic.enabled:
            return None
        if self._runner is None:
            self._provider = JevProvider(self.cfg.semantic,
                                         api_key=self.cfg.api_key)
            self._runner = SemanticRunner(self.cfg.semantic, self._provider)
        return self._runner

    @property
    def stats(self) -> dict[str, Any]:
        return self._provider.stats() if self._provider else {}

    def describe_rules(self) -> list[dict[str, Any]]:
        return self._engine.describe()

    # ------------------------------------------------------------------ 单篇

    def judge_one(self, note: NoteRecord) -> JudgeResult:
        """判定一篇（不落盘）。"""
        t0 = time.monotonic()

        sig = self._sig.compute(note)
        sig_tuple = tuple(sig.values())

        # 语义层
        dims: tuple = ()
        sem_ok = True
        sem_err = ""
        runner = self._ensure_semantic()
        if runner is not None:
            try:
                sem = runner.judge(note)
                dims = sem.dims
            except ProviderError as exc:
                sem_ok = False
                sem_err = f"{type(exc).__name__}: {exc}"
                # 模型挂了不伪装成「干净」—— semantic_ok=False 会进产物
                self.log(f"  [!] 语义层失败: {sem_err[:80]}")

        # 组装 context：语义维度 + L2 聚合值
        ctx: dict[str, float] = {d.name: d.value for d in dims}
        l2 = self._aggregate_l2(sig)
        if l2 is not None:
            ctx["l2_mean"] = l2

        verdict = self._engine.evaluate(
            note.note_id, ctx, dims=dims, signals=sig_tuple)

        return JudgeResult(
            note_id=note.note_id,
            verdict=verdict,
            signals=sig,
            semantic_ok=sem_ok,
            semantic_error=sem_err,
            elapsed_ms=int((time.monotonic() - t0) * 1000),
        )

    def _aggregate_l2(self, sig: dict[str, SignalResult]) -> float | None:
        """把统计信号聚合成一个标量（供规则集的 ``l2_mean`` 取用）。

        只聚合**非缺失**的信号，且只取 ``config.fuse.l2_signals``
        指定的（空 = 全部）。缺失的不算 0 —— 那会把
        「没数据」拉低平均值，等于替平台说好话。
        """
        want = set(self.cfg.fuse.l2_signals) or None
        vals = [r.value for r in sig.values()
                if not r.missing and (want is None or r.name in want)]
        vals = [v for v in vals if v is not None]
        if not vals:
            return None

        mode = self.cfg.fuse.l2_aggregate
        if mode == "max":
            return max(vals)
        if mode == "median":
            s = sorted(vals)
            m = len(s) // 2
            return s[m] if len(s) % 2 else (s[m - 1] + s[m]) / 2
        return sum(vals) / len(vals)

    # ------------------------------------------------------------------ 批量

    def run(self, *, notes: Iterable[NoteRecord] | None = None,
            limit: int | None = None,
            skip_existing: bool = False,
            flush_every: int = 1,
            per_note: bool = False,
            max_consec_semantic_fail: int = 3) -> dict[str, Any]:
        """跑批。

        Parameters
        ----------
        skip_existing
            True 时跳过 ``scores.jsonl`` 里已有 ``note_id`` 的篇 ——
            重跑不用重新付模型钱。
        flush_every
            每 N 篇落盘一次。默认 1（每篇都写）—— 40 篇规模下
            写盘成本远低于重跑模型的成本。
        per_note
            额外为每篇落 ``out/<note_id>/{scores.json, report.md}``。
            单篇模式（``judge --note``）默认开启 —— 那时只判一篇，
            输出一个孤立目录最直观。
        max_consec_semantic_fail
            连续多少篇语义层失败就**中止整批**（0 = 不熔断）。

            为什么需要：上游 451（\"Endpoint is unavailable\"）会让
            **每一篇**都失败。不熔断的话整批会被写成 "总分全 0、
            semantic_ok=false" —— 看着像「40 篇全干净」，实际什么
            都没判。只算统计信号的 0 分和「判下来确实干净」长得一模一样，
            所以宁可不跑完。
            — 单篇偶发失败不算数，必须是**连续**。
        """
        t0 = time.monotonic()
        if notes is None:
            notes, bad = load_all(self.cfg.paths.data_root)
            for p, why in bad:
                self.log(f"  [skip] 坏数据 {p.name}: {why[:60]}")
        else:
            notes = list(notes)
        if limit:
            notes = list(notes)[:limit]

        done = self.store.existing_ids() if skip_existing else set()
        if skip_existing:
            n_all = len(self.store.existing_ids(retry_semantic_failed=False))
            retry = n_all - len(done)
            self.log(f"已有 {len(done)} 篇有效结果，将跳过"
                     + (f"；另有 {retry} 篇上次语义层失败，会重试"
                        if retry else ""))

        meta = self.store.meta or RunMeta.create(
            config_hash=config_hash(self.cfg),
            model=self.cfg.semantic.model,
            rule_set=self.cfg.fuse.rule_set)
        self.store.meta = meta

        rows: list[dict[str, Any]] = []
        note_dirs: list[str] = []
        ok = skipped = failed = 0
        sem_fail = 0
        consec_fail = 0
        aborted = ""
        total = len(notes)

        for i, note in enumerate(notes, 1):
            if note.note_id in done:
                skipped += 1
                continue
            try:
                jr = self.judge_one(note)
            except DataError as exc:
                failed += 1
                self.log(f"[{i}/{total}] {note.note_id[:8]} 数据错误: {exc}")
                continue
            except AuthError:
                # 凭据问题必须立刻停 —— 继续跑只会写一堆假结果
                self.log("[X] 凭据无效，中止整批")
                raise

            if not jr.semantic_ok:
                sem_fail += 1
                consec_fail += 1
            else:
                consec_fail = 0

            row = jr.to_row(meta=meta, note=note)
            rows.append(row)
            ok += 1

            if per_note:
                try:
                    info = write_note_bundle(
                        self.cfg.paths.out_dir, row, title=note.title)
                    note_dirs.append(info["dir"])
                except (OSError, ValueError) as exc:
                    # 单篇落盘失败不该让整批失败（汇总 jsonl 才是主产物）
                    self.log(f"  [!] 单篇产物写入失败: {exc}")

            lv = jr.verdict.level.label
            v = f" veto:{jr.verdict.vetoed_by}" if jr.verdict.vetoed_by else ""
            self.log(f"[{i}/{total}] {note.note_id[:8]} "
                     f"{jr.verdict.total:.3f} {lv}{v}")

            if flush_every > 0 and len(rows) >= flush_every:
                self.store.upsert_many(rows)
                rows = []

            if (max_consec_semantic_fail
                    and consec_fail >= max_consec_semantic_fail):
                aborted = (f"连续 {consec_fail} 篇语义层调用失败（上游"
                           f"451/限流），已中止整批")
                self.log(f"[X] {aborted} —— 剩下 {total - i} 篇未跑")
                self.log("    已跑的篇 semantic_ok=false，分数只含统计信号，"
                         "偏低不代表内容干净")
                break

        if rows:
            self.store.upsert_many(rows)

        return {
            "total": total,
            "ok": ok,
            "skipped": skipped,
            "failed": failed,
            "semantic_failed": sem_fail,
            "aborted": aborted,
            "elapsed_s": round(time.monotonic() - t0, 1),
            "run_id": meta.run_id,
            "config_hash": meta.config_hash,
            "note_dirs": note_dirs,
            "model_stats": self.stats,
            "store": self.store.summary(),
        }


__all__ = ["Pipeline", "JudgeResult"]

"""批处理流水线。

三条命令的公共骨架：限流控制、断点续跑、进度上报、优雅降级。

限流是常态而非异常
------------------
``jev-1.13-free`` 是限时免费额度，实测 254 次请求后就返回 429。
所以策略是**遇到限流就优雅停下并保留进度**，而不是重试到死：
下次重跑会自动跳过已完成的，成本为零。

这比「重试 3次然后抛异常」正确得多 —— 后者会让一次 40分钟的批处理
因为第 250 条失败而全部白跑。
"""

from __future__ import annotations

import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Iterable

from ..core.config import Config
from ..core.errors import RateLimitError
from ..core.models import Label, SubjectKind
from ..core.questions import get_specs
from ..extractors.reader import Subject
from ..providers.jev import JevProvider
from .store import LabelStore

ProgressFn = Callable[[int, int, Label], None]


@dataclass(slots=True)
class BatchResult:
    ok: int = 0
    skipped: int = 0
    failed: int = 0
    total: int = 0
    stopped_by_rate_limit: bool = False
    stop_reason: str = ""
    elapsed: float = 0.0
    cost_usd: float = 0.0
    calls: int = 0

    def to_dict(self) -> dict:
        return {
            "ok": self.ok, "skipped": self.skipped, "failed": self.failed,
            "total": self.total, "stopped_by_rate_limit": self.stopped_by_rate_limit,
            "stop_reason": self.stop_reason, "elapsed_sec": round(self.elapsed, 1),
            "cost_usd": self.cost_usd, "calls": self.calls,
        }


def run_labeling(
    subjects: Iterable[Subject],
    cfg: Config,
    store: LabelStore,
    kind: SubjectKind,
    on_progress: ProgressFn | None = None,
    resume: bool = True,
) -> BatchResult:
    """给一批内容打标。

    ``resume=True`` 时自动跳过 ``store`` 里已有的 subject_id。
    """
    specs = get_specs(kind)
    provider = JevProvider(cfg)
    done = store.done_ids() if resume else set()
    res = BatchResult()
    t0 = time.monotonic()

    subjects = list(subjects)
    res.total = len(subjects)
    if not subjects:
        res.elapsed = time.monotonic() - t0
        return res

    for i, subj in enumerate(subjects, 1):
        if subj.subject_id in done:
            res.skipped += 1
            continue

        if res.calls >= cfg.daily_budget:
            res.stopped_by_rate_limit = True
            res.stop_reason = (
                f"达到单次预算上限 {cfg.daily_budget} 次请求"
            )
            break

        try:
            raw = provider.ask(subj.text_for_model, specs)
        except RateLimitError as e:
            res.stopped_by_rate_limit = True
            res.stop_reason = f"触发平台限流: {str(e)[:120]}"
            store.sync()
            break
        except Exception as e:  # noqa: BLE001
            res.failed += 1
            # 单条失败不终止整批（网络抖动等）
            _log(f"  [FAIL] {subj.subject_id}: {type(e).__name__}: {e}")
            if res.failed >= 10:
                res.stop_reason = "连续失败 10 次，疑似服务不可用"
                store.sync()
                break
            continue

        label = Label.from_response(
            subject_id=subj.subject_id,
            kind=kind,
            response=raw,
            spec=specs,
            model=cfg.model,
        )
        store.save(label)
        res.ok += 1
        res.calls = provider.calls

        if on_progress:
            on_progress(i, res.total, label)

    store.sync()
    res.elapsed = time.monotonic() - t0
    res.calls = provider.calls
    res.cost_usd = provider.cost_usd
    return res


def _log(msg: str) -> None:
    """进度输出。

    刻意用 ``print`` 而非 logging：这是 CLI 工具，日志级别由用户自己决定，
    强行加 logger 只会让输出多一层前缀。
    """
    print(msg, file=sys.stderr, flush=True)
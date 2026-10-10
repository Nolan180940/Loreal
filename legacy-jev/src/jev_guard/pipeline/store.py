"""标签持久化 + 断点续跑。

为什么用 JSONL 而不是 SQLite
---------------------------
1. 单机、几千条量级，SQLite 的并发/事务优势用不上。
2. JSONL 天然追加，进程被 kill 也不丢已写入的行 —— 而 SQLite 需要显式 commit。
3. 文本可读，PPT 里要引用某条原始判断时可以直接 grep。
4. `git diff` 能看出判断逻辑的变化（虽然标签本身不该进仓库）。

限流中断的恢复语义
------------------
:func:`LabelStore.save` 每写N 条 fsync 一次。实测被 429打断时，
已落盘的记录完整保留，重跑 :meth:`LabelStore.done_ids` 会自动跳过。
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any, Iterable, Iterator

from ..core.models import Label


class LabelStore:
    """JSONL 标签存储。"""

    def __init__(self, path: Path, fsync_every: int = 20) -> None:
        self.path = Path(path)
        self.fsync_every = max(1, fsync_every)
        self._since_sync = 0
        self.path.parent.mkdir(parents=True, exist_ok=True)

    # ---------------------------------------------------------------- 读
    def done_ids(self) -> set[str]:
        """已打标的 subject_id 集合 —— 用于断点续跑。"""
        return {r["subject_id"] for r in self._iter() if "subject_id" in r}

    def count(self) -> int:
        return sum(1 for _ in self._iter())

    def load(self) -> dict[str, dict[str, Any]]:
        """全部读成``{subject_id: record}``。"""
        return {r["subject_id"]: r for r in self._iter() if "subject_id" in r}

    def _iter(self) -> Iterator[dict[str, Any]]:
        if not self.path.is_file():
            return
        with self.path.open(encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    yield json.loads(line)
                except json.JSONDecodeError:
                    # 上次进程被 kill 可能在尾部留了半行，跳过
                    continue

    # ---------------------------------------------------------------- 写
    def save(self, label: Label) -> None:
        rec = label.to_dict()
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        self._since_sync += 1
        if self._since_sync >= self.fsync_every:
            self.sync()

    def sync(self) -> None:
        """强制刷盘。进程正常退出前必须调用。"""
        try:
            if self.path.is_file():
                fd = os.open(self.path, os.O_RDONLY)
                try:
                    os.fsync(fd)
                finally:
                    os.close(fd)
        except OSError:
            pass
        self._since_sync = 0

    # ---------------------------------------------------------------- 其他
    def replace(self, labels: Iterable[Label]) -> None:
        """全量覆盖写入（用于校准后重跑）。"""
        tmp = self.path.with_suffix(self.path.suffix + ".tmp")
        tmp.parent.mkdir(parents=True, exist_ok=True)
        with tmp.open("w", encoding="utf-8") as f:
            for lb in labels:
                f.write(json.dumps(lb.to_dict(), ensure_ascii=False) + "\n")
        tmp.replace(self.path)


class ResultStore:
    """风险评分结果存储（JSON，便于 Agent 直接读）。"""

    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def save(self, score: dict[str, Any]) -> None:
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(score, ensure_ascii=False) + "\n")

    def load(self) -> list[dict[str, Any]]:
        if not self.path.is_file():
            return []
        out = []
        with self.path.open(encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    out.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
        return out

    def reset(self) -> None:
        if self.path.is_file():
            self.path.unlink()


class RunState:
    """运行状态：记录最近一次成功时间，用于 ``--since`` 增量模式。"""

    PATH = Path("out") / ".last_run"

    @classmethod
    def mark(cls, when: float | None = None) -> None:
        cls.PATH.parent.mkdir(parents=True, exist_ok=True)
        cls.PATH.write_text(str(when or time.time()), encoding="utf-8")

    @classmethod
    def read(cls) -> float | None:
        if not cls.PATH.is_file():
            return None
        try:
            return float(cls.PATH.read_text(encoding="utf-8").strip())
        except (ValueError, OSError):
            return None
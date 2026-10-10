"""结果落盘：``out/scores.jsonl``。

三条约定
--------
1. **``note_id`` 是主键**（upsert）—— 重跑不会重复追加，
   也不会因为顺序不同而产生两份。
2. **每行带 ``schema_version`` / ``config_hash`` / ``run_id``** ——
   改了阈值之后跑出来的结果，和旧结果能区分开。
   否则同一份文件里混着两套阈值的判定，却看不出来。
3. **JSONL 而非单个 JSON** —— 40 篇能一次读完，4000 篇也能流式处理；
   写一行就是一次落盘，中断不丢已完成的。
"""

from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator

from ..config.schema import SCHEMA_VERSION
from ..core.errors import DataError

#: 结果文件名
SCORES_NAME = "scores.jsonl"


@dataclass
class RunMeta:
    """一次运行的元信息。进每一行产物。"""

    run_id: str
    config_hash: str
    model: str = ""
    rule_set: str = "default"

    @classmethod
    def create(cls, *, config_hash: str, model: str = "",
               rule_set: str = "default") -> "RunMeta":
        return cls(
            run_id=time.strftime("%Y%m%d-%H%M%S-") + uuid.uuid4().hex[:6],
            config_hash=config_hash,
            model=model,
            rule_set=rule_set,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": SCHEMA_VERSION,
            "run_id": self.run_id,
            "config_hash": self.config_hash,
            "model": self.model,
            "rule_set": self.rule_set,
            "scored_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        }


class ResultStore:
    """``scores.jsonl`` 的读写。"""

    def __init__(self, out_dir: Path, *, meta: RunMeta | None = None) -> None:
        self.out_dir = Path(out_dir)
        self.path = self.out_dir / SCORES_NAME
        self.meta = meta

    # ------------------------------------------------------------------ 读

    def load(self) -> list[dict[str, Any]]:
        """读全部行。**坏行跳过并在 stderr 之外静默** —— 一行坏了
        不该让整个报告出不来；坏行数由 :meth:`load_checked` 提供。"""
        rows, _ = self.load_checked()
        return rows

    def load_checked(self) -> tuple[list[dict[str, Any]], list[str]]:
        """读全部行，同时返回坏行信息。"""
        if not self.path.is_file():
            return [], []
        rows: list[dict[str, Any]] = []
        bad: list[str] = []
        for i, line in enumerate(self.path.read_text(
                encoding="utf-8").splitlines(), 1):
            if not line.strip():
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError as exc:
                bad.append(f"第 {i} 行: {exc}")
        return rows, bad

    def existing_ids(self) -> set[str]:
        return {r["note_id"] for r in self.load() if r.get("note_id")}

    def iter_rows(self) -> Iterator[dict[str, Any]]:
        """流式读（大文件用）。"""
        if not self.path.is_file():
            return
        with self.path.open(encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    try:
                        yield json.loads(line)
                    except json.JSONDecodeError:
                        continue

    # ------------------------------------------------------------------ 写

    def upsert(self, record: dict[str, Any]) -> None:
        """写一行。同 ``note_id`` 覆盖。

        实现：整表读回 → 替换 → 重写。40 篇规模完全够用；
        真要上万条再换 append-only + 归并，那时数据格式不用变。
        """
        nid = record.get("note_id")
        if not nid:
            raise DataError("结果里没有 note_id，无法 upsert")
        rows = [r for r in self.load() if r.get("note_id") != nid]
        rows.append(record)
        self._write_all(rows)

    def upsert_many(self, records: list[dict[str, Any]],
                    *, merge: bool = True) -> int:
        """批量写。``merge=True`` 时与已有行合并（按 ``note_id``）。"""
        if not records:
            return 0
        by_id: dict[str, dict[str, Any]] = {}
        if merge:
            for r in self.load():
                if r.get("note_id"):
                    by_id[r["note_id"]] = r
        for r in records:
            nid = r.get("note_id")
            if not nid:
                raise DataError("结果里没有 note_id，无法 upsert")
            by_id[nid] = r
        self._write_all(list(by_id.values()))
        return len(by_id)

    def append_lines(self, records: list[dict[str, Any]]) -> int:
        """追加写（不读回、不去重）。**逐行 flush** ——
        大批量跑到一半被杀也不丢已完成的。"""
        self.out_dir.mkdir(parents=True, exist_ok=True)
        n = 0
        with self.path.open("a", encoding="utf-8") as f:
            for r in records:
                f.write(json.dumps(r, ensure_ascii=False, default=str) + "\n")
                f.flush()
                n += 1
        return n

    def reset(self) -> None:
        if self.path.is_file():
            self.path.unlink()

    def _write_all(self, rows: list[dict[str, Any]]) -> None:
        self.out_dir.mkdir(parents=True, exist_ok=True)
        # 先写临时文件再原子替换 —— 中途崩了不会留下半个文件
        tmp = self.path.with_suffix(".jsonl.tmp")
        tmp.write_text(
            "\n".join(json.dumps(r, ensure_ascii=False, default=str)
                      for r in rows) + "\n",
            encoding="utf-8")
        tmp.replace(self.path)

    # ------------------------------------------------------------------ 统计

    def summary(self) -> dict[str, Any]:
        rows = self.load()
        counts: dict[str, int] = {}
        for r in rows:
            lv = r.get("level", "?")
            counts[lv] = counts.get(lv, 0) + 1
        runs = {r.get("run_id") for r in rows if r.get("run_id")}
        hashes = {r.get("config_hash") for r in rows if r.get("config_hash")}
        return {
            "path": str(self.path),
            "total": len(rows),
            "level_counts": counts,
            "runs": len(runs),
            "config_hashes": sorted(hashes),
            "mixed_runs": len(runs) > 1 or len(hashes) > 1,
        }


__all__ = ["ResultStore", "RunMeta", "SCORES_NAME"]

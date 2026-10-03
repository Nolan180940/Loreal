"""断点续抓状态。

匿名场景下每篇笔记会做多次请求，任何中断都可能丢数据。这里用「每步落盘」
的方式保证：重跑时从上次成功的步骤继续，而不是从头再来。

约定
----
- ``content``  完成即写 ``note.json``（幂等，重跑直接跳过）
- ``images``  逐张下载，已存在且非空则跳过
- ``comments`` 写 ``.ckpt/top.json``（含 cursor），成功后清理
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class Checkpoint:
    """单个笔记的断点文件集合。"""

    def __init__(self, ckpt_dir: Path) -> None:
        self.dir = Path(ckpt_dir)

    # ---------- 通用 ----------
    def _path(self, name: str) -> Path:
        return self.dir / f"{name}.json"

    def load(self, name: str) -> dict[str, Any]:
        p = self._path(name)
        if not p.is_file():
            return {}
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            return {}

    def save(self, name: str, payload: dict[str, Any]) -> None:
        self.dir.mkdir(parents=True, exist_ok=True)
        self._path(name).write_text(
            json.dumps(payload, ensure_ascii=False), encoding="utf-8"
        )

    def clear(self) -> None:
        if not self.dir.is_dir():
            return
        for f in self.dir.glob("*.json"):
            try:
                f.unlink()
            except OSError:
                pass
        try:
            self.dir.rmdir()
        except OSError:
            pass

    # ---------- 语义化封装 ----------
    def save_note_step(self, step: str, payload: dict) -> None:
        self.save(f"step_{step}", payload)

    def done_steps(self) -> set[str]:
        out = set()
        if not self.dir.is_dir():
            return out
        for f in self.dir.glob("step_*.json"):
            out.add(f.stem[len("step_"):])
        return out

    def save_comment_page(
        self, note_id: str, comments: list[dict], cursor: str, has_more: bool
    ) -> None:
        """一级评论每翻一页就落盘一次（含 cursor），中断可续。"""
        self.save(
            "top",
            {
                "note_id": note_id,
                "comments": comments,
                "cursor": cursor,
                "has_more": has_more,
            },
        )

    def load_comment_page(self, note_id: str) -> dict:
        st = self.load("top")
        if st.get("note_id") != note_id:
            return {}
        return st
"""存储布局：``data/<note_id>/{content,images,comments}``。

与既有采集产物保持一致，便于直接喂给下游特征工程。

目录约定::

    data/<note_id>/
        content/note.json      结构化正文（标题/正文/互动数/作者/标签）
        content/note.md        人读版
        images/urls.json       图片 URL 清单（按原顺序）
        images/01.jpg ...      下载后的图片，序号与 urls.json 对齐
        comments/comments.json 扁平列表：一级 + 楼中楼（带 _is_reply）
        comments/card.json     统计与对齐校验结果
        comments/.ckpt/        断点文件（成功后清理）
"""

from __future__ import annotations

import json
import re
from pathlib import Path

NOTE_ID_RE = re.compile(r"^[0-9a-f]{24}$")
IMAGE_EXTS = (".jpg", ".jpeg", ".png", ".webp", ".heic", ".avif")


class NoteLayout:
    """单篇笔记的落盘布局。"""

    def __init__(self, root: Path, note_id: str) -> None:
        self.note_id = note_id
        self.root = Path(root) / note_id
        self.content = self.root / "content"
        self.images = self.root / "images"
        self.comments = self.root / "comments"
        self.ckpt = self.comments / ".ckpt"

    def ensure(self) -> "NoteLayout":
        for d in (self.content, self.images, self.comments):
            d.mkdir(parents=True, exist_ok=True)
        return self

    # ---------- content ----------
    def write_note(self, note: dict) -> None:
        self.ensure()
        (self.content / "note.json").write_text(
            json.dumps(note, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        md = [
            f"# {note.get('title', '')}",
            "",
            f"作者：{note.get('author', '')}",
            f"发布：{note.get('time', '')}",
            "互动："
            f"赞{note.get('liked', '')} 藏{note.get('collected', '')} "
            f"评{note.get('comment_count', '')} 享{note.get('share', '')}",
            "",
            "## 正文",
            str(note.get("desc", "")),
            "",
            "## 标签",
            " ".join(note.get("tags", []) or []),
            "",
        ]
        (self.content / "note.md").write_text("\n".join(md), encoding="utf-8")

    def read_note(self) -> dict:
        p = self.content / "note.json"
        if not p.is_file():
            return {}
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            return {}

    # ---------- images ----------
    def write_image_urls(self, urls: list[str]) -> None:
        self.ensure()
        (self.images / "urls.json").write_text(
            json.dumps(list(urls), ensure_ascii=False, indent=2), encoding="utf-8"
        )

    def read_image_urls(self) -> list[str]:
        p = self.images / "urls.json"
        if not p.is_file():
            return []
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            return list(data) if isinstance(data, list) else []
        except Exception:
            return []

    def image_files(self) -> list[Path]:
        if not self.images.is_dir():
            return []
        return sorted(
            f for f in self.images.iterdir()
            if f.is_file() and f.suffix.lower() in IMAGE_EXTS
        )

    # ---------- comments ----------
    def write_comments(
        self, comments: list[dict], card: dict, replies: list[dict] | None = None
    ) -> None:
        self.ensure()
        flat = list(comments) + list(replies or [])
        (self.comments / "comments.json").write_text(
            json.dumps(flat, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        (self.comments / "card.json").write_text(
            json.dumps(card, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    def read_card(self) -> dict:
        p = self.comments / "card.json"
        if not p.is_file():
            return {}
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            return {}

    def has_comments(self) -> bool:
        return (self.comments / "card.json").is_file()

    # ---------- 断点 ----------
    def clear_ckpt(self) -> None:
        if not self.ckpt.is_dir():
            return
        for f in self.ckpt.glob("*.json"):
            try:
                f.unlink()
            except OSError:
                pass
        try:
            self.ckpt.rmdir()
        except OSError:
            pass


def scan_notes(root: Path) -> list[str]:
    """列出已有完整 ``card.json`` 的 note_id。"""
    root = Path(root)
    if not root.is_dir():
        return []
    out = []
    for d in root.iterdir():
        if d.is_dir() and NOTE_ID_RE.match(d.name):
            if (d / "comments" / "card.json").is_file():
                out.append(d.name)
    return sorted(out)
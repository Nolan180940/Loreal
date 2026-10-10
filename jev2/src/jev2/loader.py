"""``notes.json`` → :class:`NoteRecord`。

**这是全系统唯一认识数据结构的地方。**
将来 ``notes.json`` 结构变了、或要接旧目录（``content/note.json``），
只改这个文件，上层一行不动。

数据现实（2026-10-11 实测 40 篇）
--------------------------------
- ``note.*`` 的计数是**字符串**：``"7546"``；平台不公开时是 ``""``
- ``time_ms`` 是毫秒时间戳，字符串
- 评论 ``time`` 是毫秒整数；``like_count`` 是字符串
- 评论列表是**扁平的**：一级 + 楼中楼混在一起，靠 ``_is_reply`` 区分
- ``is_author`` **恒为 False**（SSR 不给），所以这里用
  「评论者昵称 == 作者昵称」兜底推导
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Iterator

from .core.errors import DataError
from .core.types import CommentRow, NoteRecord

HEX24 = re.compile(r"^[0-9a-f]{24}$")

#: 计数字段：可能出现的非数字形态，统一视为「平台未公开」
_UNKNOWN_COUNTS = {"", "-", "-1", "0.0"}


def parse_count(v: Any) -> int:
    """把各种形态的计数转成 int。

    处理过的形态（全来自真实数据）::

        "7546"    → 7546
        "1.2万"    → 12000
        "1千+"     → 1000      （评论 like_count 会出现）
        1234      → 1234
        "" / "-1" → 0          （平台不公开）

    **不抛异常**：计数缺失是常态，不是错误。
    """
    if v is None:
        return 0
    if isinstance(v, bool):
        return int(v)
    if isinstance(v, (int, float)):
        return max(int(v), 0)

    s = str(v).strip().replace(",", "")
    if not s or s in _UNKNOWN_COUNTS:
        return 0

    # ⚠️ 必须先去掉尾部的 ``+``：
    #    "1千+" 以 ``+`` 结尾，所以 ``s.endswith("千")`` 是 False ——
    #    不先脱衣就会掉进 int("1千+") 的 ValueError，返回 0。
    #    而 ``1千+`` 是评论 like_count 的真实形态。
    s = s.rstrip("+").strip()
    if not s:
        return 0

    mult = 1
    if s.endswith("万"):
        mult, s = 10_000, s[:-1]
    elif s.endswith(("w", "W")):
        mult, s = 10_000, s[:-1]
    elif s.endswith(("千", "k", "K")):
        mult, s = 1_000, s[:-1]
    s = s.strip()

    try:
        return max(int(float(s) * mult), 0)
    except ValueError:
        return 0


def _int(v: Any, default: int = 0) -> int:
    try:
        return int(v)
    except (TypeError, ValueError):
        return default


def comment_key(raw: dict[str, Any]) -> str:
    """评论的唯一标识。

    **新结构里没有评论 ``id``**（实测 498/498 行都只有 ``user_id``）——
    xhs-cli 的扁平化输出丢了它。所以这里分层取：

    1. 有 ``id`` 就用（将来数据源补上这个字段时自动生效）
    2. 否则用 ``user_id|time|content[:20]``

    第 2 种的唯一性实测过：498 行里 0 组重复。
    取 content 前 20 字是为了避免超长文本参与比较；
    真正的重复评论（同人同时同文）本来也该视为同一条。
    """
    cid = str(raw.get("id") or "").strip()
    if cid:
        return cid
    uid = str(raw.get("user_id") or "").strip()
    t = _int(raw.get("time"))
    head = str(raw.get("content") or "").strip()[:20]
    return f"{uid}|{t}|{head}"


def _comment_row(raw: dict[str, Any], *,
                 author: str) -> CommentRow | None:
    """一行评论。没有正文的丢掉（无内容可判）。"""
    content = str(raw.get("content") or "").strip()
    if not content:
        return None

    # 昵称有两个来源：新结构在顶层，旧结构在 user_info 里
    ui = raw.get("user_info") if isinstance(raw.get("user_info"), dict) else {}
    nickname = str(raw.get("nickname") or ui.get("nickname")
                   or ui.get("nick_name") or "").strip()

    # ⚠️ SSR 的 is_author 恒 False，所以两个来源取或：
    #    ① 字段本身（将来数据源修好了就能直接用）
    #    ② 昵称与作者相同（实测 26/40 篇能这样推出作者自评）
    is_author = bool(raw.get("is_author")) or (
        bool(author) and nickname == author
    )

    return CommentRow(
        cid=comment_key(raw),
        content=content,
        nickname=nickname,
        ip_location=str(raw.get("ip_location") or "").strip(),
        like_count=str(raw.get("like_count") or "0"),
        time_ms=_int(raw.get("time")),
        is_author=is_author,
        is_reply=bool(raw.get("_is_reply")),
        parent_id=str(raw.get("_parent_id") or ""),
    )


def load_note(path: Path) -> NoteRecord:
    """读一篇 ``notes.json``。

    Raises
    ------
    DataError
        文件缺失、不是合法 JSON、或缺 ``note_id``。
    """
    path = Path(path)
    if not path.is_file():
        raise DataError(f"找不到 {path}")
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError, OSError) as exc:
        raise DataError(f"{path} 读取失败: {exc}") from exc
    if not isinstance(raw, dict):
        raise DataError(f"{path} 顶层不是对象")

    note = raw.get("note") if isinstance(raw.get("note"), dict) else raw
    nid = str(raw.get("note_id") or note.get("note_id") or "").strip()
    if not nid:
        raise DataError(f"{path} 里没有 note_id")

    author = str(note.get("author") or "").strip()

    comments: list[CommentRow] = []
    seen_cids: set[str] = set()
    for c in raw.get("comments") or []:
        if not isinstance(c, dict):
            continue
        row = _comment_row(c, author=author)
        if row is None or row.cid in seen_cids:
            continue
        seen_cids.add(row.cid)
        comments.append(row)

    tags: list[str] = []
    for t in note.get("tags") or []:
        s = str(t).strip()
        # 去重 + 剔除假标签（见 docs：SSR 的 tagList 存两份，且混入界面文案「笔记」）
        if s and s != "笔记" and s not in tags:
            tags.append(s)

    images = tuple(str(u) for u in (note.get("images") or []) if u)

    # 记录「平台未公开」的计数 —— 值缺失 ≠ 值为 0
    raw_counts = {
        k: note.get(k)
        for k in ("liked", "collected", "comment_count",
                  "comment_count_l1", "share")
        if note.get(k) in (None, "") or str(note.get(k)) in _UNKNOWN_COUNTS
    }

    return NoteRecord(
        note_id=nid,
        title=str(note.get("title") or "").strip(),
        desc=str(note.get("desc") or "").strip(),
        tags=tuple(tags),
        author=author,
        author_id=str(note.get("author_id") or "").strip(),
        liked=parse_count(note.get("liked")),
        collected=parse_count(note.get("collected")),
        comment_count=parse_count(note.get("comment_count")),
        comment_count_l1=parse_count(note.get("comment_count_l1")),
        share=parse_count(note.get("share")),
        published_ms=parse_count(note.get("time_ms")),
        ip_location=str(note.get("ip_location") or "").strip(),
        images=images,
        comments=tuple(comments),
        raw_counts=raw_counts,
        source_path=path,
    )


def iter_note_paths(data_root: Path) -> Iterator[Path]:
    """列出 ``<data_root>/<24位hex>/notes.json``。

    只认 24 位 hex 目录 —— 数据目录里还混着 ``.backup`` / ``search`` /
    ``<uuid>#<ts>`` 这类搜索结果空壳（后者 note_id 带 ``#``，不是真笔记）。
    """
    root = Path(data_root)
    if not root.is_dir():
        return
    for d in sorted(root.iterdir()):
        if not (d.is_dir() and HEX24.match(d.name)):
            continue
        p = d / "notes.json"
        if p.is_file():
            yield p


def load_all(data_root: Path, *,
             on_error: str = "skip") -> tuple[list[NoteRecord], list[tuple[Path, str]]]:
    """批量读取。

    Returns
    -------
    (成功列表, [(失败路径, 原因)])

    ``on_error="skip"`` 时坏数据不中断批处理 —— 40 篇里坏 1 篇不该让
    整个报告出不来。错误一并返回，报告里能如实展示。
    """
    ok: list[NoteRecord] = []
    bad: list[tuple[Path, str]] = []
    for p in iter_note_paths(data_root):
        try:
            ok.append(load_note(p))
        except DataError as exc:
            if on_error == "raise":
                raise
            bad.append((p, str(exc)))
    return ok, bad


__all__ = ["load_note", "load_all", "iter_note_paths",
           "parse_count", "comment_key", "HEX24"]

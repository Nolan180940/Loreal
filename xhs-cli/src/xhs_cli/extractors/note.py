"""正文/互动数归一化：把 :class:`xhs_cli.page.PageData` 转成落盘结构。"""

from __future__ import annotations

import time
from typing import Any

from ..page import PageData


def to_note_dict(page: PageData) -> dict[str, Any]:
    """转成 ``content/note.json`` 的结构。"""
    published = ""
    if page.time_ms:
        published = time.strftime("%Y-%m-%d %H:%M:%S",
                                  time.localtime(page.time_ms / 1000))
    return {
        "note_id": page.note_id,
        "title": page.title,
        "desc": page.desc,
        "tags": page.tags,
        "author": page.author,
        "author_id": page.author_id,
        "published": published,
        "time_ms": page.time_ms,
        "ip_location": page.ip_location,
        "liked": page.liked,
        "collected": page.collected,
        "comment_count": page.comment_count,
        "share_count": page.share_count,
        "image_count": len(page.images),
        "images": page.images,
        "source": "share_page_ssr",
    }
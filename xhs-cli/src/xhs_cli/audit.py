"""完整性审计。

原则：**不美化数据**。抓不到就说抓不到，而不是让报告看起来完整。

三类校验
--------
1. content：标题/正文是否存在（允许为空，但要显式记录）
2. images：声明数 vs 实得数，损坏文件单独报
3. comments：一级 + 内联楼中楼 vs 平台显示的评论数，缺口如实标注
"""

from __future__ import annotations

import json
from pathlib import Path

from .storage.layout import IMAGE_EXTS, NoteLayout


def audit_note(root: Path, note_id: str) -> dict:
    """审计单篇笔记。"""
    lay = NoteLayout(root, note_id)
    issues: list[str] = []

    note = lay.read_note()
    if not note:
        issues.append("缺 content/note.json")
        desc_len = 0
    else:
        desc_len = len(str(note.get("desc") or ""))

    declared = 0
    try:
        declared = int(note.get("image_count") or 0)
    except (TypeError, ValueError):
        declared = 0

    files = lay.image_files()
    broken = []
    for f in files:
        if f.stat().st_size == 0:
            broken.append(f.name)
    if broken:
        issues.append(f"图片损坏: {','.join(broken)}")
    if declared and len(files) < declared:
        issues.append(f"图片缺 {declared - len(files)} 张")
    if declared and not (lay.read_image_urls() or []):
        issues.append("缺 images/urls.json")

    card = lay.read_card()
    if not card:
        issues.append("缺 comments/card.json")
        cmt_total = 0
        expect = 0
        partial = False
    else:
        cmt_total = int(card.get("total") or 0)
        expect = int(card.get("note_reported") or 0)
        partial = bool(card.get("partial"))
        if expect > 0 and cmt_total > expect:
            issues.append(f"评论超出平台计数 {cmt_total}>{expect}")

    return {
        "note_id": note_id,
        "desc_len": desc_len,
        "images_declared": declared,
        "images_on_disk": len(files),
        "comments": cmt_total,
        "comments_expected": expect,
        "comments_partial": partial,
        "ok": not issues,
        "issues": issues,
    }


def audit_all(root: Path) -> list[dict]:
    """审计 ``root`` 下所有笔记目录。"""
    root = Path(root)
    if not root.is_dir():
        return []
    rows = []
    for d in sorted(root.iterdir()):
        if not d.is_dir() or len(d.name) != 24:
            continue
        rows.append(audit_note(root, d.name))
    return rows


def print_report(root: Path) -> int:
    """打印审计报告，返回不达标数量。"""
    rows = audit_all(root)
    if not rows:
        print(f"[!] {root} 下没有笔记目录")
        return 0

    header = (f"{'note_id':<26}{'正文':>6}{'图(声明/实得)':>16}"
              f"{'评论':>8}{'期望':>8}  问题")
    print(header)
    print("-" * len(header))

    bad = 0
    for r in rows:
        if not r["ok"]:
            bad += 1
        img = f"{r['images_declared']}/{r['images_on_disk']}"
        print(f"{r['note_id']:<26}{r['desc_len']:>6}{img:>16}"
              f"{r['comments']:>8}{r['comments_expected']:>8}  "
              f"{'; '.join(r['issues']) or '-'}")

    print("-" * len(header))
    total_cmt = sum(r["comments"] for r in rows)
    partial = sum(1 for r in rows if r["comments_partial"])
    print(f"共 {len(rows)} 篇，不达标 {bad} 篇")
    print(f"评论合计 {total_cmt} 条"
          f"（其中 {partial} 篇为首批数据，评论总数未取全）")
    return bad
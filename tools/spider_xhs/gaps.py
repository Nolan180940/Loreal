"""精确缺口核对（v2）。

v1 的 `xhs_cli.audit` 只认英文字段（desc/liked/...），而 `data/` 里的实际产物
是 Spider_XHS 的中文 schema（作品描述/点赞数量/...），导致审计把好数据误报成 0。

本脚本同时兼容两套 schema，按三个维度给出**逐篇**缺口：
    1. 文案   正文是否非空
    2. 图片   声明数（urls.json / 下载地址）vs 实得文件数
    3. 评论   实得条数 vs 平台计数（评论数量），并标注是否首批数据

用法:
    python tools/spider_xhs/gaps.py
    python tools/spider_xhs/gaps.py --root data --json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

IMAGE_EXTS = (".jpg", ".jpeg", ".png", ".webp", ".heic", ".avif")
NOTE_ID_LEN = 24

# 中文 key -> 英文 key
NOTE_ALIASES = {
    "title": ("作品标题", "title"),
    "desc": ("作品描述", "desc"),
    "author": ("作者昵称", "author"),
    "liked": ("点赞数量", "liked"),
    "collected": ("收藏数量", "collected"),
    "comment_count": ("评论数量", "comment_count"),
    "share_count": ("分享数量", "share_count", "share"),
    "image_urls": ("下载地址", "images"),
}


def pick(note: dict, key: str, default=None):
    """按 alias 顺序取第一个存在且非 None 的值。"""
    for k in NOTE_ALIASES.get(key, (key,)):
        if k in note and note[k] is not None:
            return note[k]
    return default


def as_int(v, default: int = 0) -> int:
    try:
        n = int(str(v).strip())
    except (TypeError, ValueError):
        return default
    return max(n, 0)


def load_json(path: Path):
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return None


def inspect_note(root: Path, note_id: str) -> dict:
    d = root / note_id
    note = load_json(d / "content" / "note.json") or {}
    card = load_json(d / "comments" / "card.json") or {}
    comments = load_json(d / "comments" / "comments.json")
    urls = load_json(d / "images" / "urls.json")

    # --- 文案 ---
    desc = str(pick(note, "desc", "") or "")
    title = str(pick(note, "title", "") or "")
    has_content = bool(desc.strip() or title.strip())

    # --- 图片 ---
    if urls is None:
        urls = pick(note, "image_urls", []) or []
    if isinstance(urls, str):
        urls = [urls]
    declared = len([u for u in urls if u])
    files = [
        f
        for f in (d / "images").glob("*")
        if f.is_file() and f.suffix.lower() in IMAGE_EXTS and f.stat().st_size > 0
    ]
    zero_byte = [
        f.name
        for f in (d / "images").glob("*")
        if f.is_file() and f.suffix.lower() in IMAGE_EXTS and f.stat().st_size == 0
    ]
    has_images = bool(files)

    # --- 评论 ---
    if isinstance(comments, list):
        got = len(comments)
        has_comments = got > 0
    elif isinstance(comments, dict):
        got = as_int(comments.get("total"), 0)
        has_comments = got > 0
    else:
        got = 0
        has_comments = False

    reported = as_int(pick(note, "comment_count"), as_int(card.get("note_reported"), 0))

    issues = []
    if not has_content:
        issues.append("缺文案")
    if zero_byte:
        issues.append(f"图片损坏x{len(zero_byte)}")
    if declared and len(files) < declared:
        issues.append(f"图缺{declared - len(files)}")
    if not has_comments:
        issues.append("缺评论")
    elif reported > 0 and got < reported:
        issues.append(f"评论{got}/{reported}")

    return {
        "note_id": note_id,
        "has_content": has_content,
        "desc_len": len(desc),
        "title_len": len(title),
        "has_images": has_images,
        "images_declared": declared,
        "images_on_disk": len(files),
        "has_comments": has_comments,
        "comments": got,
        "comments_reported": reported,
        "partial": bool(card.get("partial")) or (0 < reported and got < reported),
        "issues": issues,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default="data")
    ap.add_argument("--json", action="store_true", help="输出 JSON")
    ap.add_argument("--only-gaps", action="store_true", help="只看有缺口的")
    args = ap.parse_args()

    root = Path(args.root).resolve()
    if not root.is_dir():
        print(f"[!] 目录不存在: {root}")
        return 2

    rows = [
        inspect_note(root, p.name)
        for p in sorted(root.iterdir())
        if p.is_dir() and len(p.name) == NOTE_ID_LEN
    ]
    if not rows:
        print(f"[!] {root} 下没有笔记目录")
        return 2

    if args.json:
        print(json.dumps(rows, ensure_ascii=False, indent=2))
        return 0

    if not args.only_gaps:
        print(f"{'note_id':<26}{'正文':>6}{'图':>10}{'评论':>12}  问题")
        print("-" * 84)
        for r in rows:
            img = f"{r['images_on_disk']}/{r['images_declared']}" if r["images_declared"] else str(r["images_on_disk"])
            cmt = f"{r['comments']}/{r['comments_reported']}" if r["comments_reported"] else str(r["comments"])
            desc = str(r["desc_len"]) if r["has_content"] else "-"
            print(f"{r['note_id']:<26}{desc:>6}{img:>10}{cmt:>12}  {'; '.join(r['issues'])}")

    total = len(rows)
    c_ok = sum(r["has_content"] for r in rows)
    i_ok = sum(r["has_images"] for r in rows)
    m_ok = sum(r["has_comments"] for r in rows)
    print("=" * 84)
    print(f"共 {total} 篇")
    print(f"  文案 {c_ok}/{total}   缺 {total - c_ok}")
    print(f"  图片 {i_ok}/{total}   缺 {total - i_ok}")
    print(f"  评论 {m_ok}/{total}   缺 {total - m_ok}")
    print(
        f"  评论合计 {sum(r['comments'] for r in rows)} 条 · "
        f"图片合计 {sum(r['images_on_disk'] for r in rows)} 张"
    )
    full = [r for r in rows if not r["issues"]]
    print(f"  三项全齐 {len(full)}/{total}")

    gaps = [r for r in rows if r["issues"]]
    if gaps:
        print("\n缺口明细:")
        for r in gaps:
            print(f"  {r['note_id']}  {'; '.join(r['issues'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
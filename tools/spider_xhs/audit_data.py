# -*- coding: utf-8 -*-
"""数据完整性审计：逐篇核对 content / images / comments 是否齐全且对齐。

用法（tools\\.venv）：
    .\\.venv\\Scripts\\python.exe audit_data.py            # 全量审计
    .\\.venv\\Scripts\\python.exe audit_data.py --fix-list # 只列出待重抓的 note_id

判定口径
--------
- note_reported > 0  →  平台给出了评论数，必须 total == note_reported
- note_reported <= 0 →  HTML 解析出 -1，属「未知」，不算缺失
- 差值 > 0 一律标为 incomplete，并给出可复制的重抓命令
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
DATA = ROOT / "data"
IMG_EXT = (".jpg", ".jpeg", ".png", ".webp", ".heic", ".avif")


def _load(p: Path):
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None


def audit_one(nid: str) -> dict:
    base = DATA / nid
    row = {"note_id": nid, "ok": True, "issues": [],
           "title_len": 0, "images": 0, "comments": 0, "reported": 0,
           "imgs_declared": 0}

    note = _load(base / "content" / "note.json")
    if not note:
        row["ok"] = False
        row["issues"].append("缺 content/note.json")
        return row
    row["title_len"] = len(str(note.get("作品描述", "")))
    if row["title_len"] == 0:
        row["issues"].append("正文为空")

    urls = _load(base / "images" / "urls.json")
    row["imgs_declared"] = len(urls) if isinstance(urls, list) else 0
    img_dir = base / "images"
    if img_dir.is_dir():
        row["images"] = sum(1 for f in img_dir.iterdir()
                            if f.suffix.lower() in IMG_EXT)
    if row["imgs_declared"] and row["images"] < row["imgs_declared"]:
        row["issues"].append(
            f"图片缺 {row['imgs_declared'] - row['images']} 张")
    if (base / "Download").is_dir():
        row["issues"].append("残留 Download/ 未归位")

    card = _load(base / "comments" / "card.json")
    if not card:
        row["ok"] = False
        row["issues"].append("缺 comments/card.json")
        return row
    row["comments"] = int(card.get("total", 0))
    row["reported"] = int(card.get("note_reported", 0))
    if row["reported"] > 0 and not card.get("matched"):
        row["ok"] = False
        row["issues"].append(f"评论差 {card.get('diff')} 条")
    if card.get("thread_gaps"):
        row["ok"] = False
        row["issues"].append(f"{len(card['thread_gaps'])} 个楼未取全")
    if (base / "comments" / "comments.json").is_file() is False:
        row["ok"] = False
        row["issues"].append("缺 comments.json")
    return row


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--fix-list", action="store_true", help="只输出待重抓的 id")
    args = ap.parse_args()
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

    nids = sorted(p.name for p in DATA.iterdir()
                  if p.is_dir() and len(p.name) == 24)
    rows = [audit_one(n) for n in nids]
    bad = [r for r in rows if not r["ok"]]

    if args.fix_list:
        for r in bad:
            print(r["note_id"])
        return 0

    print(f"{'note_id':<14}{'正文':>6}{'图':>5}{'评论':>7}{'期望':>7}  问题")
    print("-" * 74)
    for r in rows:
        print(f"{r['note_id']:<14}{r['title_len']:>6}{r['images']:>5}"
              f"{r['comments']:>7}{r['reported']:>7}  "
              f"{'; '.join(r['issues']) or '-'}")
    print("-" * 74)
    print(f"共 {len(rows)} 篇，完好 {len(rows) - len(bad)}，有问题 {len(bad)}")
    tot_img = sum(r["images"] for r in rows)
    tot_cmt = sum(r["comments"] for r in rows)
    print(f"图片合计 {tot_img} 张，评论合计 {tot_cmt} 条")
    if bad:
        print("\n重抓命令：")
        print("  .\\.venv\\Scripts\\python.exe batch_fetch.py --resume")
        print("（batch_fetch.py 见到 card.json 即跳过，故需先删对应 card.json）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

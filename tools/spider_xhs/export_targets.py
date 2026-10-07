"""导出待补抓的笔记清单（note_id + 旧链接），供浏览器重新取 token 用。

用法:
    python tools/spider_xhs/export_targets.py --root data --out .session/targets.txt
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
sys.stdout.reconfigure(encoding="utf-8")

from gaps import inspect_note  # noqa: E402

# note_id -> 原始链接（来自 note.json 的"作品链接"）
def load_links(root: Path) -> dict[str, str]:
    links: dict[str, str] = {}
    for p in root.glob("*/content/note.json"):
        try:
            n = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            continue
        nid = n.get("作品ID") or n.get("note_id") or p.parent.parent.name
        url = n.get("作品链接") or ""
        if nid and url:
            links[nid] = url
    return links


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default="data")
    ap.add_argument("--out", default=".session/targets.txt")
    ap.add_argument("--only", choices=["all", "content", "comments", "images"], default="all")
    args = ap.parse_args()

    root = Path(args.root).resolve()
    links = load_links(root)

    rows = [
        inspect_note(root, p.name)
        for p in sorted(root.iterdir())
        if p.is_dir() and len(p.name) == 24
    ]

    def need(r: dict) -> bool:
        if args.only == "content":
            return not r["has_content"]
        if args.only == "comments":
            return not r["has_comments"] or r["issues"]
        if args.only == "images":
            return r["images_declared"] > r["images_on_disk"]
        return bool(r["issues"])

    todo = [r for r in rows if need(r)]
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)

    with out.open("w", encoding="utf-8") as f:
        f.write("# note_id\t问题\t旧链接(带过期token)\n")
        for r in todo:
            url = links.get(r["note_id"], "")
            f.write(f"{r['note_id']}\t{'; '.join(r['issues'])}\t{url}\n")

    print(f"待抓 {len(todo)}/{len(rows)} 篇 -> {out}")
    for r in todo:
        print(f"  {r['note_id']}  {'; '.join(r['issues'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
# -*- coding: utf-8 -*-
"""校验回填结果：格式合法性 + 下游可读性 + 是否丢数据。

用下游 ``jev_guard.reader`` 自己的读法来验，才说明真的修好了。
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "jev" / "src"))
sys.path.insert(0, str(ROOT / "xhs-cli" / "src"))

from jev_guard.extractors.reader import load_comments, load_note  # noqa: E402

DATA = ROOT / "data"
NOTE_RE = re.compile(r"/(?:explore|discovery/item)/([0-9a-f]{24})")

ids = [m.group(1) for m in
       (NOTE_RE.search(l) for l in
        (ROOT / "urls.txt").read_text(encoding="utf-8").splitlines()) if m]

REQUIRED = ("id", "content", "user_info")

print(f"{'note':<10}{'note?':<7}{'评论':<6}{'作者有名':<10}{'缺id':<7}"
      f"{'缺content':<11}{'有card':<8}{'有txt':<7}{'图':<5}")
print("-" * 82)

tot_c = tot_named = 0
issues: list[str] = []

for nid in ids:
    d = DATA / nid
    n = load_note(DATA, nid)
    cs = load_comments(DATA, nid)
    arr = []
    p = d / "comments" / "comments.json"
    if p.is_file():
        try:
            arr = json.loads(p.read_text(encoding="utf-8"))
            arr = arr if isinstance(arr, list) else []
        except Exception:  # noqa: BLE001
            issues.append(f"{nid[:8]} comments.json 不是合法 JSON")

    named = sum(1 for c in cs if c.author)
    no_id = sum(1 for r in arr if not str(r.get("id") or "").strip())
    no_text = sum(1 for r in arr if not str(r.get("content") or "").strip())
    imgs = len(list((d / "images").glob("*.jpeg"))) if (d / "images").is_dir() else 0
    has_card = (d / "comments" / "card.json").is_file()
    has_txt = (d / "comments" / "comments.txt").is_file()

    tot_c += len(cs)
    tot_named += named
    if no_id:
        issues.append(f"{nid[:8]} 有 {no_id} 行缺 id（下游会整行丢掉）")
    if no_text:
        issues.append(f"{nid[:8]} 有 {no_text} 行缺 content")

    print(f"{nid[:8]:<10}{'Y' if n else 'N':<7}{len(cs):<6}{named:<10}"
          f"{no_id:<7}{no_text:<11}{'Y' if has_card else 'N':<8}"
          f"{'Y' if has_txt else 'N':<7}{imgs:<5}")

print(f"\n42 帖下游可读评论 {tot_c} 条，其中有作者名 {tot_named} "
      f"({tot_named / max(tot_c, 1):.0%})")
if issues:
    print("\n问题：")
    for s in issues:
        print(f"  - {s}")
else:
    print("无问题")

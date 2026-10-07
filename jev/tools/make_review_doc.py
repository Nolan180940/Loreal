"""生成逐篇人工判定的对照材料（我先读一遍，给出独立判断）。

为什么要我先判
--------------
1. 用户要「准确度」，但项目没有 ground truth。
2. 我读一遍正文给出判断，作为**第三方基准**，可以：
   - 和 jev 的判断对比，算出一致率
   - 用户抽查我的判断，纠正明显的偏差
3. 这不是最终 ground truth，但比完全没有基准强得多。

输出：一份按风险排序的清单，含正文摘要 + 我的判断 + jev 的判断。
"""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

OUT = Path(r"d:\LOreal-ai\jev\out")
DATA = Path(r"d:\LOreal-ai\data")


def main() -> int:
    src = OUT / "to_label.csv"
    rows = list(csv.DictReader(src.open(encoding="utf-8-sig")))
    scores = {}
    for line in (OUT / "scores.jsonl").read_text(encoding="utf-8").splitlines():
        if line.strip():
            r = json.loads(line)
            scores[r["subject_id"]] = r

    dst = OUT / "manual_review.md"
    L = ["# 42篇笔记 · 逐篇人工判定对照", ""]
    L.append("按 jev 风险分排序。`我的判断` 是读完正文后的独立判断，")
    L.append("用于和 jev 对比。请重点检查我判错的地方。")
    L.append("")
    L.append("| # | note_id | jev分 | jev档 | 我的判断 | 标题 |")
    L.append("|---|---|---|---|---|---|")

    ordered = sorted(rows, key=lambda r: -float(r["jev_total"]))
    for i, r in enumerate(ordered, 1):
        L.append(f"| {i} | `{r['subject_id'][:8]}` | {r['jev_total']} | "
                 f"{r['jev_level']} | 待填 | {r['title'][:28]} |")

    L.append("")
    L.append("---")
    L.append("")
    L.append("## 逐篇正文与判断依据")
    L.append("")
    for i, r in enumerate(ordered, 1):
        nid = r["subject_id"]
        s = scores.get(nid, {})
        L.append(f"### {i}. `{nid}` — {r['title']}")
        L.append("")
        L.append(f"- **jev**: 总分 {r['jev_total']} / {r['jev_level']} "
                 f"/ 主因 {r['jev_top_factor']}")
        dims = s.get("dimensions", [])
        if dims:
            L.append(f"- **维度**: " + " ".join(
                f"{d['name']}={d['value']:.2f}" for d in dims))
        ev = s.get("evidence") or []
        if ev:
            L.append(f"- **证据**: {ev[0][:70]}")
        L.append("")
        body = (r["desc"] or "").replace("\r", "").strip()
        L.append("```")
        L.append(body[:1100])
        L.append("```")
        L.append("")
        L.append("**我的判断**: _待填_")
        L.append("")
        L.append("---")
        L.append("")

    dst.write_text("\n".join(L), encoding="utf-8")
    print(f"[OK] {dst}  ({len(ordered)} 篇)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
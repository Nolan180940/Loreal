"""检查评论采集是否被截断 —— 决定互动信号能不能用。"""

import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from jev_guard.core.config import load_config  # noqa: E402
from jev_guard.extractors.reader import iter_note_ids, load_note  # noqa: E402

cfg = load_config()
lines = []

rows = []
for nid in iter_note_ids(cfg.data_root):
    s = load_note(cfg.data_root, nid)
    if not s:
        continue
    p = cfg.data_root / nid / "comments" / "comments.json"
    try:
        arr = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        arr = []
    rows.append((nid, s.comment_count, len(arr)))

dist = Counter(r[2] for r in rows)
lines.append("## 采集条数分布")
lines.append("")
lines.append("| 实际采集数 | 笔记篇数 |")
lines.append("| ---: | ---: |")
for k, v in sorted(dist.items()):
    mark = "  <== 疑似 API 上限" if k == 10 else ""
    lines.append(f"| {k} | {v}{mark} |")
lines.append("")

lines.append("## 标称评论数 vs 实际采集数")
lines.append("")
lines.append("| note | 标称评论数 | 实际采集 | 缺口 |")
lines.append("| --- | ---: | ---: | ---: |")
for nid, claim, got in sorted(rows, key=lambda x: -x[1]):
    lines.append(f"| `{nid[:8]}` | {claim} | {got} | {claim - got} |")

tot_claim = sum(r[1] for r in rows)
tot_got = sum(r[2] for r in rows)
lines.append("")
lines.append(f"**合计：标称 {tot_claim} 条，实际采集 {tot_got} 条，"
             f"覆盖率 {tot_got / tot_claim * 100:.1f}%**")
lines.append("")
full = sum(1 for r in rows if r[1] <= r[2])
lines.append(f"完整采集（标称 <= 实际）的笔记：**{full}/{len(rows)}** 篇")

Path("out/truncation_check.md").write_text("\n".join(lines), encoding="utf-8")
print("written: out/truncation_check.md")
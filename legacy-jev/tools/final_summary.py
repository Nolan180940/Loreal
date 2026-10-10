"""最终汇总：笔记 + 评论的风险分布与 TOP 榜。

输出到 out/final_summary.md（UTF-8）。
"""

import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from jev_guard.extractors.reader import iter_all_subjects  # noqa: E402
from jev_guard.core.config import load_config  # noqa: E402

CFG = load_config()
TEXT_INDEX = {s.subject_id: s.text for s in iter_all_subjects(CFG.data_root)}

LINES: list[str] = []


def emit(line: str = "") -> None:
    LINES.append(line)


ROWS = [json.loads(l) for l in Path("out/scores.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
notes = [r for r in ROWS if r["kind"] == "note"]
cmts = [r for r in ROWS if r["kind"] == "comment"]

emit(f"笔记 {len(notes)} 条 | 评论 {len(cmts)} 条 | 合计 {len(ROWS)}")
emit()
for title, group in (("笔记", notes), ("评论", cmts)):
    emit(f"## {title}风险分布")
    emit()
    emit("| 等级 | 数量 | 占比 |")
    emit("| --- | ---: | ---: |")
    for lv in ("high", "medium", "low"):
        c = sum(1 for r in group if r["level"] == lv)
        emit(f"| {lv} | {c} | {c / len(group) * 100:.1f}% |")
    emit()

for title, group in (("笔记", notes), ("评论", cmts)):
    emit(f"## {title}风险 TOP 10")
    emit()
    emit("| 总分 | ID | 主因 | 文本 |")
    emit("| ---: | --- | --- | --- |")
    for r in sorted(group, key=lambda x: -x["total"])[:10]:
        txt = TEXT_INDEX.get(r["subject_id"], "").replace("\n", " ").replace("|", "/")[:40]
        emit(f"| {r['total']:.3f} | `{r['subject_id'][:8]}` | {r['top_factor']} | {txt} |")
    emit()

out = Path("out/final_summary.md")
out.write_text("\n".join(LINES), encoding="utf-8")
print(f"written: {out}")
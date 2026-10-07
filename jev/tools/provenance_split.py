"""诊断：哪些笔记的评论带完整指标，哪些不带 —— 找出两套采集路径的边界。"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from jev_guard.core.config import load_config  # noqa: E402
from jev_guard.extractors.reader import iter_note_ids, load_note  # noqa: E402

cfg = load_config()
L: list[str] = []


def emit(s: str = "") -> None:
    L.append(s)


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
    if not arr:
        continue
    n = len(arr)
    has_time = sum(1 for r in arr if r.get("create_time"))
    has_like = sum(1 for r in arr if (r.get("like_count") or r.get("liked")))
    has_ip = sum(1 for r in arr if r.get("ip_location"))
    rows.append((nid, s.comment_count, n, has_time, has_like, has_ip))

A = [r for r in rows if r[3] > 0]      # 带时间
B = [r for r in rows if r[3] == 0]     # 不带时间

emit("## 按「评论是否带 create_time」分组")
emit()
emit(f"- **A 组（有时间戳）**：{len(A)} 篇，评论 {sum(r[2] for r in A)} 条")
emit(f"- **B 组（无时间戳）**：{len(B)} 篇，评论 {sum(r[2] for r in B)} 条")
emit()

emit("### A 组：有时间戳（推测为 xhs-cli 浏览器注入，评论列表完整）")
emit()
emit("| note | 标称 | 采集 | 有time | 有like | 有ip |")
emit("| --- | ---: | ---: | ---: | ---: | ---: |")
for r in sorted(A, key=lambda x: -x[1]):
    emit(f"| `{r[0][:8]}` | {r[1]} | {r[2]} | {r[3]} | {r[4]} | {r[5]} |")
emit()

emit("### B 组：无时间戳（推测为早期 Spider_XHS，API 只返前 10 条且无指标）")
emit()
emit("| note | 标称 | 采集 | 有time | 有like | 有ip |")
emit("| --- | ---: | ---: | ---: | ---: | ---: |")
for r in sorted(B, key=lambda x: -x[1]):
    emit(f"| `{r[0][:8]}` | {r[1]} | {r[2]} | {r[3]} | {r[4]} | {r[5]} |")
emit()

emit("## 结论：能支撑互动分析的样本量")
emit()
usable = [r for r in A if r[4] > 0]
emit(f"- 评论带点赞数的笔记：**{len(usable)}** 篇")
emit(f"- 完整采集（标称<= 采集）的笔记：**{sum(1 for r in A if r[1] <= r[2])}/{len(A)}** 篇")
emit(f"- 评论带时间戳的评论数：**{sum(r[3] for r in A)}**")
emit(f"- 评论带点赞数的评论数：**{sum(r[4] for r in A)}**")

Path("out/provenance_split.md").write_text("\n".join(L), encoding="utf-8")
print("written: out/provenance_split.md")
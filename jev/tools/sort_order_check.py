"""判断评论是按时间排序还是按点赞排序 —— 这决定了"评论均赞=0"是真信号还是采集假象。"""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from jev_guard.core.config import load_config  # noqa: E402
from jev_guard.extractors.reader import iter_note_ids, load_note  # noqa: E402

cfg = load_config()
L: list[str] = []


def ts(v) -> datetime | None:
    try:
        v = int(v)
    except Exception:
        return None
    if v > 1e12:
        v //= 1000
    try:
        return datetime.fromtimestamp(v, tz=timezone.utc)
    except Exception:
        return None


def emit(s: str = "") -> None:
    L.append(s)


TRUNCATED = [nid for nid in iter_note_ids(cfg.data_root)
             if (lambda p: p.is_file() and len(json.loads(p.read_text(encoding="utf-8"))) == 10)(
                 cfg.data_root / nid / "comments" / "comments.json")]

emit(f"## 恰好采到 10 条的笔记：{len(TRUNCATED)} 篇")
emit()
emit("如果这 10 条是「最新评论」，它们的 create_time 应该非常密集（几秒~几分钟内），")
emit("且点赞普遍为 0。如果是「最热评论」，create_time 应该横跨数月且有高赞。")
emit()

emit("| note | 首条时间 | 末条时间 | 时间跨度 | 点赞序列 |")
emit("| --- | --- | --- | --- | --- |")

newest_like = 0
oldest_like = 0
for nid in TRUNCATED[:12]:
    arr = json.loads((cfg.data_root / nid / "comments" / "comments.json").read_text(encoding="utf-8"))
    times = [ts(r.get("create_time")) for r in arr]
    times = [t for t in times if t]
    likes = [r.get("like_count", 0) or r.get("liked", 0) or 0 for r in arr]
    if not times:
        continue
    times.sort()
    span = (times[-1] - times[0]).total_seconds()
    first_iso = times[0].strftime("%Y-%m-%d %H:%M")
    last_iso = times[-1].strftime("%Y-%m-%d %H:%M")
    emit(f"| `{nid[:8]}` | {first_iso} | {last_iso} | {span / 3600:.1f} h | {likes} |")

emit()
emit("## 全部 10 条截断笔记的时间跨度分布")
emit()
spans = []
likes_all = []
for nid in TRUNCATED:
    arr = json.loads((cfg.data_root / nid / "comments" / "comments.json").read_text(encoding="utf-8"))
    times = [ts(r.get("create_time")) for r in arr]
    times = [t for t in times if t]
    likes_all.extend(r.get("like_count", 0) or r.get("liked", 0) or 0 for r in arr)
    if len(times) >= 2:
        times.sort()
        spans.append((times[-1] - times[0]).total_seconds())

if spans:
    import statistics
    emit(f"- 时间跨度中位数：**{statistics.median(spans) / 3600:.1f} 小时**")
    emit(f"- 最短：{min(spans) / 3600:.1f} h · 最长：{max(spans) / 86400:.1f} 天")
    under_1h = sum(1 for s in spans if s <= 3600)
    emit(f"- 跨度 <= 1 小时的笔记：**{under_1h}/{len(spans)}**")
emit()
emit("## 点赞分布（这 10 条截断笔记的全部评论）")
emit()
emit(f"- 评论总数：{len(likes_all)}")
emit(f"- 点赞为 0 的：**{sum(1 for x in likes_all if not x)}** "
     f"({sum(1 for x in likes_all if not x) / len(likes_all) * 100:.1f}%)")
emit(f"- 点赞最大值：{max(likes_all) if likes_all else 0}")

Path("out/sort_order_check.md").write_text("\n".join(L), encoding="utf-8")
print("written: out/sort_order_check.md")
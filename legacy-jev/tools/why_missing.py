"""诊断：评论数据缺失到底是「鉴权失败」还是「取数路径不同」。

判据：
  1. 字段 key 是完全不存在，还是存在但值为空？
     - key 不存在 → 平台没返回 → 可能是鉴权/接口版本
     - key 存在但空 → 拿到了数据但没解析 → 提取逻辑问题
  2. note.json 的source 字段标记了是哪条采集路径产出的
输出 out/why_missing.md
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from jev_guard.core.config import load_config  # noqa: E402
from jev_guard.extractors.reader import iter_note_ids  # noqa: E402

cfg = load_config()
L: list[str] = []


def emit(s: str = "") -> None:
    L.append(s)


CORE = ("create_time", "ip_location", "like_count", "user_info")

rows = []
for nid in iter_note_ids(cfg.data_root):
    np = cfg.data_root / nid / "content" / "note.json"
    cp = cfg.data_root / nid / "comments" / "comments.json"
    if not np.is_file():
        continue
    try:
        n = json.loads(np.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        continue
    if not isinstance(n, dict):
        continue
    try:
        arr = json.loads(cp.read_text(encoding="utf-8")) if cp.is_file() else []
    except Exception:  # noqa: BLE001
        arr = []
    rows.append((nid, n, arr if isinstance(arr, list) else []))

emit("# 评论数据缺失根因诊断")
emit()

# ---- 1. source 标记 ----
emit("## 1. note.json 的 source 标记")
emit()
src = Counter()
src_n = {}
for nid, n, arr in rows:
    s = n.get("source") or "(无source 字段)"
    src[s] += 1
    src_n.setdefault(s, []).append((nid, len(arr)))
for s, c in src.most_common():
    ids = src_n[s]
    n10 = sum(1 for _n, k in ids if k == 10)
    emit(f"- `{s}`：**{c}** 篇，其中 {n10} 篇恰好 10 条评论")
emit()

# ---- 2. 字段 key 存在性 vs 取值 ----
emit("## 2. 核心字段：key 不存在 vs 值为空")
emit()
emit("这是判定的关键 —— 两者含义完全不同。")
emit()
grp: dict[str, list] = {}
for nid, n, arr in rows:
    if not arr:
        continue
    s = n.get("source") or "(无source)"
    grp.setdefault(s, []).append((nid, arr))

emit("| source | 笔记数 | 评论数 | key缺失 | 值为空 | 有真实值 |")
emit("| --- | ---: | ---: | ---: | ---: | ---: |")
for s, items in grp.items():
    miss = empty = real = 0
    tot = 0
    for _nid, arr in items:
        for r in arr:
            if not isinstance(r, dict):
                continue
            tot += 1
            for k in CORE:
                if k not in r:
                    miss += 1
                elif r[k] in (None, "", 0, "0", [], {}):
                    empty += 1
                else:
                    real += 1
    n_notes = len(items)
    emit(f"| `{s}` | {n_notes} | {tot} | {miss} | {empty} | {real} |")
emit()
emit("> 每条评论贡献 4 个字段（4 个核心字段 × 评论数= 总检查数）")
emit()

# ---- 3. 逐 group 抽样 ----
emit("## 3. 抽样对比原始记录")
emit()
for s, items in grp.items():
    nid, arr = items[0]
    emit(f"### source=`{s}` — `{nid[:8]}`（{len(arr)} 条）")
    emit()
    r = arr[0]
    if not isinstance(r, dict):
        continue
    emit("```json")
    emit(json.dumps({k: r[k] for k in sorted(r)}, ensure_ascii=False,
                    indent=2)[:1200])
    emit("```")
    emit()
    for k in CORE:
        if k in r:
            v = r[k]
            mark = "❌ 空" if v in (None, "", 0, "0", [], {}) else "✅ 有值"
            disp = (str(v)[:60] + "...") if len(str(v)) > 60 else str(v)
            emit(f"- `{k}` → {mark} `{disp}`")
        else:
            emit(f"- `{k}` → **key 不存在**")
    emit()

# ---- 4. 结论判据 ----
emit("## 4. 结论")
emit()
for s, items in grp.items():
    miss = empty = real = tot = 0
    for _nid, arr in items:
        for r in arr:
            if not isinstance(r, dict):
                continue
            tot += 1
            for k in CORE:
                if k not in r:
                    miss += 1
                elif r[k] in (None, "", 0, "0", [], {}):
                    empty += 1
                else:
                    real += 1
    total = miss + empty + real
    pct_missing = miss / total * 100 if total else 0
    pct_real = real / total * 100 if total else 0
    emit(f"### `{s}`")
    emit()
    emit(f"- key 缺失率 **{pct_missing:.1f}%**，真实值率 **{pct_real:.1f}%**")
    if pct_missing > 80:
        emit("- → **平台就没返回这些字段**（接口版本/鉴权层级差异）")
    elif pct_real > 80:
        emit("- → **拿到了但没解析出来**（提取逻辑问题，可修）")
    else:
        emit("- → 混合情况")
    emit()

out = ROOT / "out" / "why_missing.md"
out.write_text("\n".join(L), encoding="utf-8")
print(f"written: {out}")
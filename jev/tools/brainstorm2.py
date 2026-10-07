"""brainstorm 实测第二轮：用"作者身份"做独立标签。

上一轮犯了方法论错误 —— 用 jev 分数当真值验证结构信号。
本轮改用两个与 jev 完全无关的独立标签：
  A. 作者身份（官方号/情报官/矩阵号 vs 个人号）
  B. 正文自述（明写「广告/合作/赞助」vs 不写）
看看评论均长等信号是否依然成立。
输出 out/brainstorm2.md
"""

from __future__ import annotations

import json
import re
import statistics
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from jev_guard.core.config import load_config  # noqa: E402
from jev_guard.extractors.reader import (  # noqa: E402
    iter_note_ids, load_comments, load_note, to_int,
)

cfg = load_config()
L: list[str] = []


def emit(s: str = "") -> None:
    L.append(s)


def read_json(p: Path):
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return None


def mean(xs: list[float]) -> float:
    return sum(xs) / len(xs) if xs else 0.0


scores = [json.loads(l) for l in
          (ROOT / "out" / "scores.jsonl").read_text(encoding="utf-8").splitlines()
          if l.strip()]
note_score = {s["subject_id"]: s for s in scores if s["kind"] == "note"}

notes = []
for nid in iter_note_ids(cfg.data_root):
    s = load_note(cfg.data_root, nid)
    if not s:
        continue
    sc = note_score.get(nid)
    if not sc:
        continue
    notes.append({
        "id": nid, "s": s, "risk": sc["total"], "level": sc["level"],
    })

OFFICIAL = ("雅诗兰黛", "兰蔻", "欧莱雅", "城市情报官", "REDPICK")
SELF_DECL = re.compile(r"(广告|推广|赞助|合作|恰饭|品牌方|种草位|kol)")

emit("# 独立标签验证：作者身份 + 自述")
emit()

# ---- 打标签 ----
rows = []
for n in notes:
    auth = n["s"].author or ""
    text = (n["s"].title or "") + (n["s"].text or "")
    is_off = any(k in auth for k in OFFICIAL)
    is_self = bool(SELF_DECL.search(text))
    rows.append({**n, "official": is_off, "self_decl": is_self})

n_off = sum(1 for r in rows if r["official"])
n_self = sum(1 for r in rows if r["self_decl"])
emit(f"- 官方号/情报官：**{n_off}** 篇")
for r in rows:
    if r["official"]:
        emit(f"  - `{r['id'][:8]}` {r['s'].author} jev={r['risk']:.3f} "
             f"{r['level']}")
emit(f"- 正文自述合作：**{n_self}** 篇")
emit()

# ---- 信号 vs 独立标签 ----
emit("## 1. 四个信号 × 官方标签")
emit()

def feats(r):
    cs = load_comments(cfg.data_root, r["id"])
    texts = [(c.text or "") for c in cs]
    cml = mean([len(t) for t in texts]) if texts else 0.0
    q = sum(1 for t in texts if any(w in t for w in
            ("吗", "怎么", "为什么", "如何")) or "?" in t)
    lks, cts = r["s"].liked, r["s"].comment_count
    cr = cts / lks if lks else None
    return {"cml": cml, "qr": q / len(texts) if texts else 0.0,
            "cr": cr, "tags": len(r["s"].tags), "n": len(texts)}

emit("| 笔记 | 作者 | official | jev | 评论均长 | 疑问率 | 评赞比 | 标签数 | 评论数 |")
emit("| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |")
for r in sorted(rows, key=lambda x: -x["risk"]):
    f = feats(r)
    cr = "-" if f["cr"] is None else f"{f['cr'] * 100:.1f}%"
    emit(f"| `{r['id'][:8]}` | {r['s'].author[:10]} | "
         f"{'**官**' if r['official'] else '-'} | {r['risk']:.3f} | "
         f"{f['cml']:.0f} | {f['qr'] * 100:.0f}% | {cr} | {f['tags']} | "
         f"{f['n']} |")
emit()

emit("## 2. 分组对比")
emit()
groups = {"官方": [r for r in rows if r["official"]],
          "个人": [r for r in rows if not r["official"]]}
emit("| 组 | 篇数 | jev均值 | 评论均长 | 疑问率均值 | 评赞比中位 | 标签数中位 |")
emit("| --- | ---: | ---: | ---: | ---: | ---: | ---: |")
for name, g in groups.items():
    if not g:
        continue
    fs = [feats(r) for r in g]
    crs = sorted(f["cr"] for f in fs if f["cr"] is not None)
    tgs = sorted(f["tags"] for f in fs)
    emit(f"| {name} | {len(g)} | {mean([r['risk'] for r in g]):.3f} | "
         f"{mean([f['cml'] for f in fs]):.0f} | "
         f"{mean([f['qr'] for f in fs]) * 100:.0f}% | "
         f"{(crs[len(crs) // 2] * 100 if crs else 0):.1f}% | "
         f"{tgs[len(tgs) // 2] if tgs else 0} |")
emit()

# ---- 真软广 vs 官方 ----
emit("## 3. 灵魂问题：软广抓得到吗")
emit()
emit("官方号好认，真正的挑战是**个人号发的软广**。")
emit()
emit("用 `is_ad` 维度看个人号里有没有疑似软广，")
emit("再看它们的评论均长是否也短 —— 如果是，信号才对软广有效。")
emit()
ad_by_note = {}
for s in scores:
    if s["kind"] != "note":
        continue
    v = next((d["value"] for d in s["dimensions"]
              if d["name"] == "is_ad"), None)
    ad_by_note[s["subject_id"]] = v
emit("| 个人号笔记 | jev风险 | is_ad | 评论均长 | 疑问率 |")
emit("| --- | ---: | ---: | ---: | ---: |")
pers = [r for r in rows if not r["official"]]
for r in sorted(pers, key=lambda x: -(ad_by_note.get(x["id"]) or 0))[:8]:
    f = feats(r)
    emit(f"| `{r['id'][:8]}` {r['s'].author[:10]} | {r['risk']:.3f} | "
         f"{ad_by_note.get(r['id'], 0):.2f} | {f['cml']:.0f} | "
         f"{f['qr'] * 100:.0f}% |")
emit()
emit("如果 is_ad 高的个人号评论也短 → 信号抓软广有效；")
emit("如果只有官方号短 → 信号只是在测账号类型。")
emit()

out = ROOT / "out" / "brainstorm2.md"
out.write_text("\n".join(L), encoding="utf-8")
print(f"written: {out}")
"""对新采的两条短链笔记做完整判定展示（引擎输出的样子）。"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from jev_guard.core.config import load_config  # noqa: E402
from jev_guard.extractors.reader import load_comments, load_note  # noqa: E402

cfg = load_config()
L: list[str] = []


def emit(s: str = "") -> None:
    L.append(s)


rows = [json.loads(x) for x in
        (ROOT / "out" / "scores.jsonl").read_text(encoding="utf-8").splitlines()
        if x.strip()]
by_id = {r["subject_id"]: r for r in rows}

NEW = ["6ac7a169000000000200e07a", "6ac78f92000000001c02e653"]

for nid in NEW:
    n = load_note(cfg.data_root, nid)
    r = by_id.get(nid)
    if not n or not r:
        emit(f"跳过 {nid[:8]}（无数据）")
        continue
    emit(f"{'=' * 72}")
    emit(f"笔记 {nid}")
    emit(f"{'=' * 72}")
    emit(f"标题: {n.title}")
    emit(f"作者: {n.author}")
    emit(f"正文: {n.text[:100]}...")
    emit(f"互动: 赞 {n.liked} · 藏 {n.collected} · "
         f"评 {n.comment_count} · 分享 {n.share}")
    emit()
    emit(f"── Layer 1：内容真实性 ──")
    emit(f"总分 {r['total']:.3f}  →  {r['level_label']}")
    emit(f"主因: {r.get('top_factor')}")
    emit()
    emit("维度:")
    for d in r.get("dimensions", []):
        bar = "#" * int(d["value"] * 28)
        emit(f"  {d['name']:<14}{d['value']:.3f} {bar}")
    if r.get("evidence"):
        emit()
        emit("命中证据:")
        for e in r["evidence"][:4]:
            emit(f"  · {e[:70]}")
    emit()
    emit(f"── Layer 2：传播质量 ──")
    sd = r.get("spread_sd")
    emit(f"评论数 {r.get('spread_n')}  均长 "
         f"{r.get('spread_mean')}  标准差 "
         f"{sd if sd is not None else '样本不足'}"
         f"{'  ⚠ 整齐得不自然' if r.get('spread_flag') else ''}")
    # 评论级判定分布
    cs = [c for c in rows if c["kind"] == "comment"]
    ids = {c.subject_id for c in load_comments(cfg.data_root, nid)}
    mine = [c for c in cs if c["subject_id"] in ids]
    dist = {"high": 0, "medium": 0, "low": 0}
    for c in mine:
        dist[c["level"]] += 1
    emit()
    emit(f"── 评论级判定（{len(mine)} 条）──")
    emit(f"  高 {dist['high']} · 中 {dist['medium']} · 低 {dist['low']}")
    top = sorted(mine, key=lambda x: -x["total"])[:3]
    for c in top:
        txt = ""
        for cc in load_comments(cfg.data_root, nid):
            if cc.subject_id == c["subject_id"]:
                txt = cc.text[:44]
                break
        emit(f"  {c['total']:.3f} [{c['level']}] {txt}")
    emit()

out = ROOT / "out" / "engine_demo.md"
out.write_text("\n".join(L), encoding="utf-8")
print("\n".join(L))
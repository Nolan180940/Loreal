"""把 regression/ 阶段已打好的 42 篇标签转成 jev-guard 格式。

用途：验证 ``score`` 链路而不消耗 jev 额度（free 正在限流）。
这些标签本来就是 jev-1.13-free产出的，只是存成了旧格式。
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from jev_guard.core.models import Label, SubjectKind
from jev_guard.core.questions import NOTE_SPECS
from jev_guard.pipeline.store import LabelStore

SRC = Path(r"d:\LOreal-ai\regression\labels\note_labels.json")
DST = Path(r"d:\LOreal-ai\jev\out\labels_note.jsonl")

CLAIM_MAP = {"none": 0.0, "promotion": 0.3333, "skincare": 0.6667,
             "medical": 1.0}


def main() -> int:
    if not SRC.is_file():
        print(f"[FAIL] 找不到 {SRC}")
        return 2
    raw = json.loads(SRC.read_text(encoding="utf-8"))
    store = LabelStore(DST, fsync_every=10)
    store.reset() if hasattr(store, "reset") else None
    if DST.is_file():
        DST.unlink()

    n = ok = 0
    for nid, ans in raw.items():
        if not isinstance(ans, dict) or "error" in ans:
            continue
        n += 1
        a = ans.get("answers") or ans
        dims = []
        # noul 维度
        for k in ("is_ad", "is_cta", "has_risk"):
            v = (a.get(k) or {}).get("noul")
            if v is not None:
                dims.append({"name": k, "value": float(v),
                             "confidence": None, "detail": {}})
        # score 维度：用 probabilities 归一化（与normalize_answer 一致）
        ex = a.get("exaggeration") or {}
        probs = ex.get("probabilities")
        if isinstance(probs, dict) and probs:
            order = NOTE_SPECS["exaggeration"].criteria_order
            n_ = len(order)
            acc = wsum = 0.0
            for i, lab in enumerate(order):
                p = probs.get(str(i), probs.get(lab))
                if p is None:
                    continue
                acc += float(p) * (i / (n_ - 1))
                wsum += float(p)
            if wsum:
                dims.append({"name": "exaggeration", "value": acc / wsum,
                             "confidence": ex.get("confidence"),
                             "detail": {"legend": ex.get("legend")}})
        # choice 维度：映射成 0..1 数值
        ct = a.get("claim_type") or {}
        if ct.get("choice"):
            dims.append({"name": "claim_type",
                         "value": CLAIM_MAP.get(ct["choice"], 0.0),
                         "confidence": ct.get("confidence"),
                         "detail": {"choice": ct["choice"]}})

        if not dims:
            continue
        store.save(Label(subject_id=nid, kind=SubjectKind.NOTE,
                         dimensions=tuple(_mk(d) for d in dims),
                         model="jev-1.13-free", raw={}))
        ok += 1

    store.sync()
    print(f"converted {ok}/{n} -> {DST}")
    return 0 if ok else 1


def _mk(d: dict):
    from jev_guard.core.models import DimensionScore
    return DimensionScore(name=d["name"], value=d["value"],
                          confidence=d["confidence"], detail=d["detail"])


if __name__ == "__main__":
    raise SystemExit(main())
"""标注工作台：生成待人工标注的清单。

为什么需要它
------------
「准确率」必须有 ground truth 才能算。当前项目**没有任何可信标注**：
`小红书帖子CTA单人标注_200条.xlsx` 与 `data/` 的42 篇ID 完全对不上
（实测四种匹配方式全部0 命中），且标注对象是 AI 生成的营销长文，
而 `data/` 是真实 UGC 笔记 —— 两批不同的数据。

所以只能自己标。本模块负责：
1. 挑出**信息量最大**的样本（分数落在阈值边界附近的）
2. 生成一个可以直接在Excel 里填的清单
3. 读回填好的标注，算出与 jev 的一致率

关键设计：优先挑边界样本
------------------------
全42篇里挑30篇随机标，浪费在「明显安全」和「明显危险」上。
边界样本（total 在 0.25~0.75）才是阈值该卡的地方。
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

OUT = Path(r"d:\LOreal-ai\jev\out")
DATA = Path(r"d:\LOreal-ai\data")


def load_scores() -> list[dict]:
    p = OUT / "scores.jsonl"
    if not p.is_file():
        raise SystemExit(f"[!] 缺�� {p}，先跑 `jev-guard score`")
    rows = []
    with p.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    rows.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    return rows


def pick_for_labeling(rows: list[dict], n: int) -> list[dict]:
    """挑信息量最大的 n 条。

    优先级：
    1. 边界区（total 0.25~0.75）—— 这些决定了阈值卡在哪
    2. 极高分（top risk）—— 确认 jev 没瞎报
    3. 极低分（bottom）—— 确认 jev 没漏报
    """
    notes = [r for r in rows if r.get("kind") == "note"]
    for r in notes:
        r["_band"] = ("边界" if 0.25 <= r["total"] <= 0.75
                      else "高" if r["total"] > 0.75 else "低")
    bands = {"边界": [], "高": [], "低": []}
    for r in notes:
        bands[r["_band"]].append(r)

    # 边界区按距离 0.5 的远近排，越靠近越优先
    bands["边界"].sort(key=lambda r: abs(r["total"] - 0.5))
    bands["高"].sort(key=lambda r: -r["total"])
    bands["低"].sort(key=lambda r: r["total"])

    quota = {"边界": int(n * 0.6), "高": int(n * 0.2)}
    quota["低"] = n - quota["边界"] - quota["高"]
    out: list[dict] = []
    for k in ("高", "边界", "低"):
        out.extend(bands[k][:quota[k]])

    # 某档不够时，用剩余样本按「离阈值最近」补齐，
    # 否则 n=30 会被某档的样本量卡成 25。
    if len(out) < n:
        chosen = {r["subject_id"] for r in out}
        rest = [r for r in notes if r["subject_id"] not in chosen]
        rest.sort(key=lambda r: abs(r["total"] - 0.5))
        out.extend(rest[:n - len(out)])
    return out[:n]


def export(sel: list[dict], path: Path) -> None:
    rows = []
    for r in sel:
        nid = r["subject_id"]
        nj = DATA / nid / "content" / "note.json"
        title = desc = ""
        if nj.is_file():
            n = json.loads(nj.read_text(encoding="utf-8"))
            title = str(n.get("作品标题") or n.get("title") or "")
            desc = str(n.get("作品描述") or n.get("desc") or "")
        rows.append({
            "subject_id": nid,
            "band": r["_band"],
            "jev_total": round(r["total"], 3),
            "jev_level": r.get("level_label", ""),
            "jev_top_factor": r.get("top_factor") or "",
            "title": title,
            "desc": desc[:900],
            # 留空给人填
            "human_label": "",
            "human_note": "",
        })
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    print(f"[OK] {path}  ({len(rows)} 条待标注)")
    print("     填 human_label 列: high / medium / low")
    print("     建议先读 desc 再判，不要看 jev_total —— 避免锚定")


def evaluate(ann_path: Path, scores_path: Path) -> dict:
    """读回人工标注，算一致率。"""
    import csv as _csv
    rows = list(_csv.DictReader(ann_path.open(encoding="utf-8-sig")))
    scores = {r["subject_id"]: r
              for r in (json.loads(l) for l in
                        scores_path.read_text(encoding="utf-8").splitlines()
                        if l.strip())}

    n = 0
    agree = 0
    conf = {}
    mismatches = []
    for r in rows:
        hl = (r.get("human_label") or "").strip().lower()
        if hl not in ("high", "medium", "low"):
            continue
        sid = r["subject_id"]
        s = scores.get(sid)
        if not s:
            continue
        n += 1
        jl = s.get("level")
        # 二值化：high 算正例，medium/low 算负例（校准阈值关心的是高风险召回）
        agree += int((hl == "high") == (jl == "high"))
        conf[(hl, jl)] = conf.get((hl, jl), 0) + 1
        if hl != jl:
            mismatches.append({
                "subject_id": sid, "human": hl, "jev": jl,
                "total": s["total"], "title": r.get("title", "")[:40],
            })

    if n == 0:
        return {"error": "没有有效标注行"}

    tp = conf.get(("high", "high"), 0)
    fn = conf.get(("high", "medium"), 0) + conf.get(("high", "low"), 0)
    fp = conf.get(("medium", "high"), 0) + conf.get(("low", "high"), 0)
    prec = tp / (tp + fp) if tp + fp else 0.0
    rec = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * prec * rec / (prec + rec) if prec + rec else 0.0
    kappa_num = agree / n
    pe = sum((sum(v for (a, _), v in conf.items() if a == k)
              * sum(v for (_, b), v in conf.items() if b == k))
             for k in ("high", "medium", "low")) / (n * n) if n else 0
    kappa = ((kappa_num - pe) / (1 - pe)) if pe < 1 else 0.0

    return {
        "n": n,
        "agreement": round(kappa_num, 4),
        "cohen_kappa": round(kappa, 4),
        "high_precision": round(prec, 4),
        "high_recall": round(rec, 4),
        "high_f1": round(f1, 4),
        "confusion": {f"human_{a}/jev_{b}": v
                      for (a, b), v in sorted(conf.items())},
        "mismatches": mismatches,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("action", choices=["export", "eval"])
    ap.add_argument("--n", type=int, default=30)
    ap.add_argument("--file", default=str(OUT / "to_label.csv"))
    ap.add_argument("--scores", default=str(OUT / "scores.jsonl"))
    args = ap.parse_args()

    if args.action == "export":
        rows = pick_for_labeling(load_scores(), args.n)
        export(rows, Path(args.file))
    else:
        res = evaluate(Path(args.file), Path(args.scores))
        print(json.dumps(res, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
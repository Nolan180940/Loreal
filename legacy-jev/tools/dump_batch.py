"""导出分批正文，供人工阅读判定。"""
from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
OUT = Path(r"d:\LOreal-ai\jev\out")

rows = list(csv.DictReader((OUT / "to_label.csv").open(encoding="utf-8-sig")))
rows.sort(key=lambda r: -float(r["jev_total"]))
sc: dict[str, dict] = {}
for line in (OUT / "scores.jsonl").read_text(encoding="utf-8").splitlines():
    if line.strip():
        x = json.loads(line)
        sc[x["subject_id"]] = x

batch = int(sys.argv[1]) if len(sys.argv) > 1 else 1
size = int(sys.argv[2]) if len(sys.argv) > 2 else 10
chunk = rows[(batch - 1) * size: batch * size]

out = []
for i, r in enumerate(chunk, (batch - 1) * size + 1):
    m = sc.get(r["subject_id"], {})
    out.append(f"=== {i}. {r['subject_id']} jev={r['jev_total']} {r['jev_level']}")
    out.append(f"标题: {r['title']}")
    out.append("维度: " + " ".join(
        f"{d['name']}={d['value']:.2f}" for d in m.get("dimensions", [])))
    ev = m.get("evidence") or []
    if ev:
        out.append(f"证据: {ev[0][:80]}")
    out.append("正文: " + (r["desc"] or "")[:700].replace("\n", " "))
    out.append("")

p = OUT / f"batch{batch}.txt"
p.write_text("\n".join(out), encoding="utf-8")
print(f"[OK] {p}  {len(chunk)} 篇")
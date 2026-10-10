# -*- coding: utf-8 -*-
"""最终核对：图片三处口径必须一致。

* ``images``（SSR，去重后）
* ``下载地址``（历史 schema）
* ``images/*.jpeg`` 实际文件数
* ``images/urls.json`` 清单长度

四者应当相等；不等就说明还有残留问题。
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
NOTE_RE = re.compile(r"/(?:explore|discovery/item)/([0-9a-f]{24})")
IMG_EXTS = (".jpg", ".jpeg", ".png", ".webp", ".heic", ".avif")

ids = [m.group(1) for m in
       (NOTE_RE.search(l) for l in
        (ROOT / "urls.txt").read_text(encoding="utf-8").splitlines()) if m]


def key(u: object) -> str:
    """图片标识。非字符串（历史产物里偶有 dict）原样落回，避免误判。"""
    if not isinstance(u, str):
        return json.dumps(u, ensure_ascii=False, sort_keys=True)[:80]
    return u.split("?", 1)[0].split("!", 1)[0].rstrip("/").rsplit("/", 1)[-1]


print(f"{'note':<10}{'images':<8}{'下载地址':<10}{'urls.json':<11}{'文件':<6}"
      f"{'一致?':<7}")
print("-" * 56)

bad = []
for nid in ids:
    d = DATA / nid
    n = {}
    p = d / "content" / "note.json"
    if p.is_file():
        try:
            n = json.loads(p.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            n = {}
    imgs = n.get("images") or []
    dzd = n.get("下载地址")
    dzd_n = len(dzd) if isinstance(dzd, list) else (
        1 if isinstance(dzd, str) and dzd.strip() else 0)
    u = []
    up = d / "images" / "urls.json"
    if up.is_file():
        try:
            u = json.loads(up.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            u = []
    u = u if isinstance(u, list) else []
    files = [f for f in (d / "images").iterdir()
             if f.is_file() and f.suffix.lower() in IMG_EXTS] \
        if (d / "images").is_dir() else []

    # 去重后的真实张数
    real = len({key(x) for x in u}) or len(files)
    ok = (len({key(x) for x in imgs}) == real
          and len({key(x) for x in u}) == real
          and len(files) == real)
    if not ok:
        bad.append(nid)
    print(f"{nid[:8]:<10}{len(imgs):<8}{dzd_n:<10}{len(u):<11}{len(files):<6}"
          f"{'Y' if ok else 'N':<7}")

print(f"\n不一致 {len(bad)} / {len(ids)}"
      + (f": {[b[:8] for b in bad]}" if bad else ""))

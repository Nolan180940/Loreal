# -*- coding: utf-8 -*-
"""修复被回填写坏的图片字段（同一张图的 CDN 变体重复）。

背景
----
``ssr.parse_note()`` 早期版本没做图片去重。小红书 SSR 里同一张图会以
两个 CDN 变换后缀各出现一次（``!h5_1080jpg`` 展示版 +
``!style_xxx`` 样式预览版），于是：

* ``images`` / ``下载地址`` 里每张图重复 2 次
* ``image_count`` 是真实张数的 2 倍（实测 `6ab8e804`：14 个 URL = 7 张图）

去重逻辑已修进 ``ssr._dedupe_images()``；这个脚本负责**把已经落坏的
数据改回来**，不需要重新联网抓取。

只动 ``source == "xhs-cli/core"`` 的笔记 —— 那是回填写过的标记，
没这个标记说明是历史采集产物，不该碰。

用法::

    python tools/fix_image_dupes.py            # 干跑
    python tools/fix_image_dupes.py --apply
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "xhs-cli" / "src"))

from xhs_cli.core.ssr import _dedupe_images  # noqa: E402

DATA = ROOT / "data"
MARK = "xhs-cli/core"


def force_utf8() -> None:
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8", errors="replace")
        except Exception:  # noqa: BLE001
            pass


def read(p: Path) -> Any:
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return None


def dedupe_url_list(v: Any) -> tuple[Any, int]:
    """列表就按 base 去重；字符串（历史 schema 的空格分隔串）保持原样。"""
    if isinstance(v, list):
        urls = [u for u in v if isinstance(u, str)]
        out = _dedupe_images(urls)
        return out, len(urls) - len(out)
    return v, 0


def main() -> int:
    ap = argparse.ArgumentParser(description="修复重复的图片字段")
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()
    force_utf8()

    targets = sorted(d for d in DATA.iterdir()
                     if d.is_dir() and len(d.name) == 24)
    touched = 0

    for d in targets:
        p = d / "content" / "note.json"
        n = read(p)
        if not isinstance(n, dict) or n.get("source") != MARK:
            continue

        changed: list[str] = []
        for key in ("images", "下载地址"):
            if key not in n:
                continue
            new, dropped = dedupe_url_list(n[key])
            if dropped:
                n[key] = new
                changed.append(f"{key}-{dropped}")

        if "images" in n and isinstance(n["images"], list):
            want = len(n["images"])
            if n.get("image_count") != want:
                changed.append(f"image_count {n.get('image_count')}→{want}")
                n["image_count"] = want

        if not changed:
            continue
        touched += 1
        print(f"{d.name[:8]}  {'  '.join(changed)}")
        if args.apply:
            p.write_text(json.dumps(n, ensure_ascii=False, indent=2),
                         encoding="utf-8")

    print(f"\n{'已修复' if args.apply else '待修复'} {touched} 篇")
    if not args.apply and touched:
        print("加 --apply 执行")
    return 0


if __name__ == "__main__":
    sys.exit(main())

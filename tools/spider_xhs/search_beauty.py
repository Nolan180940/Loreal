# -*- coding: utf-8 -*-
"""搜索小红书笔记并抓取评论，用于收集「差评/避雷」类语料。

用法（tools\\.venv 解释器）：
    .\\.venv\\Scripts\\python.exe search_beauty.py

流程：搜索关键词 -> 逐篇抓评论（含楼中楼）-> 落盘
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
TOOLS = HERE.parent
ROOT = TOOLS.parent
for p in (str(HERE), str(TOOLS)):
    if p not in sys.path:
        sys.path.insert(0, p)

OUT = ROOT / "data" / "search"

# 关键词：直接指向「负面口碑」的内容
QUERIES = [
    "美妆避雷",
    "面霜踩雷",
    "护肤翻车",
]

PER_QUERY = 6          # 每个词取多少篇
MAX_COMMENT = 40       # 每篇最多抓多少条评论（风控 + 时间）
SLEEP = 2.0            # 每篇之间的间隔（秒）


def read_cookie() -> str:
    env = ROOT / ".env"
    if env.is_file():
        for ln in env.read_text(encoding="utf-8", errors="replace").splitlines():
            if ln.startswith("XHS_COOKIE="):
                return ln.split("=", 1)[1].strip()
    return ""


def main() -> int:
    from thread_fetcher import complete_threads
    from xhs_utils.xhs_pc import XHSPcAuth
    from apis.xhs_pc_apis import XHS_Apis

    cookie = read_cookie()
    if not cookie:
        print("[X] 未找到 cookie")
        return 2

    auth = XHSPcAuth.from_cookie(cookie)
    apis = XHS_Apis(auth)
    apis.bootstrap()
    print("[OK] 签名就绪")

    OUT.mkdir(parents=True, exist_ok=True)
    results = []

    for q in QUERIES:
        print(f"\n=== 搜索：{q} ===")
        try:
            ok, msg, notes = apis.search_some_note(q, require_num=PER_QUERY)
        except Exception as e:
            print(f"  搜索失败：{type(e).__name__}: {e}")
            continue
        notes = notes or []
        print(f"  返回 {len(notes)} 篇")
        for n in notes[:PER_QUERY]:
            nid = n.get("note_id") or n.get("id") or ""
            title = (n.get("title") or n.get("display_title") or "")[:36]
            if not nid:
                continue
            print(f"  - {nid} {title}")
            try:
                cok, cmsg, tops = apis.get_note_all_out_comment(
                    nid, n.get("xsec_token") or "")
                tops = tops or []
                stat = complete_threads(apis, tops, nid,
                                        n.get("xsec_token") or "", verbose=False)
                replies = []
                for c in tops:
                    for s in (c.get("sub_comments") or []):
                        s["_parent_id"] = c.get("id", "")
                        replies.append(s)
                results.append({
                    "query": q,
                    "note_id": nid,
                    "title": title,
                    "like": n.get("liked_count") or n.get("like_count") or "",
                    "comments": tops,
                    "replies": replies,
                    "total": len(tops) + len(replies),
                    "gaps": len(stat.get("gaps") or []),
                })
                print(f"    评论 {len(tops)}+{len(replies)} = "
                      f"{len(tops)+len(replies)}")
            except Exception as e:
                print(f"    评论失败：{type(e).__name__}")
            time.sleep(SLEEP)

    path = OUT / "beauty_negative.json"
    path.write_text(json.dumps(results, ensure_ascii=False, indent=2),
                    encoding="utf-8")
    print(f"\n[OK] 共 {len(results)} 篇 -> {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

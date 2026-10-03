# -*- coding: utf-8 -*-
"""搜索小红书「美妆种草」类笔记并抓取评论（含楼中楼）。

与 search_beauty.py 的区别：那个搜「避雷/踩雷」负面帖，这个搜种草帖。
目标：拿到与「新版白绷带」同类型的品牌种草笔记，用于分析正面评论语料。

用法（tools\\.venv 解释器）：
    .\\.venv\\Scripts\\python.exe search_seeding.py
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
for p in (str(HERE), str(HERE.parent)):
    if p not in sys.path:
        sys.path.insert(0, p)

OUT = ROOT / "data" / "search"

# 品牌种草类关键词（对标「新版白绷带」笔记类型）
QUERIES = [
    "赫莲娜白绷带",
    "面霜测评",
    "贵妇面霜推荐",
    "油皮面霜",
]

PER_QUERY = 5           # 每个词取多少篇
SLEEP_BETWEEN_NOTES = 2.5   # 篇与篇之间（秒）
SLEEP_BETWEEN_QUERY = 4.0  # 词与词之间（秒）


def read_cookie() -> str:
    env = ROOT / ".env"
    if env.is_file():
        for ln in env.read_text(encoding="utf-8", errors="replace").splitlines():
            if ln.startswith("XHS_COOKIE="):
                return ln.split("=", 1)[1].strip()
    return ""


def _first(d: dict, *keys, default=""):
    for k in keys:
        v = d.get(k)
        if v:
            return v
    return default


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
    print("[OK] 登录态就绪  user_id=%s" % auth.user_id)

    OUT.mkdir(parents=True, exist_ok=True)
    results = []
    seen = set()

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
            # 搜索接口的返回结构（实测）：
            #   {"id": note_id, "xsec_token": ..., "note_card": {
            #      "display_title": ..., "user": {...}, "interact_info": {...}}}
            card = n.get("note_card") or {}
            inter = card.get("interact_info") or {}
            user = card.get("user") or {}
            nid = str(n.get("id") or "")
            token = str(n.get("xsec_token") or "")
            if not nid or nid in seen:
                continue
            seen.add(nid)
            title = str(card.get("display_title") or "")[:36]
            nickname = str(user.get("nickname") or user.get("nick_name") or "")
            like = inter.get("liked_count") or card.get("liked_count") or ""
            print(f"  - {nid} {title}")

            row = {
                "query": q,
                "note_id": nid,
                "xsec_token": token,
                "url": (f"https://www.xiaohongshu.com/explore/{nid}"
                        f"?xsec_token={token}&xsec_source=pc_search"
                        if token else ""),
                "title": title,
                "author": nickname,
                "author_id": str(user.get("user_id") or ""),
                "like": like,
                "comments": [], "replies": [],
                "total": 0, "gaps": 0,
            }

            try:
                cok, cmsg, tops = apis.get_note_all_out_comment(nid, token)
                tops = tops or []
                stat = complete_threads(apis, tops, nid, token, verbose=False)
                replies = []
                for c in tops:
                    for sr in (c.get("sub_comments") or []):
                        sr["_parent_id"] = c.get("id", "")
                        replies.append(sr)
                row["comments"] = tops
                row["replies"] = replies
                row["total"] = len(tops) + len(replies)
                row["gaps"] = len(stat.get("gaps") or [])
                print(f"    评论 {len(tops)}+{len(replies)} = {row['total']}")
            except Exception as e:
                print(f"    评论失败：{type(e).__name__}")

            results.append(row)
            time.sleep(SLEEP_BETWEEN_NOTES)

        time.sleep(SLEEP_BETWEEN_QUERY)

    path = OUT / "seeding_posts.json"
    path.write_text(json.dumps(results, ensure_ascii=False, indent=2),
                    encoding="utf-8")
    tot = sum(r["total"] for r in results)
    print(f"\n[OK] {len(results)} 篇 / 共 {tot} 条评论 -> {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

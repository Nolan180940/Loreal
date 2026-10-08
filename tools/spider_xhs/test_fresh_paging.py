# -*- coding: utf-8 -*-
"""最小验证：新鲜 token + 翻页。

只用 2 次请求（首页 + 第2页），不做任何多余探测。
这是唯一没测过的组合 —— 之前的翻页测试全用旧 token。
"""
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent))

from apis.xhs_pc_apis import XHS_Apis  # noqa: E402
from apis.xhs_pc_login_apis import XHSLoginApi  # noqa: E402
from xhs_utils.xhs_pc import XHSPcAuth  # noqa: E402
from xhs_utils.xhs_util import splice_str  # noqa: E402

API = "/api/sns/web/v2/comment/page"
HOST = "https://edith.xiaohongshu.com"

# 两条短链展开后的新鲜笔记
TARGETS = [
    ("6ac7a169000000000200e07a",
     "CBSbM82gFQ98H0bPkS_SvF1BTpZ6RmOV7JDGzxPtFUwQc="),
    ("6ac78f92000000001c02e653",
     "CBSbM82gFQ98H0bPkS_SvF1D1_MqlC5GP7osrgCsQQG0I="),
]


def session():
    ck = XHSLoginApi().generate_init_cookies()
    cstr = "; ".join(f"{k}={v}" for k, v in ck.items())
    auth = XHSPcAuth.from_cookie(cstr)
    apis = XHS_Apis(auth)
    try:
        apis.bootstrap()
    except Exception:  # noqa: BLE001
        pass
    return apis, cstr


def get(apis, cstr, nid, curs, tok):
    sp = splice_str(API, {"note_id": nid, "cursor": curs,
                          "top_comment_id": "",
                          "image_formats": "jpg,webp,avif",
                          "xsec_token": tok})
    headers, cookies, _ = apis._request_params(sp, "", "GET")
    try:
        r = apis.http.get(HOST + sp, headers=headers, cookies=cookies,
                          timeout=25)
    except Exception as e:  # noqa: BLE001
        return f"net:{type(e).__name__}", [], ""
    if r.status_code == 461:
        return "461", [], ""
    import json
    try:
        j = r.json()
    except Exception:  # noqa: BLE001
        return f"badjson:{r.status_code}", [], ""
    if not j.get("success"):
        return f"code:{j.get('code')}", [], ""
    d = j.get("data") or {}
    return str(r.status_code), (d.get("comments") or []), str(d.get("cursor") or "")


for nid, tok in TARGETS:
    print(f"=== {nid[:8]} ===")
    apis, cstr = session()
    time.sleep(2.0)
    st, cs, cur = get(apis, cstr, nid, "", tok)
    print(f"  首页: HTTP {st} {len(cs)}条")
    if not cs:
        print("  首页空，跳过")
        continue
    c0 = cs[0]
    print(f"    首条: {(c0.get('content') or '')[:30]} "
          f"ip={c0.get('ip_location')} time={c0.get('create_time')}")
    time.sleep(3.5)
    st2, cs2, cur2 = get(apis, cstr, nid, cur, tok)
    print(f"  第2页: HTTP {st2} {len(cs2)}条")
    if cs2:
        print(f"    ✅ 翻页成功！累计 {len(cs)+len(cs2)} 条")
        print(f"    首条: {(cs2[0].get('content') or '')[:30]}")
    else:
        print(f"    ❌ 第2页失败")
    print()
    time.sleep(2.0)
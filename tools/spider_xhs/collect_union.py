# -*- coding: utf-8 -*-
"""全量评论采集器：多会话 + 锚点轮换。

已确认的机制（多轮实测）
------------------------
1. 每个全新匿名会话只给 **1 次**评论请求配额（第 2 次必 461 / 空 data）
2. 但不同会话返回的**窗口不同**（排序随机化）
   - 5 个会话的首页并集 = 12 条（单个只有 10）
   - 3 个不同 top_comment_id 的并集 = 14 条
3. 所以：N 个会话 → N 次请求 → 每轮约 2 条新评论

策略
----
轮换会话，每轮用不同的 anchor（top_comment_id）：
  - 第 1 轮 anchor=""（首页）
  - 后续轮用已收集到的评论 id 做 anchor，探不同窗口
合并去重，直到连续 K 轮无新增或触发配额。

断点续跑：进度写 _union_state.json，重跑自动继续。
"""

import json
import re
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent))

from apis.xhs_pc_apis import XHS_Apis
from apis.xhs_pc_login_apis import XHSLoginApi
from xhs_utils.xhs_pc import XHSPcAuth
from xhs_utils.xhs_util import splice_str

API = "/api/sns/web/v2/comment/page"
STATE = HERE / "_union_state.json"

# ---- 目标：从命令行列传入，或用默认 ----
NID = sys.argv[1] if len(sys.argv) > 1 else "6aa37e93000000000d027216"
TOK = (sys.argv[2] if len(sys.argv) > 2
       else "ABP1f-kqDOrM1WTlwyuFhlqe5vY6pzb3ZFhiqI-A69gdk=")
MAX_ROUNDS = int(sys.argv[3]) if len(sys.argv) > 3 else 40
MAX_NEW_FAIL = 6      # 连续 N 轮无新增就停


def load_state() -> dict:
    if STATE.is_file():
        try:
            st = json.loads(STATE.read_text(encoding="utf-8"))
            if st.get("note_id") == NID:
                return st
        except Exception:  # noqa: BLE001
            pass
    return {"note_id": NID, "comments": {}, "anchors_tried": [],
            "rounds": 0, "log": []}


def save_state(st: dict) -> None:
    STATE.write_text(json.dumps(st, ensure_ascii=False), encoding="utf-8")


def fresh_apis():
    ck = XHSLoginApi().generate_init_cookies()
    cstr = "; ".join(f"{k}={v}" for k, v in ck.items())
    auth = XHSPcAuth.from_cookie(cstr)
    apis = XHS_Apis(auth)
    apis.bootstrap()
    return apis


def one_call(anchor: str) -> tuple[str, list[dict]]:
    """用全新会话发一次请求。返回 (status, comments)。"""
    apis = fresh_apis()
    params = {"note_id": NID, "cursor": "", "top_comment_id": anchor,
              "image_formats": "jpg,webp,avif", "xsec_token": TOK}
    sp = splice_str(API, params)
    headers, cookies, _ = apis._request_params(sp, "", "GET")
    try:
        r = apis.http.get(apis.base_url + sp, headers=headers,
                          cookies=cookies, timeout=20)
    except Exception as e:  # noqa: BLE001
        return f"net:{type(e).__name__}", []
    if r.status_code == 461:
        return "461", []
    try:
        j = r.json()
    except Exception:  # noqa: BLE001
        return f"bad_json:{r.status_code}", []
    if not j.get("success"):
        return f"fail:{j.get('code')}", []
    return "ok", ((j.get("data") or {}).get("comments") or [])


def harvest(cs: list[dict]) -> int:
    """合并新评论，返回新增数。"""
    n = 0
    for c in cs:
        cid = c.get("id")
        if cid and cid not in st["comments"]:
            st["comments"][cid] = c
            n += 1
    return n


st = load_state()
print(f"已有 {len(st['comments'])} 条，轮次 {st['rounds']}", flush=True)

no_new = 0
quota_hit = 0
for rnd in range(st["rounds"], st["rounds"] + MAX_ROUNDS):
    # 选 anchor：第 1 轮空，之后轮换已收集的 id
    known = list(st["comments"])
    if rnd == 0:
        anchor = ""
    else:
        pool = [k for k in known if k not in st["anchors_tried"]]
        if not pool:
            pool = known          # 全部试过就重头轮换
        anchor = pool[rnd % len(pool)] if pool else ""

    status, cs = one_call(anchor)
    new = harvest(cs) if cs else 0
    st["rounds"] = rnd + 1
    if anchor:
        st["anchors_tried"].append(anchor)
    save_state(st)
    print(f"[{rnd + 1}] anchor={anchor[:8] or '(首页)'} status={status} "
          f"got={len(cs)} new={new} 总={len(st['comments'])}", flush=True)

    if status == "461":
        quota_hit += 1
        if quota_hit >= 3:
            print("配额连续耗尽，停止（重跑本脚本可续）")
            break
        time.sleep(5)
        continue
    quota_hit = 0

    if new == 0:
        no_new += 1
        if no_new >= MAX_NEW_FAIL:
            print(f"连续 {MAX_NEW_FAIL} 轮无新增，停止")
            break
    else:
        no_new = 0

    time.sleep(2.0)

print(f"\n最终: {len(st['comments'])} 条 / 轮次 {st['rounds']}")
out = Path(r"D:\LOreal-ai\jev\out") / f"_union_{NID[:8]}.json"
out.write_text(json.dumps(list(st["comments"].values()),
                          ensure_ascii=False), encoding="utf-8")
print(f"written: {out}")
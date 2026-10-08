# -*- coding: utf-8 -*-
"""配额恢复探测器：每 N 分钟测一次首页，找恢复窗口。

用法: python watch_quota.py [间隔秒] [总轮次]
"""
import json
import sys
import time
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent))

from apis.xhs_pc_apis import XHS_Apis
from apis.xhs_pc_login_apis import XHSLoginApi
from xhs_utils.xhs_pc import XHSPcAuth
from xhs_utils.xhs_util import splice_str

API = "/api/sns/web/v2/comment/page"
NID = "6aa37e93000000000d027216"
TOK = "ABP1f-kqDOrM1WTlwyuFhlqe5vY6pzb3ZFhiqI-A69gdk="
LOG = HERE / "_quota_watch.jsonl"

INTERVAL = int(sys.argv[1]) if len(sys.argv) > 1 else 300
ROUNDS = int(sys.argv[2]) if len(sys.argv) > 2 else 12


def probe() -> tuple[str, int]:
    ck = XHSLoginApi().generate_init_cookies()
    cstr = "; ".join(f"{k}={v}" for k, v in ck.items())
    auth = XHSPcAuth.from_cookie(cstr)
    apis = XHS_Apis(auth)
    apis.bootstrap()
    sp = splice_str(API, {"note_id": NID, "cursor": "",
                          "top_comment_id": "",
                          "image_formats": "jpg,webp,avif",
                          "xsec_token": TOK})
    headers, cookies, _ = apis._request_params(sp, "", "GET")
    try:
        r = apis.http.get(apis.base_url + sp, headers=headers,
                          cookies=cookies, timeout=20)
    except Exception as e:  # noqa: BLE001
        return f"net:{type(e).__name__}", 0
    if r.status_code == 461:
        return "461", 0
    try:
        j = r.json()
    except Exception:  # noqa: BLE001
        return "badjson", 0
    if not j.get("success"):
        return f"code:{j.get('code')}", 0
    d = j.get("data") or {}
    return "ok", len(d.get("comments") or [])


for i in range(ROUNDS):
    ts = datetime.now().strftime("%H:%M:%S")
    status, n = probe()
    rec = {"t": ts, "status": status, "n": n}
    with LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    print(f"[{ts}] round{i + 1}: {status} {n}条", flush=True)
    if status == "ok" and n > 0:
        print("✅ 配额已恢复")
        break
    if i < ROUNDS - 1:
        time.sleep(INTERVAL)

print(f"日志: {LOG}")
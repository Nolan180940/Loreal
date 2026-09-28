# -*- coding: utf-8 -*-
import sys, io, json
_out = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stdout = _out
sys.path.insert(0, r"D:\LOreal-ai\tools\spider_xhs")
sys.path.insert(0, r"D:\LOreal-ai")
from forensic.xhs_comments import get_cookie
from xhs_utils.xhs_pc import XHSPcAuth
from apis.xhs_pc_apis import XHS_Apis

NOTE="6a4cc2cd000000001101daf1"
TOKEN="CBzj7RPSlGq4mj5dZrkKRC4dHUhMRsg277nNCC2DPFur0="

ck = get_cookie()
print("cookie len:", len(ck))
auth = XHSPcAuth.from_cookie(ck)
print("auth built | user_id:", getattr(auth, "user_id", None))
apis = XHS_Apis(auth)
try:
    apis.bootstrap()
    print("bootstrap OK | user_id:", auth.user_id)
except Exception as e:
    print("bootstrap FAIL:", type(e).__name__, str(e)[:140])

ok, msg, lst = apis.get_note_all_out_comment(NOTE, TOKEN)
print(f"\ncomments ok={ok} n={len(lst) if lst else 0} msg={str(msg)[:120]}")
for c in (lst or [])[:6]:
    ui = c.get("user_info", {})
    print(" -", ui.get("nickname"), "|", c.get("ip_location"),
          "| like", c.get("like_count"), "|", (c.get("content") or "")[:46])

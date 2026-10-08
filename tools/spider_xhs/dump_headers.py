# -*- coding: utf-8 -*-
"""导出 _request_params 的完整头，与手工签名对比。"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent))

from apis.xhs_pc_login_apis import XHSLoginApi  # noqa: E402
from xhs_utils.xhs_pc import XHSPcAuth  # noqa: E402
from xhs_utils.xhs_pc.params import generate_xs_xs_common  # noqa: E402
from xhs_utils.xhs_util import splice_str  # noqa: E402
from apis.xhs_pc_apis import XHS_Apis  # noqa: E402

NID = "6aa37e93000000000d027216"
TOK = "ABP1f-kqDOrM1WTlwyuFhlqe5vY6pzb3ZFhiqI-A69gdk="
API = "/api/sns/web/v2/comment/page"

ck = XHSLoginApi().generate_init_cookies()
cstr = "; ".join(f"{k}={v}" for k, v in ck.items())
auth = XHSPcAuth.from_cookie(cstr)
apis = XHS_Apis(auth)
apis.bootstrap()

sp = splice_str(API, {"note_id": NID, "cursor": "", "top_comment_id": "",
                      "image_formats": "jpg,webp,avif", "xsec_token": TOK})
headers, cookies, _ = apis._request_params(sp, "", "GET")
print("=== _request_params 的头 ===")
for k, v in headers.items():
    print(f"  {k}: {str(v)[:70]}")

print("\n=== 对比：手工签名 ===")
a1 = ck.get("a1", "")
sc = auth.next_sign_context(API)
now = sc["now"]
xs2, xt2, xsc2 = generate_xs_xs_common(
    a1, sp, data="", method="GET",
    b1=auth.current_b1(now), dsl_pair=auth.dsl_pair,
    cookie=cstr, sign_context=sc)
print(f"  手工 x-s: {xs2[:70]}")
print(f"  正式 x-s: {str(headers.get('x-s', ''))[:70]}")
print(f"  一致: {xs2 == headers.get('x-s')}")
print(f"  手工 x-t: {xt2}  正式: {headers.get('x-t')}")
print(f"  手工 tier: {sc.get('tier')}")

# 保存正式头供浏览器使用
out = HERE / "_real_headers.json"
out.write_text(json.dumps(
    {k: str(v) for k, v in headers.items() if k.lower() != "cookie"},
    ensure_ascii=False), encoding="utf-8")
print(f"\n[written] {out}")
print(f"api = {sp[:120]}")
# -*- coding: utf-8 -*-
"""混合方案：Python 生成签名 + Playwright 浏览器指纹。

假设
----
服务端的评论翻页配额可能绑定「指纹维度」：
  - Python curl_cffi 指纹 -> 首页过，翻页 461
  - 如果浏览器指纹是独立配额，那用浏览器发 + Python 签名 = 翻页可过

做法
----
1. Python 生成匿名会话（a1 / web_session）并算出签名头（X-s / X-t / X-S-Common）
2. 把这些 cookie 注入 Playwright 浏览器上下文
3. 浏览器（真实 TLS/JS 指纹）发出带签名的 GET 请求
4. 如果第 2 页能过 -> 找到突破口

注意：签名的 a1 必须与浏览器携带的 a1 一致，否则签名校验失败。
"""
import json
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

NID = "6aa37e93000000000d027216"
TOK = "ABP1f-kqDOrM1WTlwyuFhlqe5vY6pzb3ZFhiqI-A69gdk="
API = "/api/sns/web/v2/comment/page"

# ---- 1. Python 建会话 ----
ck = XHSLoginApi().generate_init_cookies()
cstr = "; ".join(f"{k}={v}" for k, v in ck.items())
auth = XHSPcAuth.from_cookie(cstr)
apis = XHS_Apis(auth)
apis.bootstrap()
print("会话建立:", sorted(ck)[:6])

# ---- 2. 用 Python 拿首页 + cursor ----
ok, msg, res = apis.get_note_out_comment(NID, "", TOK)
cs = (res.get("data") or {}).get("comments") or []
cur = str((res.get("data") or {}).get("cursor") or "")
print(f"Python 首页: {len(cs)}条 cursor={cur[:16]}")

# ---- 3. 为第 2 页生成签名 ----
params2 = {"note_id": NID, "cursor": cur, "top_comment_id": "",
           "image_formats": "jpg,webp,avif", "xsec_token": TOK}
sp2 = splice_str(API, params2)
headers2, cookies2, _ = apis._request_params(sp2, "", "GET")
print("签名头 keys:", sorted(headers2.keys()))

# ---- 4. 浏览器侧：注入同会话 cookie + 发带签名的请求 ----
from playwright.sync_api import sync_playwright  # noqa: E402

with sync_playwright() as pw:
    br = pw.chromium.launch(headless=True, args=[
        "--disable-blink-features=AutomationControlled"])
    ctx = br.new_context(
        user_agent=headers2.get("user-agent", ""),
        locale="zh-CN",
        viewport={"width": 1440, "height": 900})
    # 注入 Python 会话的 cookie（a1 必须一致，否则签名失效）
    ctx.add_cookies([{"name": k, "value": str(v),
                      "domain": ".xiaohongshu.com", "path": "/"}
                     for k, v in ck.items()])
    pg = ctx.new_page()
    # 先访问首页让指纹热身
    try:
        pg.goto("https://www.xiaohongshu.com/explore",
                wait_until="domcontentloaded", timeout=25000)
        pg.wait_for_timeout(3000)
    except Exception as e:  # noqa: BLE001
        print("热身失败:", type(e).__name__)

    # 把签名头传进页面并发请求
    hdr = {k: v for k, v in headers2.items()
           if k.lower() in ("x-s", "x-t", "x-s-common", "x-b3-traceid",
                            "x-mns", "x-rap-param", "user-agent",
                            "accept", "accept-language", "referer",
                            "content-type")}
    js = """async (payload) => {
      const r = await fetch(payload.url, {
        method: 'GET',
        credentials: 'include',
        headers: payload.headers
      });
      const t = await r.text();
      return {status: r.status, body: t.slice(0, 300)};
    }"""
    got = pg.evaluate(js, {"url": "https://edith.xiaohongshu.com" + sp2,
                           "headers": hdr})
    print("浏览器+Python签名 第2页:", got["status"],
          got["body"][:200])
    br.close()

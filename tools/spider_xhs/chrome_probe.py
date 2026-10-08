# -*- coding: utf-8 -*-
"""有头真 Chrome + Python 签名：一体化全量评论采集。

为什么这个组合有可能成
----------------------
已排除的组合：
  headless chromium + Python 会话 + Python 签名  -> 461（指纹被识别）
  集成浏览器 + 无签名                            -> 500
  headless chromium + 浏览器会话                  -> 461

未测的：
  **有头真 Chrome（channel=chrome）+ 浏览器自建会话 + Python 签名**

真 Chrome 有完整的浏览器指纹（GPU、字体、插件、真实 TLS），
headless chromium 缺这些 —— 这很可能就是 461 的根源。

如果 feed 能加载 = 指纹通过，再做评论请求。
"""
import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent))

from playwright.sync_api import sync_playwright  # noqa: E402

from xhs_utils.xhs_pc import XHSPcAuth  # noqa: E402
from xhs_utils.xhs_pc.params import generate_xs_xs_common  # noqa: E402

NID = "6aa37e93000000000d027216"
TOK = "ABP1f-kqDOrM1WTlwyuFhlqe5vY6pzb3ZFhiqI-A69gdk="
API = "/api/sns/web/v2/comment/page"

with sync_playwright() as pw:
    br = pw.chromium.launch(
        channel="chrome", headless=False,
        args=["--disable-blink-features=AutomationControlled"])
    ctx = br.new_context(locale="zh-CN",
                         viewport={"width": 1440, "height": 900})
    pg = ctx.new_page()

    print("打开首页建立会话...", flush=True)
    try:
        pg.goto("https://www.xiaohongshu.com/explore?channel_id=homefeed_recommend",
                wait_until="domcontentloaded", timeout=35000)
        pg.wait_for_timeout(7000)
    except Exception as e:  # noqa: BLE001
        print("导航异常:", type(e).__name__)

    feed_ok = pg.evaluate(
        "() => { const f = window.__INITIAL_STATE__;"
        " const d = f && f.feed && f.feed.feeds && f.feed.feeds._rawValue;"
        " return Array.isArray(d) ? d.length : 0; }")
    print(f"feed 条数: {feed_ok}  "
          f"{'✅ 指纹通过' if feed_ok else '❌ 指纹被识别'}", flush=True)

    ck = {c["name"]: c["value"] for c in ctx.cookies()
          if "xiaohongshu" in c["domain"]}
    print(f"cookie: {sorted(ck)[:13]}", flush=True)
    print(f"有 web_session: {bool(ck.get('web_session'))}", flush=True)

    if feed_ok:
        # 用真浏览器的会话做签名
        cstr = "; ".join(f"{k}={v}" for k, v in ck.items())
        auth = XHSPcAuth.from_cookie(cstr)
        a1 = ck.get("a1", "")
        sc = auth.next_sign_context(API)
        now = sc["now"]
        xs, xt, xsc = generate_xs_xs_common(
            a1, API, data="", method="GET",
            b1=auth.current_b1(now), dsl_pair=auth.dsl_pair,
            cookie=cstr, sign_context=sc)
        print(f"签名就绪 tier={sc.get('tier')}", flush=True)

        # 在页面里发带签名的请求（浏览器自己带 cookie）
        result = pg.evaluate("""async (p) => {
          const r = await fetch(p.url, {credentials: 'include',
            headers: {'x-s': p.xs, 'x-t': p.xt, 'x-s-common': p.xsc,
                      'Accept': 'application/json, text/plain, */*'}});
          const t = await r.text();
          return {status: r.status, body: t.slice(0, 400)};
        }""", {"url": API + "?note_id=" + NID + "&cursor=&top_comment_id="
               "&image_formats=jpg%2Cwebp%2Cavif&xsec_token="
               + TOK, "xs": xs, "xt": str(xt), "xsc": xsc})
        print(f"comment/page: HTTP {result['status']}", flush=True)
        print(f"  {result['body'][:250]}", flush=True)

    br.close()

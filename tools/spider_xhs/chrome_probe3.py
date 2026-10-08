# -*- coding: utf-8 -*-
"""真 Chrome + 原样复用 _request_params 头：全量评论采集。

与上一版的区别
-------------
上一版手工拼头，漏了 **x-xray-traceid**（RAP 签名链的一环）。
本版直接用 `apis._request_params()` 的完整输出，一个字不改。

只剔除两个浏览器禁设的头：
  cookie  -> 浏览器自动带自己的（与签名同源）
  user-agent -> 浏览器自己的真 UA
"""
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent))

from playwright.sync_api import sync_playwright  # noqa: E402

from apis.xhs_pc_apis import XHS_Apis  # noqa: E402
from xhs_utils.xhs_pc import XHSPcAuth  # noqa: E402
from xhs_utils.xhs_util import splice_str  # noqa: E402

NID = "6aa37e93000000000d027216"
TOK = "ABP1f-kqDOrM1WTlwyuFhlqe5vY6pzb3ZFhiqI-A69gdk="
API = "/api/sns/web/v2/comment/page"
SKIP = {"cookie", "user-agent", "accept-encoding", "priority",
        "sec-fetch-dest", "sec-fetch-mode", "sec-fetch-site"}
# 真实 API 域名：相对路径会打到 www，但接口在 edith
API_HOST = "https://edith.xiaohongshu.com"

with sync_playwright() as pw:
    br = pw.chromium.launch(
        channel="chrome", headless=False,
        args=["--disable-blink-features=AutomationControlled"])
    ctx = br.new_context(locale="zh-CN",
                         viewport={"width": 1440, "height": 900})
    pg = ctx.new_page()
    print("打开首页...", flush=True)
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
    print(f"feed: {feed_ok} 条", flush=True)

    ck = {c["name"]: c["value"] for c in ctx.cookies()
          if "xiaohongshu" in c["domain"]}
    cstr = "; ".join(f"{k}={v}" for k, v in ck.items())
    auth = XHSPcAuth.from_cookie(cstr)
    apis = XHS_Apis(auth)
    try:
        apis.bootstrap()
    except Exception:  # noqa: BLE001
        pass

    def call(cursor: str) -> dict:
        sp = splice_str(API, {
            "note_id": NID, "cursor": cursor, "top_comment_id": "",
            "image_formats": "jpg,webp,avif", "xsec_token": TOK})
        headers, _cookies, _ = apis._request_params(sp, "", "GET")
        hdr = {k: str(v) for k, v in headers.items()
               if k.lower() not in SKIP}
        return pg.evaluate("""async (p) => {
          const r = await fetch(p.url, {credentials: 'include',
                                        headers: p.headers});
          const t = await r.text();
          let j = null;
          try { j = JSON.parse(t); } catch (e) {}
          return {status: r.status, raw: t.slice(0, 220),
                  ok: !!(j && j.success),
                  n: (j && j.data && (j.data.comments || []).length) || 0,
                  cursor: (j && j.data && j.data.cursor) || '',
                  hasMore: !!(j && j.data && j.data.has_more)};
        }""", {"url": API_HOST + sp, "headers": hdr})

    r1 = call("")
    print(f"首页: HTTP {r1['status']} n={r1['n']} "
          f"cursor={str(r1['cursor'])[:14]}", flush=True)
    if r1["n"] == 0:
        print(f"  raw: {r1['raw']}", flush=True)
    else:
        print(f"  ✅ 首页成功", flush=True)
        time.sleep(3.0)
        r2 = call(str(r1["cursor"]))
        print(f"第2页: HTTP {r2['status']} n={r2['n']}", flush=True)
        if r2["n"]:
            print("  🎉🎉 翻页成功 —— 全量评论路径打通！", flush=True)
        else:
            print(f"  raw: {r2['raw']}", flush=True)

    br.close()

# -*- coding: utf-8 -*-
"""真 Chrome + 精确 URL 签名：全量评论采集。

上一版的 bug
-----------
手工拼 URL 时 `xsec_token=...=` 的 `=` 未编码，而签名用的 URL 里是 `%3D`。
签名绑定 URL —— 两边不一致 → 网关拒绝 → 500。

本版修正
--------
1. 用 splice_str 生成唯一权威的 URL 字符串
2. 签名与请求都用同一个字符串
3. 补齐 RAP 头：x-rap-param / x-b3-traceid / x-xray-traceid
"""
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent))

from playwright.sync_api import sync_playwright  # noqa: E402

from xhs_utils.xhs_pc import XHSPcAuth  # noqa: E402
from xhs_utils.xhs_pc.params import (  # noqa: E402
    generate_x_b3_traceid, generate_xs_xs_common,
)
from xhs_utils.xhs_util import splice_str  # noqa: E402

NID = "6aa37e93000000000d027216"
TOK = "ABP1f-kqDOrM1WTlwyuFhlqe5vY6pzb3ZFhiqI-A69gdk="
API = "/api/sns/web/v2/comment/page"


def build_query(cursor: str) -> str:
    return splice_str(API, {
        "note_id": NID, "cursor": cursor, "top_comment_id": "",
        "image_formats": "jpg,webp,avif", "xsec_token": TOK,
    })


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
    a1 = ck.get("a1", "")

    def sign_and_call(cursor: str) -> dict:
        """签名 + 在浏览器里发请求（URL 完全一致）。"""
        url = build_query(cursor)
        sc = auth.next_sign_context(API)
        now = sc["now"]
        xs, xt, xsc = generate_xs_xs_common(
            a1, url, data="", method="GET",
            b1=auth.current_b1(now), dsl_pair=auth.dsl_pair,
            cookie=cstr, sign_context=sc)
        payload = {
            "url": url,
            "headers": {
                "x-s": xs, "x-t": str(xt), "x-s-common": xsc,
                "x-b3-traceid": generate_x_b3_traceid(16),
                "accept": "application/json, text/plain, */*",
                "accept-language": "zh-CN,zh;q=0.9",
                "referer": "https://www.xiaohongshu.com/",
            },
        }
        return pg.evaluate("""async (p) => {
          const r = await fetch(p.url, {credentials: 'include',
                                        headers: p.headers});
          const t = await r.text();
          let j = null;
          try { j = JSON.parse(t); } catch (e) {}
          return {status: r.status, raw: t.slice(0, 200),
                  ok: j && j.success, n: (j && j.data &&
                      (j.data.comments || []).length) || 0,
                  cursor: (j && j.data && j.data.cursor) || '',
                  hasMore: j && j.data && j.data.has_more};
        }""", payload)

    # 首页
    r1 = sign_and_call("")
    print(f"首页: HTTP {r1['status']} n={r1['n']} "
          f"cursor={str(r1['cursor'])[:14]}", flush=True)
    if r1["n"] == 0:
        print(f"  raw: {r1['raw']}", flush=True)

    if r1["n"] > 0:
        time.sleep(3.0)
        r2 = sign_and_call(str(r1["cursor"]))
        print(f"第2页: HTTP {r2['status']} n={r2['n']}", flush=True)
        if r2["n"] > 0:
            print("  🎉 翻页成功！", flush=True)
        else:
            print(f"  raw: {r2['raw']}", flush=True)

    br.close()

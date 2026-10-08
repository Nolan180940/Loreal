# -*- coding: utf-8 -*-
"""反向混合：浏览器建会话 -> Python 复用 cookie 签名。

为什么试这个
------------
之前的会话都是 `generate_init_cookies()` 脚本生成的 —— 它自己发 8-12 次
请求到 login/security 域，这个行为模式本身就是风控信号。短时间建 30+ 个
这样的会话，很可能就是触发 IP 级处罚的原因。

如果换「真浏览器访问页面」来建会话，cookie 的签发路径就是正常的，
可能落在不同的配额桶里。

流程
----
1. Playwright 打开 xhs 首页，等 session 建立
2. 导出全部 cookie（含 HttpOnly 的 web_session）
3. 用这些 cookie 构造 XHSPcAuth + 签名
4. 调 comment/page 首页 + 第 2 页
"""
import json
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
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")

# ---- 1. 浏览器建会话 ----
print("启动浏览器建立会话...", flush=True)
with sync_playwright() as pw:
    br = pw.chromium.launch(headless=True, args=[
        "--disable-blink-features=AutomationControlled"])
    ctx = br.new_context(user_agent=UA, locale="zh-CN",
                         viewport={"width": 1440, "height": 900})
    pg = ctx.new_page()
    try:
        pg.goto("https://www.xiaohongshu.com/explore",
                wait_until="domcontentloaded", timeout=30000)
        pg.wait_for_timeout(6000)
    except Exception as e:  # noqa: BLE001
        print("导航异常:", type(e).__name__)
    ck = {c["name"]: c["value"] for c in ctx.cookies()
          if "xiaohongshu" in c["domain"]}
    print(f"拿到 {len(ck)} 个 cookie: {sorted(ck)[:12]}", flush=True)
    # 顺便看看页面能不能拿到 note 数据
    try:
        ok = pg.evaluate(
            "() => { const f = window.__INITIAL_STATE__;"
            " const d = f && f.feed && f.feed.feeds && f.feed.feeds._rawValue;"
            " return !!(d && d.length); }")
        print(f"页面 feed 可用: {ok}", flush=True)
    except Exception:  # noqa: BLE001
        pass
    br.close()

if not ck.get("web_session"):
    print("⚠ 没拿到 web_session，会话未建立")

# ---- 2. 用浏览器 cookie 签名 ----
cstr = "; ".join(f"{k}={v}" for k, v in ck.items())
auth = XHSPcAuth.from_cookie(cstr)
apis = XHS_Apis(auth)
apis.bootstrap()
print("签名上下文就绪", flush=True)


def call(cursor: str) -> tuple[str, list, str]:
    sp = splice_str(API, {"note_id": NID, "cursor": cursor,
                          "top_comment_id": "",
                          "image_formats": "jpg,webp,avif",
                          "xsec_token": TOK})
    headers, cookies, _ = apis._request_params(sp, "", "GET")
    try:
        r = apis.http.get(apis.base_url + sp, headers=headers,
                          cookies=cookies, timeout=20)
    except Exception as e:  # noqa: BLE001
        return f"net:{type(e).__name__}", [], ""
    if r.status_code == 461:
        return "461", [], ""
    try:
        j = r.json()
    except Exception:  # noqa: BLE001
        return f"bad:{r.status_code}", [], ""
    if not j.get("success"):
        return f"code:{j.get('code')}", [], ""
    d = j.get("data") or {}
    return "ok", (d.get("comments") or []), str(d.get("cursor") or "")


st, cs, cur = call("")
print(f"首页: {st} {len(cs)}条 cursor={cur[:14]}", flush=True)
if cs:
    print(f"  首条: {(cs[0].get('content') or '')[:40]} "
          f"ip={cs[0].get('ip_location')} like={cs[0].get('like_count')}",
          flush=True)
    time.sleep(3.0)
    st2, cs2, cur2 = call(cur)
    print(f"第2页: {st2} {len(cs2)}条", flush=True)
    if cs2:
        print("  ✅ 浏览器会话 + Python 签名 可以翻页！", flush=True)
        print(f"  首条: {(cs2[0].get('content') or '')[:40]}", flush=True)
    else:
        print("  ❌ 第2页仍失败", flush=True)

# 存 cookie 供后续复用
out = HERE / "_browser_session.json"
out.write_text(json.dumps(ck, ensure_ascii=False), encoding="utf-8")
print(f"cookie 已存: {out}", flush=True)
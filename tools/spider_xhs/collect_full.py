# -*- coding: utf-8 -*-
"""全量评论采集器（真 Chrome + 精确签名）。

已验证
------
- 真 Chrome 指纹通过（feed 可加载）
- 签名必须用 `https://edith.xiaohongshu.com` 域名（相对路径打到 www 会 500）
- 签名与请求 URL 必须逐字节一致（splice_str 的输出）
- 修好域名后返回 461（配额），不再是 500（签名错）—— 签名链路已通

本脚本
------
保持一个 Chrome 常驻，轮询等待配额恢复；一旦首页能拿到数据，
就连续翻页直到取完或再次触发限流。全部数据落盘，支持断点续跑。

用法
    python collect_full.py <note_id> <xsec_token> [间隔秒]
"""
import json
import sys
import time
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent))

from playwright.sync_api import sync_playwright  # noqa: E402

from apis.xhs_pc_apis import XHS_Apis  # noqa: E402
from xhs_utils.xhs_pc import XHSPcAuth  # noqa: E402
from xhs_utils.xhs_util import splice_str  # noqa: E402

API = "/api/sns/web/v2/comment/page"
API_HOST = "https://edith.xiaohongshu.com"
SKIP = {"cookie", "user-agent", "accept-encoding", "priority",
        "sec-fetch-dest", "sec-fetch-mode", "sec-fetch-site"}

NID = sys.argv[1] if len(sys.argv) > 1 else "6aa37e93000000000d027216"
TOK = (sys.argv[2] if len(sys.argv) > 2
       else "ABP1f-kqDOrM1WTlwyuFhlqe5vY6pzb3ZFhiqI-A69gdk=")
GAP = int(sys.argv[3]) if len(sys.argv) > 3 else 180

OUT = Path(r"D:\LOreal-ai\jev\out") / f"_full_{NID[:8]}.json"
LOG = HERE / "_collect_log.txt"


def log(msg: str) -> None:
    ts = datetime.now().strftime("%H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line, flush=True)
    with LOG.open("a", encoding="utf-8") as f:
        f.write(line + "\n")


with sync_playwright() as pw:
    br = pw.chromium.launch(
        channel="chrome", headless=False,
        args=["--disable-blink-features=AutomationControlled"])
    ctx = br.new_context(locale="zh-CN",
                         viewport={"width": 1440, "height": 900})
    pg = ctx.new_page()
    log("打开首页建会话...")
    try:
        pg.goto("https://www.xiaohongshu.com/explore?channel_id=homefeed_recommend",
                wait_until="domcontentloaded", timeout=35000)
        pg.wait_for_timeout(6000)
    except Exception as e:  # noqa: BLE001
        log(f"导航异常 {type(e).__name__}")

    ck = {c["name"]: c["value"] for c in ctx.cookies()
          if "xiaohongshu" in c["domain"]}
    cstr = "; ".join(f"{k}={v}" for k, v in ck.items())
    auth = XHSPcAuth.from_cookie(cstr)
    apis = XHS_Apis(auth)
    try:
        apis.bootstrap()
    except Exception:  # noqa: BLE001
        pass
    log(f"会话就绪 a1={ck.get('a1', '')[:16]}...")

    def call(cursor: str) -> dict:
        sp = splice_str(API, {
            "note_id": NID, "cursor": cursor, "top_comment_id": "",
            "image_formats": "jpg,webp,avif", "xsec_token": TOK})
        headers, _c, _ = apis._request_params(sp, "", "GET")
        hdr = {k: str(v) for k, v in headers.items()
               if k.lower() not in SKIP}
        return pg.evaluate("""async (p) => {
          const r = await fetch(p.url, {credentials: 'include',
                                        headers: p.headers});
          const t = await r.text();
          let j = null;
          try { j = JSON.parse(t); } catch (e) {}
          return {status: r.status, raw: t.slice(0, 150),
                  n: (j && j.data && (j.data.comments || []).length) || 0,
                  cursor: (j && j.data && j.data.cursor) || '',
                  hasMore: !!(j && j.data && j.data.has_more),
                  comments: (j && j.data && j.data.comments) || []};
        }""", {"url": API_HOST + sp, "headers": hdr})

    # 断点续跑
    state = {"note_id": NID, "comments": {}, "cursor": "", "done": False}
    if OUT.is_file():
        try:
            old = json.loads(OUT.read_text(encoding="utf-8"))
            state["comments"] = {c["id"]: c for c in old if c.get("id")}
            log(f"续跑：已有 {len(state['comments'])} 条")
        except Exception:  # noqa: BLE001
            pass

    # ---- 阶段1：等配额 ----
    attempts = 0
    while True:
        attempts += 1
        r = call("")
        if r["n"] > 0:
            log(f"配额已恢复（第 {attempts} 次探测），首页 {r['n']} 条")
            break
        log(f"探测 {attempts}: HTTP {r['status']} {r['raw'][:60]}")
        if attempts >= 20:
            log("探测 20 次仍未恢复，退出")
            br.close()
            raise SystemExit(1)
        time.sleep(GAP)

    # ---- 阶段2：翻页采集 ----
    def hz(cs):
        n = 0
        for c in cs:
            if c.get("id") and c["id"] not in state["comments"]:
                state["comments"][c["id"]] = c
                n += 1
        return n

    hz(r["comments"])
    cursor = str(r["cursor"])
    page = 1
    log(f"第1页: +{len(r['comments'])} 总={len(state['comments'])} "
        f"hasMore={r['hasMore']}")
    while r["hasMore"] and page < 300:
        time.sleep(4.0)
        r = call(cursor)
        page += 1
        if r["n"] == 0:
            log(f"第{page}页: HTTP {r['status']} 中断 ({r['raw'][:50]})")
            break
        new = hz(r["comments"])
        log(f"第{page}页: +{new} 总={len(state['comments'])} "
            f"hasMore={r['hasMore']}")
        cursor = str(r["cursor"])
        if new == 0 and not r["hasMore"]:
            break
        # 每页落盘
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(json.dumps(list(state["comments"].values()),
                                  ensure_ascii=False), encoding="utf-8")

    OUT.write_text(json.dumps(list(state["comments"].values()),
                              ensure_ascii=False), encoding="utf-8")
    log(f"完成：{len(state['comments'])} 条 -> {OUT}")
    br.close()

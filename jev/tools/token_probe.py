"""匿名取 token 的可行性验证。

warmup() 已确认 feed 可通，所以推荐流里的笔记链接应该带新鲜
xsec_token。本脚本验证三件事：

  1. 推荐流能否提取到 (note_id, xsec_token)
  2. 用这个 token 能否打开详情页并拿到 noteDetailMap
  3. token 是否与 note_id 绑定（能否用一个 token 打开别的笔记）

输出 out/token_probe.md
"""

from __future__ import annotations

import json
import sys
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT.parent / "xhs-cli" / "src"))

L: list[str] = []
LOG = ROOT / "out" / "_probe_progress.txt"


def emit(s: str = "") -> None:
    L.append(s)
    try:
        LOG.write_text("\n".join(L), encoding="utf-8")
    except Exception:  # noqa: BLE001
        pass


def finish(code: int = 0) -> None:
    (ROOT / "out" / "token_probe.md").write_text("\n".join(L), encoding="utf-8")
    print(f"written: out/token_probe.md")
    raise SystemExit(code)


try:
    from playwright.sync_api import sync_playwright
    from xhs_cli.anonymity import guest_cookies
    from xhs_cli.page import UA, warmup
except Exception:  # noqa: BLE001
    emit("导入失败：")
    emit("```")
    emit(traceback.format_exc())
    emit("```")
    finish(2)

emit("# 匿名取 token 可行性验证")
emit()

pw = br = None
try:
    pw = sync_playwright().start()
    br = pw.chromium.launch(headless=False, args=[
        "--disable-blink-features=AutomationControlled"])
    ctx = br.new_context(user_agent=UA, locale="zh-CN",
                          viewport={"width": 1440, "height": 900})
    gc = guest_cookies()
    ctx.add_cookies([{"name": k, "value": v,
                      "domain": ".xiaohongshu.com", "path": "/"}
                     for k, v in gc.items()])
    pg = ctx.new_page()
except Exception:  # noqa: BLE001
    emit("浏览器启动失败：")
    emit("```")
    emit(traceback.format_exc())
    emit("```")
    if br:
        br.close()
    if pw:
        pw.stop()
    finish(3)

emit("## 1. 预热")
emit()
try:
    ok = warmup(pg)
except Exception:  # noqa: BLE001
    emit("```")
    emit(traceback.format_exc())
    emit("```")
    ok = False
emit(f"- warmup(): **{ok}**")
emit(f"- 当前 URL: `{pg.url}`")
emit(f"- cookie: `{', '.join(sorted(c['name'] for c in ctx.cookies()))}`")
emit()

emit("## 2. 从推荐流提取 (note_id, xsec_token)")
emit()
emit("```")
emit(pg.evaluate("""() => {
    const s = window.__INITIAL_STATE__ || {};
    const f = s.feed;
    if (!f) return 'no s.feed';
    const raw = f.feeds && f.feeds._rawValue;
    const out = {keys: Object.keys(f), isArray: Array.isArray(raw),
                 len: (raw && raw.length) || 0, sample: null};
    if (raw && raw.length) {
        const it = raw[0];
        out.sampleKeys = Object.keys(it);
        out.sample = JSON.stringify(it).slice(0, 1200);
    }
    return JSON.stringify(out, null, 1);
}"""))
emit("```")
emit()

emit("## 3. 直接从 DOM 抓推荐卡片链接")
emit()
pg.wait_for_timeout(3000)
pg.evaluate("() => window.scrollBy(0, 800)")
pg.wait_for_timeout(2500)
emit("```")
emit(pg.evaluate("""() => {
    const as = Array.from(document.querySelectorAll('a[href*="/explore/"]'));
    const out = [];
    const seen = new Set();
    as.forEach(a => {
        const h = a.getAttribute('href') || '';
        const m = h.match(/\\/explore\\/([0-9a-f]{24})/);
        if (!m) return;
        const tk = (h.match(/xsec_token=([^&]+)/) || [])[1] || '';
        if (seen.has(m[1])) return;
        seen.add(m[1]);
        out.push(m[1].slice(0,8) + '  tok=' + (tk ? tk.slice(0,14)+'..' : '(none)'));
    });
    return out.length ? out.join('\\n') : '(0 个链接)';
}"""))
emit("```")
emit()

# ---- 4. 拿一个 token 试着打开详情页 ----
emit("## 4. 用推荐流的 token 打开详情页")
emit()
pairs = pg.evaluate("""() => {
    const out = []; const seen = new Set();
    document.querySelectorAll('a[href*="/explore/"]').forEach(a => {
        const h = a.getAttribute('href') || '';
        const m = h.match(/\\/explore\\/([0-9a-f]{24})[^#]*?xsec_token=([^&]+)/);
        if (m && !seen.has(m[1])) { seen.add(m[1]); out.push({id: m[1], token: m[2]}); }
    });
    return out;
}""")
emit(f"拿到 **{len(pairs)}** 个带 token 的链接")
emit()

if not pairs:
    emit("**推荐流也拿不到 token，匿名路径基本断了。**")
    if br:
        br.close()
    if pw:
        pw.stop()
    finish(1)

for p in pairs[:3]:
    url = (f"https://www.xiaohongshu.com/explore/{p['id']}"
           f"?xsec_token={p['token']}&xsec_source=pc_feed")
    try:
        pg.goto(url, wait_until="domcontentloaded", timeout=30000)
        pg.wait_for_timeout(3200)
    except Exception as e:  # noqa: BLE001
        emit(f"- `{p['id'][:8]}` 导航失败：{type(e).__name__}")
        continue
    if "/login" in pg.url:
        emit(f"- `{p['id'][:8]}` **重定向登录页**")
        continue
    d = pg.evaluate("""() => {
        const s = window.__INITIAL_STATE__;
        const m = s && s.note && s.note.noteDetailMap;
        if (!m) return {err: 'no_map'};
        const k = Object.keys(m)[0];
        const e = m[k] || {}; const n = e.note || {};
        const ii = n.interactInfo || {};
        const list = (e.comments||{}).list || [];
        return {
            id: k, hasMap: true,
            liked: ii.likedCount, collected: ii.collectedCount,
            cmtCnt: ii.commentCount, share: ii.shareCount,
            nComments: list.length,
            first: list[0] || null
        };
    }""")
    if d.get("err"):
        emit(f"- `{p['id'][:8]}` {d['err']}")
        continue
    emit(f"### `{p['id'][:8]}` ✅")
    emit()
    emit(f"- 点赞 **{d['liked']}** · 收藏 **{d['collected']}** · "
         f"评论 **{d['cmtCnt']}** · 分享 **{d['share']}**")
    emit(f"- 页面内联评论数：**{d['nComments']}**")
    fc = d.get("first") or {}
    if fc:
        emit(f"- 首条评论字段：`{', '.join(sorted(fc))}`")
        for k in ("create_time", "ip_location", "like_count",
                  "sub_comment_count"):
            emit(f"    - {k} = `{fc.get(k, '(缺失)')}`")
    emit()

# ---- 5. token 是否通用 ----
emit("## 5. token 是否与 note_id 绑定")
emit()
if len(pairs) >= 2:
    a, b = pairs[0], pairs[1]
    try:
        pg.goto(f"https://www.xiaohongshu.com/explore/{b['id']}"
                f"?xsec_token={a['token']}&xsec_source=pc_feed",
                wait_until="domcontentloaded", timeout=30000)
        pg.wait_for_timeout(3000)
        crossed = "/login" not in pg.url and pg.evaluate(
            "() => !!(window.__INITIAL_STATE__ && "
            "window.__INITIAL_STATE__.note && "
            "window.__INITIAL_STATE__.note.noteDetailMap)")
        emit(f"- 用 A 的 token 打开 B："
             f"{'**成功 —— token 可通用**' if crossed else '失败'}")
    except Exception as e:  # noqa: BLE001
        emit(f"- 跨笔记测试异常：{type(e).__name__}")
else:
    emit("- 链接不足 2 个，跳过")

emit()
if br:
    br.close()
if pw:
    pw.stop()
finish(0)
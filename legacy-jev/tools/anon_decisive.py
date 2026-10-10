"""决定性测试：匿名态到底能不能拿到数据 / 新鲜 token。

之前 token_probe.py 的结论不可靠 —— warmup() 返回 True 但页面其实
已被重定向到 /login（warmup 只检查 cookie 数量，不检查数据）。
本脚本每一步都显式验证「拿到数据了吗」，不再依赖间接指标。

测试矩阵（全部无 cookie）：
  1. 访客会话能否建立
  2. 无 token 的笔记详情页 -> noteDetailMap 有数据吗
  3. 各种 xsec_source 变体
  4. 首页/发现页里能否解析出 (note_id, xsec_token)
  5. 搜索页（匿名是否有权限）
  6. 老 token 是否真的失效

输出 out/anon_decisive.md
"""

from __future__ import annotations

import json
import re
import sys
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT.parent / "xhs-cli" / "src"))

L: list[str] = []
LOG = ROOT / "out" / "_decisive.txt"


def emit(s: str = "") -> None:
    L.append(s)
    try:
        LOG.write_text("\n".join(L), encoding="utf-8")
    except Exception:  # noqa: BLE001
        pass


def finish(code: int = 0) -> None:
    (ROOT / "out" / "anon_decisive.md").write_text("\n".join(L),
                                                    encoding="utf-8")
    print("written: out/anon_decisive.md")
    raise SystemExit(code)


try:
    from playwright.sync_api import sync_playwright
    from xhs_cli.anonymity import guest_cookies
    from xhs_cli.page import UA
except Exception:  # noqa: BLE001
    emit(traceback.format_exc())
    finish(2)

# 用一个确定存在的笔记
NID = "6a97b778000000002b012493"
OLD_TOKEN = "AB2olX6G5vOCtoxAlWN7WUEMDAFpp-_JLzFd_DHa-QVXM="

emit("# 匿名态决定性测试")
emit()
emit(f"目标笔记：`{NID}`")
emit()

pw = br = None
try:
    pw = sync_playwright().start()
    br = pw.chromium.launch(
        headless=True,
        args=["--disable-blink-features=AutomationControlled"])
    ctx = br.new_context(user_agent=UA, locale="zh-CN",
                          viewport={"width": 1440, "height": 900})
    gc = guest_cookies()
    ctx.add_cookies([{"name": k, "value": v,
                      "domain": ".xiaohongshu.com", "path": "/"}
                     for k, v in gc.items()])
    pg = ctx.new_page()
except Exception:  # noqa: BLE001
    emit(traceback.format_exc())
    if br:
        br.close()
    if pw:
        pw.stop()
    finish(3)


def probe_state() -> dict:
    """读当前页面的 __INITIAL_STATE__ 关键信息。"""
    try:
        return pg.evaluate("""() => {
            const s = window.__INITIAL_STATE__;
            if (!s) return {err: 'no_state'};
            const out = {topKeys: Object.keys(s).slice(0, 30)};
            const m = s.note && s.note.noteDetailMap;
            if (m && Object.keys(m).length) {
                const k = Object.keys(m)[0];
                const e = m[k] || {};
                const n = e.note || {};
                const ii = n.interactInfo || {};
                out.noteId = k;
                out.title = (n.title || '').slice(0, 30);
                out.liked = ii.likedCount;
                out.collected = ii.collectedCount;
                out.commentCnt = ii.commentCount;
                out.nComments = ((e.comments||{}).list||[]).length;
            } else {
                out.noteDetailMap = m ? Object.keys(m).length : 'absent';
            }
            const f = s.feed;
            if (f) {
                const raw = f.feeds && f.feeds._rawValue;
                out.feedLen = (raw && raw.length) || 0;
            }
            return out;
        }""")
    except Exception as e:  # noqa: BLE001
        return {"err": f"{type(e).__name__}: {str(e)[:80]}"}


def go(url: str, wait: int = 4000) -> tuple[int, str]:
    try:
        r = pg.goto(url, wait_until="domcontentloaded", timeout=30000)
        pg.wait_for_timeout(wait)
        return (r.status if r else 0), pg.url
    except Exception as e:  # noqa: BLE001
        return -1, f"{type(e).__name__}: {str(e)[:80]}"


# ---------------------------------------------------------------- 1
emit("## 1. 访客会话")
emit()
code, url = go("https://www.xiaohongshu.com/explore?channel_id=homefeed_recommend")
st = probe_state()
emit(f"- 首页 HTTP {code}")
emit(f"- 最终 URL 域名路径：`{url.split('?')[0]}`")
emit(f"- 是否登录页：**{'是' if '/login' in url else '否'}**")
emit(f"- feed 条数：**{st.get('feedLen', 'N/A')}**")
emit(f"- noteDetailMap：`{st.get('noteDetailMap', st.get('noteId', 'absent'))}`")
emit()
emit(f"- cookie 名单：`{', '.join(sorted(c['name'] for c in ctx.cookies()))}`")
emit()
emit("> 判据：`feedLen > 0` 或 `noteId` 存在才算匿名会话真的可用。")
emit()

# ---------------------------------------------------------------- 2
emit("## 2. 笔记详情页 —— 各种 URL 形态")
emit()
emit("每种都显式检查 noteDetailMap，而不是只看 HTTP 200。")
emit()
emit("| URL 形态 | HTTP | 落登录页 | noteDetailMap | 点赞 | 评论数 | 首批评论 |")
emit("| --- | ---: | :-: | --- | ---: | ---: | ---: |")
CASES = [
    ("无 token 无 source",
     f"https://www.xiaohongshu.com/explore/{NID}"),
    ("无 token + pc_feed",
     f"https://www.xiaohongshu.com/explore/{NID}?xsec_source=pc_feed"),
    ("discovery/item 无 token",
     f"https://www.xiaohongshu.com/discovery/item/{NID}"),
    ("老 token（9-30 签发）",
     f"https://www.xiaohongshu.com/explore/{NID}"
     f"?xsec_token={OLD_TOKEN}&xsec_source=pc_search"),
]
for label, u in CASES:
    code, url = go(u)
    st = probe_state()
    got = st.get("noteId")
    mapdesc = (f"`{got[:8]}`" if got else
               f"{st.get('noteDetailMap', st.get('err', '-'))}")
    emit(f"| {label} | {code} | "
         f"{'**是**' if '/login' in url else '否'} | {mapdesc} | "
         f"{st.get('liked', '-')} | {st.get('commentCnt', '-')} | "
         f"{st.get('nComments', '-')} |")
emit()

# ---------------------------------------------------------------- 3
emit("## 3. 能否解析出新鲜 (note_id, xsec_token)")
emit()
code, url = go("https://www.xiaohongshu.com/explore?channel_id=homefeed_recommend")
pg.wait_for_timeout(2000)
pg.evaluate("() => window.scrollBy(0, 900)")
pg.wait_for_timeout(2500)
found = pg.evaluate("""() => {
    const out = []; const seen = new Set();
    document.querySelectorAll('a[href]').forEach(a => {
        const h = a.getAttribute('href') || '';
        const m = h.match(/\\/(?:explore|discovery\\/item)\\/([0-9a-f]{24})/);
        if (!m) return;
        const tk = (h.match(/xsec_token=([^&]+)/) || [])[1] || '';
        const k = m[1];
        if (seen.has(k)) return;
        seen.add(k);
        out.push({id: k, token: tk});
    });
    return out;
}""")
emit(f"- DOM 里 `/explore/` 链接：**{len(found)}** 条")
emit(f"- 其中带 xsec_token：**{sum(1 for f in found if f['token'])}** 条")
emit()
if found:
    emit("| note | token |")
    emit("| --- | --- |")
    for f in found[:8]:
        emit(f"| `{f['id'][:8]}` | "
             f"`{(f['token'][:22] + '..') if f['token'] else '(无)'}` |")
    emit()
    if any(f["token"] for f in found):
        emit("**🎉 匿名态能拿到新鲜 token！**")
    else:
        emit("有链接但**没有 token** —— 拿不到凭证。")
emit()

# ---------------------------------------------------------------- 4
emit("## 4. 搜索页（匿名是否有权限）")
emit()
code, url = go("https://www.xiaohongshu.com/search_result?keyword=%E9%9B%85%E8%AF%97%E5%85%B0%E8%8E%B1")
pg.wait_for_timeout(3000)
emit(f"- HTTP {code} ·落登录页：**{'是' if '/login' in url else '否'}**")
emit(f"- 页面标题含「登录后」："
     f"**{'是' if '登录后查看' in pg.content() else '否'}**")
emit()

# ---------------------------------------------------------------- 5
emit("## 5. 结论")
emit()
any_work = False
for label, u in CASES:
    code, url = go(u, wait=4500)
    st = probe_state()
    if st.get("noteId"):
        emit(f"✅ **{label}** 可用：拿到 `{st['noteId'][:8]}`"
             f" 赞{st.get('liked')} 藏{st.get('collected')} "
             f"评{st.get('commentCnt')} 首批评论{st.get('nComments')}")
        any_work = True
if not any_work:
    emit("❌ **所有形态都没拿到笔记数据。**")
emit()
emit("### token 是否必需")
emit()
emit("如果「无 token」也能拿到 noteDetailMap，")
emit("说明 token 只是入口凭证而非数据凭证，匿名完全可行。")
emit("如果只有带 token 的能拿到 —— 而老 token 又已过期 ——")
emit("那匿名路径必须先解决「怎么拿新 token」。")
emit()

if br:
    br.close()
if pw:
    pw.stop()
finish(0)
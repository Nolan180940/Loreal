"""匿名实测：xhs-cli 到底能拿到哪些字段。

流程（全部匿名，无任何 cookie）：
  1. 访问 explore 首页预热，让平台种下访客会话
  2. 访问搜索页，从渲染后的结果里提取新鲜 note_id + xsec_token
  3. 逐篇打开详情页，dump noteDetailMap 里所有 key
  4. dump comments.list 里所有字段
输出 out/anon_fields.md
"""

from __future__ import annotations  # noqa: E402

import json
import sys
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "xhs-cli" / "src"))

try:
    from playwright.sync_api import sync_playwright  # noqa: E402
    from xhs_cli.anonymity import guest_cookies  # noqa: E402
    from xhs_cli.page import UA, warmup  # noqa: E402
except Exception:  # noqa: BLE001
    traceback.print_exc()
    raise SystemExit(2)

L: list[str] = []
LOG = Path(__file__).resolve().parents[1] / "out" / "_anon_progress.txt"


def emit(s: str = "") -> None:
    L.append(s)
    try:
        LOG.write_text("\n".join(L), encoding="utf-8")
    except Exception:  # noqa: BLE001
        pass


def cookies_safe(ctx) -> dict:
    return {c["name"]: c["value"] for c in ctx.cookies()}


pw = None
br = None
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
    emit("# 匿名实测：xhs-cli 能力边界")
    emit()
    emit("**浏览器启动失败：**")
    emit()
    emit("```")
    emit(traceback.format_exc())
    emit("```")
    if br:
        br.close()
    if pw:
        pw.stop()
    Path("out/anon_fields.md").write_text("\n".join(L), encoding="utf-8")
    raise SystemExit(3)

emit("# 匿名实测：xhs-cli 能力边界")
emit()
emit("## 1. 预热（访客会话）")
emit()
try:
    ok = warmup(pg)
    emit(f"- warmup(): **{ok}**")
except Exception:  # noqa: BLE001
    emit("- warmup() 抛异常：")
    emit()
    emit("```")
    emit(traceback.format_exc())
    emit("```")
    ok = False

c = cookies_safe(ctx)
emit(f"- cookie 数量：{len(c)}")
emit(f"- cookie 名单：`{', '.join(sorted(c))}`")
emit()

# ---- 2. 取 token ----
KEYWORDS = ["雅诗兰黛 小棕瓶"]
emit("## 2. 取token")
emit()
found: list[dict] = []
for kw in KEYWORDS:
    try:
        pg.goto("https://www.xiaohongshu.com/search_result?keyword="
                + kw.replace(" ", "%20"),
                wait_until="domcontentloaded", timeout=30000)
    except Exception as e:  # noqa: BLE001
        emit(f"- 搜索 `{kw}` 失败：{type(e).__name__}")
        continue
    pg.wait_for_timeout(4500)
    # 搜索页可能滚到下方才渲染出卡片
    pg.evaluate("() => window.scrollBy(0, 600)")
    pg.wait_for_timeout(2000)
    found = pg.evaluate("""() => {
        const out = [];
        const seen = new Set();
        document.querySelectorAll('a[href*="/explore/"]').forEach(a => {
            const href = a.getAttribute('href') || '';
            const m = href.match(/\\/explore\\/([0-9a-f]{24})[^#]*?xsec_token=([^&]+)/);
            if (m && !seen.has(m[1])) {
                seen.add(m[1]);
                out.push({id: m[1], token: m[2], href});
            }
        });
        return out;
    }""")
    if not found:
        # 兜底：从 __INITIAL_STATE__ 的搜索结果里捞
        found = pg.evaluate("""() => {
            const s = window.__INITIAL_STATE__ || {};
            const raw = (s.search && s.search.feeds &&
                         s.search.feeds._rawValue) || [];
            const out = [];
            (Array.isArray(raw) ? raw : []).forEach(it => {
                const c = it && it.noteCard && it.noteCard.interactInfo
                          ? it : null;
                const id = c && c.id;
                const link = (c && c.noteCard) ? '' : '';
            });
            return out;
        }""")
    if found:
        emit(f"- 搜索 `{kw}` 拿到 **{len(found)}** 条带 token 的链接")
        break
    emit(f"- 搜索 `{kw}` 拿到 0 条")

emit()
if not found:
    emit("搜索页被拦（匿名访客无搜索权限）。")
    emit()
    emit("改用已知 note_id 走详情页 —— 验证 token 是否还有效。")
    emit()
    KNOWN = [
        ("6a97b778000000002b012493",
         "AB2olX6G5vOCtoxAlWN7WUEMDAFpp-_JLzFd_DHa-QVXM="),
        ("693abce3000000001e03b9bd",
         "ABcIzAIpURB-vkVd36gxOmzIuvPv7bQrKNjuk244UUUeA="),
    ]
    for nid, tk in KNOWN:
        found.append({"id": nid, "token": tk})
    emit(f"改用 {len(found)} 个存量 token 继续探测。")
    emit()
if not found:
    emit("**没有拿到任何 token，终止探测。**")
    Path("out/anon_fields.md").write_text("\n".join(L), encoding="utf-8")
    br.close(); pw.stop()
    raise SystemExit(1)

seen, uniq = set(), []
for f in found:
    if f["id"] in seen:
        continue
    seen.add(f["id"])
    uniq.append(f)
emit(f"去重后：**{len(uniq)}** 篇可用")
emit()

# ---- 3. 逐篇打开详情页 ----
emit("## 3. 详情页字段（noteDetailMap）")
emit()
note_keys: set = set()
interact_keys: set = set()
cmt_keys: set = set()
opened = 0

for f in uniq[:2]:
    url = (f"https://www.xiaohongshu.com/explore/{f['id']}"
           f"?xsec_token={f['token']}&xsec_source=pc_search")
    try:
        pg.goto(url, wait_until="domcontentloaded", timeout=30000)
        pg.wait_for_timeout(3000)
    except Exception as e:  # noqa: BLE001
        emit(f"- `{f['id'][:8]}` 打开失败：{type(e).__name__}")
        continue
    if "/login" in pg.url:
        emit(f"- `{f['id'][:8]}` **被重定向到登录页**")
        continue
    opened += 1
    d = pg.evaluate("""() => {
        const s = window.__INITIAL_STATE__;
        const m = s && s.note && s.note.noteDetailMap;
        if (!m) return {err: 'no_map'};
        const k = Object.keys(m)[0];
        const e = m[k] || {};
        const n = e.note || {};
        return {
            id: k,
            note: Object.keys(n),
            interact: Object.keys(n.interactInfo || {}),
            comments: Object.keys(e.comments || {}),
            first: ((e.comments||{}).list||[])[0] || null,
            interactVals: n.interactInfo || {}
        };
    }""")
    if d.get("err"):
        emit(f"- `{f['id'][:8]}` {d['err']}")
        continue
    note_keys |= set(d["note"])
    interact_keys |= set(d["interact"])
    cmt_keys |= set(d["comments"])
    emit(f"### `{f['id'][:8]}`")
    emit()
    emit("**笔记字段**：")
    emit()
    emit("```")
    emit(", ".join(sorted(d["note"])))
    emit("```")
    emit()
    emit("**interactInfo（互动指标）**：")
    emit()
    emit("```")
    emit(", ".join(sorted(d["interact"])))
    emit()
    vals = d.get("interactVals") or {}
    for k in ("likedCount", "collectedCount", "commentCount", "shareCount"):
        if k in vals:
            emit(f"- {k} = **{vals[k]}**")
    emit()
    fc = d.get("first") or {}
    emit(f"**首条评论字段**（共 {len(d['comments'])} 个容器 key）：")
    emit()
    emit("```")
    emit(", ".join(sorted(fc.keys())) if fc else "(无评论)")
    emit("```")
    emit()
    if fc:
        for k in ("create_time", "ip_location", "like_count",
                  "sub_comment_count"):
            emit(f"- {k} = `{fc.get(k, '(缺失)')}`")
        ui = fc.get("user_info") or {}
        emit(f"- user_info键: `{', '.join(sorted(ui))}`")
    emit()

emit("## 4. 汇总：匿名拿到的字段全集")
emit()
emit("### 笔记层")
emit()
emit("```")
emit(", ".join(sorted(note_keys)) or "(未取到)")
emit("```")
emit()
emit("### 笔记互动指标")
emit()
emit("```")
emit(", ".join(sorted(interact_keys)) or "(未取到)")
emit("```")
emit()
emit("### 评论容器")
emit()
emit("```")
emit(", ".join(sorted(cmt_keys)) or "(未取到)")
emit("```")

br.close()
pw.stop()
Path("out/anon_fields.md").write_text("\n".join(L), encoding="utf-8")
print(f"written: out/anon_fields.md (opened={opened})")
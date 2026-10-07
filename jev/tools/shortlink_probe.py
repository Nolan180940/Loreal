"""匿名采集 —— 用短链展开拿新鲜 token，再逐篇取数。

短链是唯一已知匿名可用的入口（share.py 文档记载：
「短链跳转本身匿名可用」）。本脚本：
  1. 读 urls.txt，对每条 URL 判断是否短链
  2. 短链 → 匿名浏览器展开 →拿新鲜 note_id + xsec_token
  3. 长链（token 已过期）→ 记录，标记失效
  4. 汇总：哪些能救、哪些彻底废

输出 out/shortlink_probe.md
"""

from __future__ import annotations

import json
import sys
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT.parent / "xhs-cli" / "src"))

L: list[str] = []
LOG = ROOT / "out" / "_sl_progress.txt"


def emit(s: str = "") -> None:
    L.append(s)
    try:
        LOG.write_text("\n".join(L), encoding="utf-8")
    except Exception:  # noqa: BLE001
        pass


def finish(code: int = 0) -> None:
    (ROOT / "out" / "shortlink_probe.md").write_text("\n".join(L),
                                                      encoding="utf-8")
    print("written: out/shortlink_probe.md")
    raise SystemExit(code)


try:
    from playwright.sync_api import sync_playwright
    from xhs_cli.anonymity import guest_cookies
    from xhs_cli.page import UA
    from xhs_cli.share import is_short_link
except Exception:  # noqa: BLE001
    emit("导入失败：")
    emit("```")
    emit(traceback.format_exc())
    emit("```")
    finish(2)

# ---- 读 urls.txt ----
URL_FILE = ROOT.parent / "urls.txt"
urls: list[str] = []
for raw in URL_FILE.read_text(encoding="utf-8").splitlines():
    s = raw.strip()
    if s and not s.startswith("#"):
        urls.append(s)

shorts = [u for u in urls if is_short_link(u)]
longs = [u for u in urls if not is_short_link(u)]

emit("# 短链展开探测（匿名）")
emit()
emit(f"- `urls.txt` 共 **{len(urls)}** 条")
emit(f"- 短链：**{len(shorts)}** 条")
emit(f"- 长链（带 token）：**{len(longs)}** 条")
emit()

if not shorts:
    emit("**没有短链可展开。**")
    emit()
    emit("urls.txt 里全是 `xsec_token=` 长链，且都签发于 2026-09-30，")
    emit("已确认过期。当前无任何匿名入口可用。")
    finish(1)

emit("## 逐条展开短链")
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

ok_list = []
for i, u in enumerate(shorts, 1):
    emit(f"### [{i}/{len(shorts)}] `{u}`")
    emit()
    try:
        resp = pg.goto(u, wait_until="domcontentloaded", timeout=30000)
        pg.wait_for_timeout(2600)
    except Exception as e:  # noqa: BLE001
        emit(f"- 失败：{type(e).__name__}")
        emit()
        continue
    final = pg.url
    code = resp.status if resp else 0
    has_token = "xsec_token=" in final
    on_login = "/login" in final
    emit(f"- HTTP {code} · 最终 URL 长度 {len(final)}")
    emit(f"- {'**落到登录页**' if on_login else '未跳登录'}")
    if has_token:
        emit(f"- `{final[:150]}`")
        ok_list.append({"src": u, "final": final})
    emit()

emit("## 汇总")
emit()
emit(f"- 短链 {len(shorts)} 条，成功展开 **{len(ok_list)}** 条")
emit()

if br:
    br.close()
if pw:
    pw.stop()

if ok_list:
    out = ROOT / "out" / "fresh_urls.txt"
    out.write_text("\n".join(x["final"] for x in ok_list) + "\n",
                   encoding="utf-8")
    emit(f"新鲜 URL 已写入 `{out}`")
    emit()
    emit("下一步：拿这些新 token 打开详情页，验证能否拿到 noteDetailMap。")
    finish(0)

emit("**短链也无法匿名展开 —— 匿名路径全部不通。**")
finish(1)
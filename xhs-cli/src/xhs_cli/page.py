"""匿名页面抓取。

用 ``curl_cffi`` 伪装 Chrome 直连，不带任何登录态。分享链接的详情页 HTML 里
内联了 ``window.__INITIAL_STATE__``，其中包含：

- 完整正文（``note.desc`` / ``note.title`` / ``note.tagList``）
- 互动数（``note.interactInfo``：点赞/评论/收藏/分享）
- 图片清单（``note.imageList``，含 ``urlDefault`` 与原始尺寸）
- **首批评论**（``comments.list``，实测 10 条）

已实测的关键事实（决定本模块设计）：

1. **纯 HTTP 抓不到笔记数据**。匿名请求拿到的 HTML 里
   ``__INITIAL_STATE__`` 只有 ~12KB 空壳，**不含** ``noteDetailMap``
   （即没有正文、没有图片、没有评论）。必须让浏览器执行 JS 渲染。
2. 浏览器渲染后，``note.noteDetailMap[note_id]`` 里包含完整正文、
   互动数、图片清单，以及**首批评论** ``comments.list``（实测 10 条）。
3. ``comment/page`` 接口匿名可用，但**每会话仅 1 次**（第 2 页必定 461）。
   因此首批评论优先从渲染后的状态取，不额外发请求。
4. ``comment/sub/page``（楼中楼）匿名首请求即 461 → 只能拿页面内联的
   ``sub_comments``（实测覆盖率约 84.5%）。

所以本模块走 **Playwright 渲染 + 状态抽取** 路线，而不是纯 HTTP 解析。
"""

from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass
from typing import Any

from .anonymity import assert_anonymous, guest_cookies

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)

# 小红书把状态挂在 window.__INITIAL_STATE__= {...}</script> 里。
# 该对象含大量 undefined，需要先归一化才能 json.loads。
_STATE_RE = re.compile(
    r"window\.__INITIAL_STATE__\s*=\s*(\{.*?\})\s*</script>", re.S
)


class FetchError(RuntimeError):
    """页面抓取失败。``kind`` 用于分类统计。"""

    def __init__(self, message: str, kind: str = "unknown") -> None:
        super().__init__(message)
        self.kind = kind


@dataclass
class PageData:
    """分享页解析结果。"""

    note_id: str
    title: str
    desc: str
    tags: list[str]
    liked: str
    collected: str
    comment_count: str
    share_count: str
    author: str
    author_id: str
    time_ms: int
    ip_location: str
    images: list[dict]
    comments: list[dict]
    has_more: bool
    cursor: str


def _make_session(proxy: str | None = None):
    """curl_cffi 会话（保留给将来可能的直连场景）。"""
    from curl_cffi import requests as cr

    return cr.Session(impersonate="chrome", proxy=proxy)


def normalize_state(raw: str) -> dict:
    """把 SSR 里的 JS 字面量转成可解析的 JSON。

    小红书会输出 ``undefined`` / ``new Map([])`` 等非 JSON 语法。
    """
    text = raw
    # new Map([]) 是 SSR 渲染 Map 的惯用写法，等价于空数组
    text = text.replace("new Map([])", "[]")
    text = re.sub(r"\bundefined\b", "null", text)
    # 去掉尾随逗号
    text = re.sub(r",(\s*[}\]])", r"\1", text)
    return json.loads(text)


def extract_state(html: str) -> dict:
    """从 HTML 中抽出 ``__INITIAL_STATE__``。"""
    m = _STATE_RE.search(html)
    if not m:
        raise FetchError("HTML 中没有 __INITIAL_STATE__", kind="no_state")
    try:
        return normalize_state(m.group(1))
    except Exception as exc:  # noqa: BLE001
        raise FetchError(f"__INITIAL_STATE__ 解析失败: {exc}", kind="bad_state") from exc


def _dig(state: dict, note_id: str) -> dict:
    """定位 ``note.noteDetailMap[note_id]``。"""
    detail = (
        state.get("note", {}).get("noteDetailMap") or state.get("noteDetailMap") or {}
    )
    if not isinstance(detail, dict) or not detail:
        raise FetchError("noteDetailMap 为空（无 token 或页面未渲染）", kind="empty_note")

    # 服务端渲染通常直接以 note_id 为键；退化时取最后一个条目。
    entry = detail.get(note_id)
    if entry is None:
        for value in detail.values():
            if isinstance(value, dict) and "note" in value:
                entry = value
                break
    if entry is None:
        raise FetchError("noteDetailMap 中找不到目标笔记", kind="no_entry")
    return entry


def parse_page(html: str, note_id: str) -> PageData:
    """解析分享页 HTML，产出 :class:`PageData`。"""
    state = extract_state(html)
    entry = _dig(state, note_id)
    note = entry.get("note") or {}
    comments_box = entry.get("comments") or {}
    interact = note.get("interactInfo") or {}
    user = note.get("user") or {}

    images = []
    for item in note.get("imageList") or []:
        url = item.get("urlDefault") or item.get("url") or ""
        if not url:
            continue
        images.append(
            {
                "url": url,
                "width": item.get("width"),
                "height": item.get("height"),
            }
        )

    return PageData(
        note_id=str(note.get("noteId") or note_id),
        title=str(note.get("title") or ""),
        desc=str(note.get("desc") or ""),
        tags=[t.get("name", "") for t in (note.get("tagList") or []) if t.get("name")],
        liked=str(interact.get("likedCount") or ""),
        collected=str(interact.get("collectedCount") or ""),
        comment_count=str(interact.get("commentCount") or ""),
        share_count=str(interact.get("shareCount") or ""),
        author=str(user.get("nickName") or user.get("nickname") or ""),
        author_id=str(user.get("userId") or user.get("user_id") or ""),
        time_ms=int(note.get("time") or 0),
        ip_location=str(note.get("ipLocation") or ""),
        images=images,
        comments=list(comments_box.get("list") or []),
        has_more=bool(comments_box.get("hasMore")),
        cursor=str(comments_box.get("cursor") or ""),
    )


def fetch_share_page(
    url: str,
    note_id: str,
    *,
    proxy: str | None = None,
    timeout: int = 25,
    retries: int = 2,
    retry_wait: float = 3.0,
    browser=None,
    page=None,
    navigated: bool = False,
    engine: str = "chromium",
) -> PageData:
    """匿名抓取分享页（浏览器渲染）并解析。

    ``navigated=True`` 表示页面已因短链展开而停在目标详情页，直接抽取不再跳转。
    """
    if page is not None:
        return _fetch_via_page(page, url, note_id, timeout=timeout,
                               retries=retries, navigated=navigated)

    with _anon_browser(proxy, engine=engine) as (br, pg):
        return _fetch_via_page(pg, url, note_id, timeout=timeout,
                               retries=retries, navigated=navigated)


def _anon_browser(proxy: str | None = None, with_guest_cookies: bool = True,
                  engine: str = "chromium", headless: bool = True):
    """创建**全新、无登录态**的浏览器上下文（文档见模块顶部设计说明）。"""
    from playwright.sync_api import sync_playwright

    pw = sync_playwright().start()
    launch: dict = {"headless": headless}
    if proxy:
        p = proxy if "://" in proxy else f"http://{proxy}"
        launch["proxy"] = {"server": p}
    if engine == "chrome":
        # 本机 Chrome：TLS 指纹与真人一致。注意仍是全新隔离上下文，
        # 不加载用户 profile，不携带任何登录态。
        launch["channel"] = "chrome"
        launch.setdefault("args", []).append(
            "--disable-blink-features=AutomationControlled")
    br = pw.chromium.launch(**launch)
    ctx = br.new_context(
        user_agent=UA,
        locale="zh-CN",
        viewport={"width": 1440, "height": 900},
    )
    if with_guest_cookies:
        gc = guest_cookies()
        assert_anonymous(cookies=gc)     # 硬约束：不得含登录态
        ctx.add_cookies([
            {
                "name": k,
                "value": v,
                "domain": ".xiaohongshu.com",
                "path": "/",
            }
            for k, v in gc.items()
        ])
    pg = ctx.new_page()
    return _BrowserCtx(pw, br, ctx, pg)


# 平台首页：匿名访问后页面脚本会自行种下访客会话与反爬 cookie
# （sec_poison_id / websectiga / gid 等）。没有这些，
# noteDetailMap 的 key 会被渲染成字符串 "undefined"，笔记数据为空。
_WARMUP_URL = "https://www.xiaohongshu.com/explore?channel_id=homefeed_recommend"


def warmup(page, timeout_ms: int = 25000) -> bool:
    """访问一次首页，让平台把访客 cookie 补齐。

    Returns
    -------
    bool
        True 表示已拿到访客会话（含 ``web_session`` 之类的访客票），
        False 表示仍是空壳状态。
    """
    try:
        page.goto(_WARMUP_URL, wait_until="domcontentloaded", timeout=timeout_ms)
    except Exception:  # noqa: BLE001
        return False

    # 等页面脚本把 cookie 写完
    for _ in range(12):
        page.wait_for_timeout(500)
        try:
            has_state = page.evaluate(
                "() => { const f = window.__INITIAL_STATE__;"
                " const d = f && f.feed && f.feed.feeds && f.feed.feeds._rawValue;"
                " return !!(d && d.length); }"
            )
        except Exception:  # noqa: BLE001
            has_state = False
        if has_state:
            break

    try:
        n = len(page.context.cookies())
    except Exception:  # noqa: BLE001
        return False
    return n > 0


class _BrowserCtx:
    """浏览器上下文包装，保证 with 退出时全部资源被释放。"""

    def __init__(self, pw, br, ctx, page) -> None:
        self.pw, self.br, self.ctx, self.page = pw, br, ctx, page

    def __enter__(self):
        return self.br, self.page

    def __exit__(self, *exc) -> None:
        for closer in (self.ctx.close, self.br.close, self.pw.stop):
            try:
                closer()
            except Exception:
                pass
        return False


# 在页面上下文里执行的抽取脚本：把 __INITIAL_STATE__ 摊平成可序列化对象。
_EXTRACT_JS = """
() => {
  const st = window.__INITIAL_STATE__ || {};
  const detail = (st.note && st.note.noteDetailMap) || st.noteDetailMap || {};
  const keys = Object.keys(detail);
  if (!keys.length) return {ok: false, reason: 'empty_noteDetailMap'};
  const entry = detail[keys[0]] || {};
  const note = entry.note || {};
  const box = entry.comments || {};
  return {
    ok: true,
    noteId: note.noteId || keys[0],
    title: note.title || '',
    desc: note.desc || '',
    tags: (note.tagList || []).map(t => t.name || '').filter(Boolean),
    liked: String(((note.interactInfo||{}).likedCount) || ''),
    collected: String(((note.interactInfo||{}).collectedCount) || ''),
    commentCount: String(((note.interactInfo||{}).commentCount) || ''),
    shareCount: String(((note.interactInfo||{}).shareCount) || ''),
    author: ((note.user||{}).nickName) || ((note.user||{}).nickname) || '',
    authorId: ((note.user||{}).userId) || ((note.user||{}).user_id) || '',
    time: note.time || 0,
    ipLocation: note.ipLocation || '',
    images: (note.imageList || [])
      .map(i => ({url: i.urlDefault || i.url || '', width: i.width, height: i.height}))
      .filter(i => i.url),
    comments: box.list || [],
    hasMore: !!box.hasMore,
    cursor: String(box.cursor || ''),
  };
}
"""


def _fetch_via_page(page, url: str, note_id: str, *,
                    timeout: int, retries: int,
                    navigated: bool = False) -> PageData:
    """在已打开的页面里渲染并抽取数据。

    ``navigated=True`` 时跳过 ``goto``（短链展开后页面已在目标详情页）。
    """
    ms = timeout * 1000
    last = None
    for attempt in range(retries + 1):
        try:
            resp = None if navigated else page.goto(
                url, wait_until="domcontentloaded", timeout=ms)

            # 关键：token 失效时平台会 302 到 /login，页面依然"加载成功"。
            # 不显式判定就会误认为「拿到空数据 = 采集成功」。
            if page.url.rstrip("/").endswith("/login") or "/login?" in page.url:
                raise FetchError(
                    "被重定向到登录页：xsec_token 已失效（分享链接的 token 有效期约数小时）",
                    kind="token_expired",
                )
            if resp is not None and resp.status == 404:
                raise FetchError("HTTP 404：链接或 token 已失效", kind="not_found")

            # 等 __INITIAL_STATE__ 里出现 noteDetailMap
            for _ in range(int(timeout / 0.5)):
                has = page.evaluate(
                    "() => { const st = window.__INITIAL_STATE__ || {};"
                    " const d = (st.note && st.note.noteDetailMap) || st.noteDetailMap;"
                    " return !!(d && Object.keys(d).length); }"
                )
                if has:
                    break
                page.wait_for_timeout(500)
            else:
                text = page.evaluate("() => document.body ? document.body.innerText : ''")
                if "页面不见了" in text or "Page Isn't Available" in text:
                    raise FetchError("页面 404：token 失效或链接错误", kind="not_found")
                raise FetchError("渲染超时：noteDetailMap 未出现", kind="no_state")

            data = page.evaluate(_EXTRACT_JS)
            if not data.get("ok"):
                raise FetchError("noteDetailMap 为空（token 失效或被限流）",
                                 kind="empty_note")

            # 平台在 token 不被接受时会把 noteDetailMap 的键渲染成字符串
            # "undefined"，此时 note 对象为空 —— 等价于拿不到数据。
            if not data.get("noteId") or (
                not data.get("desc") and not data.get("images")
            ):
                raise FetchError(
                    "note 为空：xsec_token 未被接受（键被渲染为 undefined）",
                    kind="token_rejected",
                )

            return PageData(
                note_id=str(data["noteId"] or note_id),
                title=data["title"],
                desc=data["desc"],
                tags=list(data["tags"]),
                liked=data["liked"],
                collected=data["collected"],
                comment_count=data["commentCount"],
                share_count=data["shareCount"],
                author=data["author"],
                author_id=data["authorId"],
                time_ms=int(data["time"] or 0),
                ip_location=data["ipLocation"],
                images=list(data["images"]),
                comments=list(data["comments"]),
                has_more=bool(data["hasMore"]),
                cursor=data["cursor"],
            )
        except FetchError:
            raise
        except Exception as exc:  # noqa: BLE001
            last = exc
            if attempt < retries:
                page.wait_for_timeout(int(1500 * (attempt + 1)))
    raise FetchError(f"渲染失败: {last}", kind="network") from last


def download_images(
    urls: list[str],
    dest_dir,
    *,
    proxy: str | None = None,
    timeout: int = 30,
    page=None,
) -> list[dict[str, Any]]:
    """下载图片到 ``dest_dir``，命名为 ``01.jpg`` …

    已存在且非空的文件会跳过（断点续传）。返回每张图的结果记录。
    ``page`` 可选：传入浏览器页面时用浏览器上下文下载，与正文请求同源更稳。
    """
    from pathlib import Path

    dest = Path(dest_dir)
    dest.mkdir(parents=True, exist_ok=True)

    results: list[dict[str, Any]] = []
    for idx, url in enumerate(urls, 1):
        name = f"{idx:02d}.jpg"
        target = dest / name
        if target.is_file() and target.stat().st_size > 0:
            results.append({"url": url, "file": name, "status": "skipped",
                            "bytes": target.stat().st_size})
            continue
        data = None
        if page is not None:
            try:
                data = _download_via_browser(page, url)
            except Exception as exc:  # noqa: BLE001
                results.append({"url": url, "file": name,
                                "status": f"error:{type(exc).__name__}", "bytes": 0})
                continue
        if data:
            target.write_bytes(data)
            results.append({"url": url, "file": name, "status": "ok",
                            "bytes": len(data)})
        else:
            results.append({"url": url, "file": name, "status": "empty", "bytes": 0})
    return results


def _download_via_browser(page, url: str) -> bytes | None:
    """在页面上下文里下载图片字节（同源、免鉴权）。"""
    import base64

    b64 = page.evaluate(
        """async (u) => {
            const r = await fetch(u, {credentials: 'omit'});
            if (!r.ok) return null;
            const b = await r.arrayBuffer();
            let s = '';
            const u8 = new Uint8Array(b);
            const CH = 0x8000;
            for (let i = 0; i < u8.length; i += CH) {
              s += String.fromCharCode.apply(null, u8.subarray(i, i + CH));
            }
            return btoa(s);
        }""",
        url,
    )
    return base64.b64decode(b64) if b64 else None
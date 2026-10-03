"""分享链接归一化。

支持的输入形态（均为平台公开分享链接，匿名可访问）：

1. 手机短链：``https://xhslink.cn/o/<code>`` / ``xhslink.com``
2. PC 分享：``https://www.xiaohongshu.com/discovery/item/<note_id>?xsec_token=..&xsec_source=pc_share``
3. App 分享：``https://www.xiaohongshu.com/explore/<note_id>?...&xsec_source=app_share``

统一输出 :class:`ShareRef`：``note_id`` + ``token`` + ``source`` + 规范化 URL。

设计要点
--------
- **短链必须用浏览器展开**：``xhslink.cn/o/<code>`` 纯 HTTP 跳转会落到登录页
  （已实测），因此改用匿名浏览器跟随跳转，读最终 URL 里的 ``note_id`` 与
  **新鲜的** ``xsec_token``（有效期约数小时，必须用当前时刻的跳转结果）。
- **短链只解决「拿到新 URL」，不解决「读到数据」**：实测短链跳转本身匿名可用，
  但跳转后的详情页读取数据仍与直接访问详情页一样受登录态约束。
- **保留最终 URL 原样**：它带有 ``apptime`` / ``share_id`` 等平台签发参数，
  改写反而可能失效。
- **token 是关键**：无 token 的裸详情页匿名拿不到任何数据（已实测 404/空壳），
  所以缺 token 时直接判定为不可采集，而不是发出必然失败的请求。

匿名性
------
短链展开只用「匿名浏览器上下文」，不携带任何登录 cookie；
展开得到的 token 是平台刚签发的访客凭证，与任何账号无关。
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import parse_qs, urlparse

# 小红书笔记 ID 恒为 24 位小写 hex。
NOTE_ID_RE = re.compile(r"\b[0-9a-f]{24}\b")

# xsec_token：AB…（PC 搜索/推荐）与 CB…（分享）两类前缀都出现过，不做前缀限制。
TOKEN_RE = re.compile(r"(?:xsec_token=)([A-Za-z0-9_\-=]+)")

# 短链 code：xhslink 的 /o/<code> 或 /<code> 形态。
SHORT_CODE_RE = re.compile(r"xhslink\.(?:cn|com)/o/([A-Za-z0-9]+)")

VALID_SOURCES = frozenset({"pc_share", "app_share", "pc_search", "pc_feed"})


class UnsupportedLink(RuntimeError):
    """链接形态不受支持。"""


class ShortLinkError(RuntimeError):
    """短链展开失败（跳登录、失效、非笔记链接等）。"""


@dataclass(frozen=True)
class ShareRef:
    """归一化后的分享链接引用。"""

    note_id: str
    token: str
    source: str
    url: str
    is_short: bool = False

    @property
    def has_token(self) -> bool:
        return bool(self.token)


def _pick_token(query: str) -> str:
    qs = parse_qs(query)
    values = qs.get("xsec_token") or []
    return values[0] if values else ""


def _pick_source(query: str) -> str:
    qs = parse_qs(query)
    values = qs.get("xsec_source") or []
    for v in values:
        if v in VALID_SOURCES:
            return v
    return "pc_share"


def is_short_link(url: str) -> bool:
    """判断是否为 ``xhslink.cn/o/<code>`` 短链。"""
    return bool(SHORT_CODE_RE.search(url or ""))


def from_final_url(url: str) -> ShareRef:
    """从跳转后的最终 URL 构造引用。

    最终 URL 形如 ``/explore/<note_id>?...&xsec_source=app_share&xsec_token=CB...``
    """
    parsed = urlparse(url)
    m = NOTE_ID_RE.search(parsed.path)
    if not m:
        raise ShortLinkError(f"最终 URL 里没有 note_id: {url[:100]}")
    note_id = m.group(0)

    token = _pick_token(parsed.query)
    source = _pick_source(parsed.query)
    if not token:
        raise ShortLinkError(f"最终 URL 里没有 xsec_token: {url[:100]}")

    # 原样保留最终 URL：apptime / share_id 等签发参数不能丢
    return ShareRef(
        note_id=note_id, token=token, source=source,
        url=url, is_short=False,
    )


def normalize(url: str) -> ShareRef:
    """归一化分享链接；短链请先经 :func:`expand_short_link` 展开。

    Raises
    ------
    ShortLinkError
        传入的是短链——请改用短链展开流程。
    UnsupportedLink
        链接里找不到 24 位 note_id。
    """
    raw = (url or "").strip()
    if not raw:
        raise UnsupportedLink("空链接")

    if is_short_link(raw):
        raise ShortLinkError(
            "这是 xhslink 短链，请改用 expand_short_link() 展开")

    parsed = urlparse(raw if "//" in raw else f"https://{raw}")
    note_match = NOTE_ID_RE.search(parsed.path)
    if not note_match:
        raise UnsupportedLink(f"链接中找不到 note_id: {raw[:80]}")

    note_id = note_match.group(0)
    token = _pick_token(parsed.query)
    source = _pick_source(parsed.query)

    # 原样保留，避免丢失 apptime / share_id
    return ShareRef(
        note_id=note_id, token=token, source=source,
        url=raw if "//" in raw else f"https://{raw}",
        is_short=False,
    )


def expand_short_link(page, url: str, timeout_ms: int = 30000,
                     retries: int = 2) -> ShareRef:
    """用**匿名浏览器**跟随短链跳转，返回归一化引用。

    参数
    ----
    page
        已打开的匿名页面（复用同一上下文，避免每次重启浏览器）。
    url
        ``https://xhslink.cn/o/<code>`` 形态短链。
    retries
        短链跳登录偶发（平台对同一 IP 的短链解析有频率限制），失败时重试。

    失败
    ----
    ShortLinkError
        跳登录页、链接失效、或最终 URL 不是笔记页。
    """
    last_err = ""
    for attempt in range(retries + 1):
        try:
            page.goto(url.strip(), wait_until="domcontentloaded",
                      timeout=timeout_ms)
        except Exception as exc:  # noqa: BLE001
            last_err = f"跳转异常 {type(exc).__name__}: {exc}"
        else:
            # 等跳转链完成（短链是 302 → 详情页），最多 4 秒
            final = page.url
            for _ in range(10):
                if "/login" in final:
                    break
                if NOTE_ID_RE.search(final) and "xsec_token=" in final:
                    break
                page.wait_for_timeout(400)
                final = page.url

            if "/login" not in final and NOTE_ID_RE.search(final) \
                    and "xsec_token=" in final:
                # 页面已在详情页上，等渲染完成后调用方即可直接抽取
                try:
                    page.wait_for_load_state("domcontentloaded", timeout=5000)
                except Exception:  # noqa: BLE001
                    pass
                return from_final_url(final)

            if "/login" in final:
                last_err = "短链跳转到登录页"
            elif not NOTE_ID_RE.search(final):
                last_err = f"未跳转到笔记页: {final[:70]}"
            else:
                last_err = "最终 URL 缺少 xsec_token"

        if attempt < retries:
            page.wait_for_timeout(1500 * (attempt + 1))

    raise ShortLinkError(f"{last_err}（已重试 {retries} 次）")


def can_fetch(ref: ShareRef) -> tuple[bool, str]:
    """判断该引用能否匿名采集，返回 ``(是否可行, 原因)``。

    实测结论：
    - 无 token 的裸详情页匿名拿不到任何数据 → 不可行。
    - 短链必须先经 :func:`expand_short_link` 展开。
    """
    if ref.is_short:
        return False, "短链需先展开（用 expand_short_link）"
    if not ref.token:
        return False, "缺少 xsec_token：匿名访问无 token 详情页返回空壳/404"
    return True, "可直接匿名采集"
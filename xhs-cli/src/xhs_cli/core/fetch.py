"""核心层：HTTP 直连采集（不依赖浏览器）。

与 ``xhs_cli.page``（Playwright 路线）完全解耦。

**为什么另起一套而不是改 page.py**
--------------------------------
2026-10-10 实测：Playwright 的指纹被小红书风控识别，
headless 与有头真 Chrome 全部 302 跳登录页；
而 ``urllib`` + 手机 UA 直连 3/3 成功。
所以浏览器路线在当前风控下不可用，必须走 HTTP。

三条铁律（改动前先读）
----------------------
1. **必须手机 UA**。桌面 UA 会 302 到登录页，且 HTTP 状态仍是 200 ——
   不校验最终 URL 就发现不了。
2. **必须 urllib**。实测它的 TLS 指纹能过。
   ``requests`` / ``httpx`` / ``curl_cffi`` 未验证，不许替换。
3. **不许复用连接**（不开 Session、不加 keep-alive）。
   每次新建 Request 最接近"新用户首次访问"。

采集链路::

    短链 --urllib--> 完整URL(含新鲜xsec_token) --urllib--> HTML --正则--> 字段
"""

from __future__ import annotations

import urllib.error
import urllib.request

#: 唯一实测可用的 UA。配置化是为了应急时能快速切换，
#: 但**未验证的 UA 不许默认启用**。
MOBILE_UAS: tuple[str, ...] = (
    # iOS 17 Safari（2026-10-10 实测可用）
    ("Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
     "AppleWebKit/605.1.15 (KHTML, like Gecko) "
     "Version/17.0 Mobile/15E148 Safari/604.1"),
    # iOS 16 Safari（备用，未实测）
    ("Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) "
     "AppleWebKit/605.1.15 (KHTML, like Gecko) "
     "Version/16.6 Mobile/15E148 Safari/604.1"),
)

DEFAULT_UA = MOBILE_UAS[0]


class FetchError(RuntimeError):
    """采集失败。``kind`` 用于分类统计与上层降级判断。"""

    def __init__(self, message: str, kind: str = "unknown") -> None:
        super().__init__(message)
        self.kind = kind


def _headers(ua: str) -> dict[str, str]:
    return {
        "User-Agent": ua,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9",
    }


def expand(link: str, *, ua: str = DEFAULT_UA, timeout: int = 15) -> str:
    """展开短链，返回带 ``xsec_token`` 的完整 URL。

    ``urllib`` 自动跟随 302，最终 URL 在 ``response.url``。

    关键校验：展开结果里**必须**有 ``xsec_token``。
    桌面 UA 也会返回 200，但落点是登录页、没有 token ——
    只判状态码会静默拿到一个废 URL。
    """
    try:
        req = urllib.request.Request(link, headers=_headers(ua))
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            final = resp.url
            body_head = resp.read(200).decode("utf-8", "replace")
    except urllib.error.HTTPError as exc:
        raise FetchError(
            f"短链展开 HTTP {exc.code}", kind=f"expand_http_{exc.code}"
        ) from exc
    except Exception as exc:  # noqa: BLE001
        raise FetchError(
            f"短链展开失败: {type(exc).__name__}: {exc}",
            kind="expand_network") from exc

    if "/login" in final:
        raise FetchError(
            "短链被重定向到登录页（UA 可能被风控）", kind="expand_login")
    if "xsec_token=" not in final:
        raise FetchError(
            "展开结果里没有 xsec_token，无法读取详情页", kind="expand_no_token")
    # 有些短链 200 但 body 是登录页骨架
    if "登录" in body_head and "noteDetailMap" not in body_head:
        raise FetchError("短链返回登录页骨架", kind="expand_login_body")
    return final


def fetch_html(url: str, *, ua: str = DEFAULT_UA, timeout: int = 20) -> str:
    """抓取详情页 HTML。

    返回原始 HTML（含 ``\\u002F`` 转义），解析由 :mod:`xhs_cli.core.ssr` 负责。
    """
    try:
        req = urllib.request.Request(url, headers=_headers(ua))
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
    except urllib.error.HTTPError as exc:
        raise FetchError(
            f"详情页 HTTP {exc.code}（token 可能已失效）",
            kind=f"detail_http_{exc.code}") from exc
    except Exception as exc:  # noqa: BLE001
        raise FetchError(
            f"详情页抓取失败: {type(exc).__name__}: {exc}",
            kind="detail_network") from exc

    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return raw.decode("utf-8", "replace")


def fetch_image(url: str, *, ua: str = DEFAULT_UA,
                timeout: int = 20) -> bytes:
    """下载单张图片。CDN 公网可达，无需任何凭证。"""
    try:
        req = urllib.request.Request(url, headers={
            "User-Agent": ua, "Accept": "image/*,*/*;q=0.8",
            "Referer": "https://www.xiaohongshu.com/",
        })
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read()
    except Exception as exc:  # noqa: BLE001
        raise FetchError(
            f"图片下载失败: {type(exc).__name__}: {exc}",
            kind="image_network") from exc
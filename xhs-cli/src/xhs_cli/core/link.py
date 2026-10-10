"""链接归一化：把用户各种粘贴形态统一成 :class:`LinkRef`。

支持的用户输入（前端不做任何限制，后端全兼容）::

    https://xhslink.cn/o/9E8z07rhA16
    https://www.xiaohongshu.com/discovery/item/6ac9205b...?xsec_token=CB00...
    https://www.xiaohongshu.com/explore/6ac9205b...?xsec_token=...
    xiaohongshu.com/explore/6ac9205b...          # 缺协议
    https://www.xiaohongshu.com/explore/6ac9205b # 无 token（需展开）

设计原则
--------
**短链是首选形态。** 短链可以无限次重新展开拿到新 token，
而写死的长链 token 几小时后失效。所以调用方应优先存短链。
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import parse_qs, unquote, urlparse

#: 小红书笔记 ID：24 位小写 hex
NOTE_ID_RE = re.compile(r"\b([0-9a-f]{24})\b")

#: 短链域名
SHORT_HOSTS = ("xhslink.cn", "xhslink.com")

#: 长链路径前缀
LONG_PATHS = ("/explore/", "/discovery/item/")


class UnsupportedLink(RuntimeError):
    """链接形态不受支持。"""


@dataclass(frozen=True, slots=True)
class LinkRef:
    """归一化后的链接。"""

    raw: str                 # 用户原始输入（去空格后）
    kind: str                # "short" | "long"
    url: str                 # 规范化后的 URL
    note_id: str = ""        # 长链可直接解析；短链为空（要展开才知道）
    token: str = ""          # xsec_token；空表示需要展开

    @property
    def has_token(self) -> bool:
        return bool(self.token)

    @property
    def needs_expand(self) -> bool:
        """是否需要先展开才能抓。"""
        return self.kind == "short" or not self.token


def _clean(raw: str) -> str:
    s = (raw or "").strip().strip('"\'').strip()
    # 用户从 App 复制常带中文引导语，取其中的 URL
    if "http" not in s and "." in s:
        pass
    s = s.split()[0] if s and " " in s.strip() else s
    if not s.lower().startswith(("http://", "https://")):
        if "xhslink" in s or "xiaohongshu" in s:
            s = "https://" + s.lstrip("/")
    return s


def _parse(url: str) -> tuple[str, str]:
    """从长链 URL 抽 (note_id, token)。"""
    parsed = urlparse(url)
    m = NOTE_ID_RE.search(parsed.path) or NOTE_ID_RE.search(url)
    note_id = m.group(1) if m else ""
    qs = parse_qs(parsed.query)
    token = (qs.get("xsec_token") or [""])[0]
    return note_id, unquote(token)


def normalize(raw: str) -> LinkRef:
    """把用户输入归一化成 :class:`LinkRef`。

    Raises
    ------
    UnsupportedLink
        不是小红书笔记链接。
    """
    url = _clean(raw)
    if not url:
        raise UnsupportedLink("链接为空")

    host = urlparse(url).netloc.lower()

    # 短链
    if any(h in host for h in SHORT_HOSTS):
        return LinkRef(raw=raw, kind="short", url=url)

    # 长链
    if "xiaohongshu.com" in host:
        note_id, token = _parse(url)
        if not note_id:
            raise UnsupportedLink(f"链接里没有 24 位笔记 ID: {url[:80]}")
        return LinkRef(raw=raw, kind="long", url=url,
                       note_id=note_id, token=token)

    raise UnsupportedLink(
        f"不是小红书链接（支持 xhslink.cn/xhslink.com 短链 "
        f"和 xiaohongshu.com 长链）: {url[:80]}"
    )
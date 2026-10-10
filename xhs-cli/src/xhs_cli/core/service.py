"""核心层对外入口：一条命令从链接走到结构化数据。

用法::

    from xhs_cli.core import parse_link
    result = parse_link("https://xhslink.cn/o/9E8z07rhA16")

设计
----
**短链优先。** 短链每次展开都拿到**新签发的 token**，
而长链里写死的 token 几小时后失效。所以调用方应尽量保存短链。

降级链::

    HTTP 直连（主路径）
      ↓ 失败 / 字段全空
    重新展开短链换新 token，重试 1 次
      ↓ 仍失败
    指数退避 1s → 2s → 4s，最多 3 次
      ↓ 仍失败
    抛 FetchError（带 kind，上层据此决定返回什么错误码）
"""

from __future__ import annotations

import time
from typing import Any

from ..page import FetchError
from . import fetch, ssr
from .link import LinkRef, normalize

#: 退避序列（秒）
BACKOFF = (1.0, 2.0, 4.0)


def _sleep(seconds: float) -> None:
    if seconds > 0:
        time.sleep(seconds)


def _attempt(ref: LinkRef, ua: str) -> tuple[dict[str, Any], str]:
    """单次尝试。返回 (解析结果, 实际用的完整 URL)。

    短链每次尝试都重新展开 —— 这正是它能绕过 token 失效的原因。

    ``ua`` 必须往下传：之前这个参数没串进来，``parse_link(ua=...)``
    是死代码，整条链路只能用默认 UA。
    """
    if ref.needs_expand:
        url = fetch.expand(ref.raw, ua=ua)
    else:
        url = ref.url

    html = fetch.fetch_html(url, ua=ua)
    parsed = ssr.parse(html)
    ssr.validate(parsed)          # 空壳直接抛，触发重试
    return parsed, url


#: 需要**换 UA** 重试的 kind：这些都是「这个指纹被盯上了」。
#:
#: 注意与 461 区分：461 是评论分页接口的 IP + 接口滑窗配额，
#: 换 UA 没用。这里管的是短链展开被跳登录/验证码。
_UA_ROTATE_KINDS = ("expand_captcha", "expand_login", "expand_login_body")


def parse_link(raw: str, *, ua: str | None = None,
               retries: int = len(BACKOFF) + 1) -> dict[str, Any]:
    """解析一个小红书链接，返回完整结构化数据。

    Parameters
    ----------
    ua
        指定 UA。**不传则在 :data:`fetch.MOBILE_UAS` 之间轮换** ——
        单个 UA 被风控时换下一个继续，而不是原地重试到耗尽。

    Returns
    -------
    dict
        ``note`` / ``images`` / ``comments`` / ``declared`` / ``got`` /
        ``complete`` / ``note_id`` / ``url`` / ``ua`` / ``elapsed_ms``

    Raises
    ------
    UnsupportedLink
        链接形态不受支持。
    FetchError
        重试后仍然失败。
    """
    ref = normalize(raw)
    t0 = time.monotonic()
    last: Exception | None = None

    # 显式传 ua 就只用那一个（调试用）；否则轮换内置的全部 UA。
    uas = [ua] if ua else list(fetch.MOBILE_UAS)
    ua_idx = 0

    for attempt in range(max(1, retries)):
        used_ua = uas[ua_idx % len(uas)]
        try:
            parsed, url = _attempt(ref, used_ua)
            note = parsed["note"]
            return {
                "note": note,
                # images 提到顶层，调用方不用再钻一层
                "images": note.get("images") or [],
                "comments": parsed["comments"],
                "declared": parsed["declared"],
                "got": parsed["got"],
                "complete": parsed["complete"],
                "note_id": note.get("note_id") or ref.note_id,
                "url": url,
                "kind": ref.kind,
                "ua": used_ua,
                "elapsed_ms": int((time.monotonic() - t0) * 1000),
                "attempts": attempt + 1,
            }
        except FetchError as exc:
            last = exc
            # UA 被风控：换下一个指纹（不额外退避，成本很低）
            if exc.kind in _UA_ROTATE_KINDS:
                ua_idx += 1
            # token 类失败：重新展开短链换新 token（不额外退避，成本很低）
            if exc.kind.startswith(("detail_http", "expand_no_token")):
                ref = LinkRef(raw=ref.raw, kind="short", url=ref.raw)
            # 空数据：同样换 token 重试
            if exc.kind == "empty_data":
                ref = LinkRef(raw=ref.raw, kind="short", url=ref.raw)
            # 限流 / 网络：指数退避
            if attempt < retries - 1:
                _sleep(BACKOFF[min(attempt, len(BACKOFF) - 1)])
        except ssr.EmptyDataError as exc:
            last = exc
            # 空壳 -> 强制走短链重新展开
            ref = LinkRef(raw=ref.raw, kind="short", url=ref.raw)
            if attempt < retries - 1:
                _sleep(BACKOFF[min(attempt, len(BACKOFF) - 1)])

    raise FetchError(
        f"解析失败（{max(1, retries)} 次尝试）: {last}",
        kind="exhausted") from last


__all__ = ["parse_link", "FetchError", "normalize", "ssr", "fetch"]
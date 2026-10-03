"""匿名约束（硬约束）。

本工程的目标是「免登录、匿名」采集，因此必须保证：

1. 不读取任何 cookie 文件（含 ``.env`` / ``cookies.txt``）。
2. 不发送 ``web_session`` / ``id_token`` 等登录态字段。
3. 只用本地随机生成的访客标识（``a1`` / ``webId``），不复用任何账号信息。

这些检查在 :func:`assert_anonymous` 中集中实现，CLI 启动与每次请求前都会调用，
避免后续维护时不小心把登录态混进来。
"""

from __future__ import annotations

import binascii
import hashlib
import random
import time

# 绝不允许出现在请求头/请求体中的登录态字段。
FORBIDDEN_HEADERS = frozenset(
    {
        "cookie",
        "authorization",
        "id_token",
        "last_web_session",
    }
)

# 绝不允许出现在 cookie 字典里的登录态键。
FORBIDDEN_COOKIE_KEYS = frozenset(
    {
        "web_session",
        "last_web_session",
        "id_token",
    }
)

_A1_CHARSET = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"


class AnonymityViolation(RuntimeError):
    """检测到登录态痕迹时抛出。"""


def generate_a1() -> str:
    """本地生成访客 ``a1``（时间戳 + 随机串 + CRC32）。

    与浏览器行为一致，但不来自任何账号，所以与真实用户无关。
    """
    ts_hex = hex(int(time.time() * 1000))[2:]
    rand = "".join(random.choices(_A1_CHARSET, k=30))
    core = f"{ts_hex}{rand}5" + "0" + "000"
    crc = binascii.crc32(core.encode()) & 0xFFFFFFFF
    return (core + str(crc))[:52]


def generate_web_id(a1: str) -> str:
    """``webId = md5(a1)``，与平台约定一致。"""
    return hashlib.md5(a1.encode()).hexdigest()


def guest_cookies() -> dict[str, str]:
    """构造一组全新的访客 cookie（不含任何登录态）。"""
    a1 = generate_a1()
    return {
        "a1": a1,
        "webId": generate_web_id(a1),
        "webBuild": "6.56.3",
        "xsecappid": "xhs-pc-web",
        "loadts": str(int(time.time() * 1000)),
        "ets": str(int(time.time() * 1000) + 1),
    }


def assert_anonymous(
    headers: dict[str, str] | None = None,
    cookies: dict[str, str] | None = None,
) -> None:
    """校验请求不含登录态；有则抛 :class:`AnonymityViolation`。

    每次发请求前调用，保证「匿名」不是靠约定而是靠断言。
    """
    if headers:
        lowered = {str(k).lower() for k in headers}
        bad = lowered & FORBIDDEN_HEADERS
        if bad:
            raise AnonymityViolation(f"请求头含登录态字段: {sorted(bad)}")

    if cookies:
        bad_keys = {str(k) for k in cookies} & FORBIDDEN_COOKIE_KEYS
        if bad_keys:
            raise AnonymityViolation(f"cookie 含登录态字段: {sorted(bad_keys)}")
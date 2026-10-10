"""核心层：HTTP 直连采集（不依赖浏览器/Playwright）。

模块划分::

    link.py     链接归一化（短链/长链 -> LinkRef）
    fetch.py    urllib 直连 + 手机 UA（唯一实测可用的指纹）
    ssr.py      HTML -> 结构化字段（正则 + 括号配对 JSON）
    ssr_json.py 括号配对提取 comments 数组（精确路径）
    service.py  parse_link()：重试 + 换 token + 降级链

与 ``xhs_cli.page``（Playwright 路线）的关系
--------------------------------------------
完全独立。Playwright 路线在 2026-10-10 实测已被风控识别
（headless 与有头真 Chrome 全部 302 登录页），保留仅为人工兜底。
"""

from __future__ import annotations

from .fetch import FetchError
from .service import parse_link

__all__ = ["parse_link", "FetchError"]

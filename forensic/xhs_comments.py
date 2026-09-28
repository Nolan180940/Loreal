# -*- coding: utf-8 -*-
"""小红书评论区读取（复用 tools/.venv 里已装好的 xhshow 签名器）。

设计要点
--------
1. **不自己逆向签名**：`xhshow.Xhshow().sign_headers_get()` 已随
   XHS-Downloader 装好，直接复用。这样我们只依赖别人已验证的实现。
2. **优雅降级**：本模块运行在 `tools/.venv`（有 curl_cffi + xhshow）；
   若在项目主 `.venv`（无这些包）中 import，调用方应先检查 `available()`。
3. **不静默丢数据**：任何异常都写进 `errors` 字段，已取到的部分照常返回。
4. **风控友好**：默认带请求间隔、不并发、limit 封顶；官方文档明确警告
   高频请求会触发风控甚至封号。

接口规格（来自 tamnd/xiaohongshu-cli 源码）
------------------------------------------
    GET https://edith.xiaohongshu.com/api/sns/web/v2/comment/page
        ?note_id=&cursor=&top_comment_id=&image_formats=&xsec_token=
    GET .../api/sns/web/v2/comment/sub/page   (楼中楼, 加 root_comment_id)
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any

COMMENT_URL = "https://edith.xiaohongshu.com/api/sns/web/v2/comment/page"
SUB_COMMENT_URL = "https://edith.xiaohongshu.com/api/sns/web/v2/comment/sub/page"

ROOT = Path(__file__).resolve().parents[1]
ENV_FILE = ROOT / ".env"

# 官方示例同款；风控友好：不要开高并发
IMPERSONATE = "chrome146"
DEFAULT_SLEEP = 1.2      # 秒；官方工具内置延时机制
DEFAULT_TIMEOUT = 15
MAX_PAGES = 20          # 安全阀：单篇最多翻 20 页


# ---------- cookie 读取 ----------

def load_env_file(path: Path = ENV_FILE) -> dict[str, str]:
    """极简 .env 解析（不引 python-dotnet 依赖）。"""
    out: dict[str, str] = {}
    if not path.is_file():
        return out
    for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        out[k.strip()] = v.strip()
    return out


def get_cookie() -> str | None:
    """优先级：系统环境变量 > .env 文件。"""
    c = os.environ.get("XHS_COOKIE")
    if c:
        return c
    return load_env_file().get("XHS_COOKIE")


def cookie_has(cookie: str, name: str) -> bool:
    return any(p.strip().startswith(f"{name}=") for p in cookie.split(";"))


# ---------- 数据结构 ----------

@dataclass
class Comment:
    cid: str = ""
    uid: str = ""
    nickname: str = ""
    content: str = ""
    like_count: int = 0
    ip_location: str = ""
    create_time: int = 0
    sub_count: int = 0
    sub_comments: list["Comment"] = field(default_factory=list)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["time"] = (time.strftime("%Y-%m-%d %H:%M",
                                   time.localtime(self.create_time))
                     if self.create_time else "")
        return d


def _to_comment(rc: dict) -> Comment:
    ui = rc.get("user_info") or {}
    try:
        likes = int(str(rc.get("like_count") or "0").replace("+", "") or 0)
    except ValueError:
        likes = 0
    try:
        subs = int(str(rc.get("sub_comment_count") or "0") or 0)
    except ValueError:
        subs = 0
    return Comment(
        cid=str(rc.get("id") or ""),
        uid=str(ui.get("user_id") or ""),
        nickname=str(ui.get("nickname") or ""),
        content=str(rc.get("content") or ""),
        like_count=likes,
        ip_location=str(rc.get("ip_location") or ""),
        create_time=int(rc.get("create_time") or 0),
        sub_count=subs,
        sub_comments=[_to_comment(s) for s in (rc.get("sub_comments") or [])],
    )


def _unwrap(resp_json: Any) -> dict:
    """小红书统一用 {code, data, success} 信封。"""
    if isinstance(resp_json, dict):
        if "data" in resp_json:
            return resp_json.get("data") or {}
        return resp_json
    return {}


# ---------- 抓取器 ----------

def available() -> bool:
    """当前解释器是否具备依赖（curl_cffi + xhshow）。"""
    try:
        import curl_cffi  # noqa: F401
        from xhshow import Xhshow  # noqa: F401
        return True
    except Exception:
        return False


class XhsComments:
    """评论区抓取器。用法::

        async with XhsComments() as c:
            card = await c.fetch(note_id, xsec_token, deep=True)
    """

    def __init__(self, cookie: str | None = None, proxy: str | None = None,
                 sleep: float = DEFAULT_SLEEP, impersonate: str = IMPERSONATE,
                 timeout: int = DEFAULT_TIMEOUT):
        self.cookie = cookie or get_cookie()
        self.proxy = proxy
        self.sleep = sleep
        self.impersonate = impersonate
        self.timeout = timeout
        self.errors: list[str] = []
        self._en: Any = None
        self._client: Any = None

    # -- 生命周期 --
    def __enter__(self) -> "XhsComments":
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    def close(self) -> None:
        if self._client is not None:
            try:
                self._client.close()
            except Exception:
                pass
            self._client = None

    def _ensure(self) -> None:
        if self._en is not None:
            return
        from curl_cffi.requests import AsyncSession
        from xhshow import Xhshow

        if not self.cookie:
            raise RuntimeError(
                "未找到 XHS_COOKIE：请复制 .env.example 为 .env 并填入 cookie")
        self._en = Xhshow()
        cookies = {}
        for part in self.cookie.split(";"):
            if "=" in part:
                k, v = part.split("=", 1)
                cookies[k.strip()] = v.strip()
        self._client = AsyncSession(
            headers={"accept": "application/json, text/plain, */*",
                     "accept-language": "zh-CN,zh;q=0.9",
                     "referer": "https://www.xiaohongshu.com/"},
            cookies=cookies,
            timeout=self.timeout,
            verify=False,
            allow_redirects=True,
            proxy=self.proxy,
            impersonate=self.impersonate,
        )

    def _headers(self, url: str, params: dict) -> dict:
        return self._en.sign_headers_get(
            uri=url, cookies=self.cookie, params=params)

    # -- 主流程 --
    async def fetch(self, note_id: str, xsec_token: str = "",
                    deep: bool = True, limit: int = 0,
                    max_pages: int = MAX_PAGES) -> dict:
        """抓取一篇笔记的评论。

        limit <= 0 表示不限条数（仍受 max_pages 安全阀约束）。
        返回 card dict（见模块 docstring 的 schema 约定）。
        """
        self._ensure()
        if not xsec_token:
            self.errors.append("缺少 xsec_token，接口可能拒绝；建议从完整分享链接中提取")

        comments: list[Comment] = []
        cursor = ""
        pages = 0
        complete = False

        while pages < max_pages:
            params = {
                "note_id": note_id,
                "cursor": cursor,
                "top_comment_id": "",
                "image_formats": "jpg,webp,avif",
                "xsec_token": xsec_token,
            }
            try:
                resp = await self._client.get(
                    COMMENT_URL, params=params,
                    headers=self._headers(COMMENT_URL, params))
                payload = _unwrap(resp.json())
            except Exception as e:  # noqa: BLE001
                self.errors.append(f"第 {pages + 1} 页请求失败：{type(e).__name__}: {e}")
                break

            batch = [_to_comment(c) for c in (payload.get("comments") or [])]
            if not batch:
                complete = True
                break
            comments.extend(batch)
            pages += 1

            if deep:
                await self._fill_subs(batch)

            if limit and len(comments) >= limit:
                comments = comments[:limit]
                complete = False
                break
            if not payload.get("has_more") or not payload.get("cursor"):
                complete = True
                break
            cursor = str(payload.get("cursor"))
            await asyncio_sleep(self.sleep)

        card = {
            "note_id": note_id,
            "fetched": len(comments),
            "pages": pages,
            "complete": complete,
            "errors": self.errors,
            "cookie_mode": ("logged_in" if self.cookie
                            and cookie_has(self.cookie, "web_session")
                            else "anonymous"),
            "comments": [c.to_dict() for c in comments],
        }
        if limit and len(comments) >= limit:
            card["truncated_by_limit"] = True
        return card

    async def _fill_subs(self, batch: list[Comment]) -> None:
        """跟进楼中楼（仅当接口没内联返回时）。"""
        for c in batch:
            if c.sub_count > len(c.sub_comments) and c.sub_count > 0:
                try:
                    c.sub_comments.extend(await self._subs(c.cid))
                except Exception as e:  # noqa: BLE001
                    self.errors.append(f"楼中楼 {c.cid} 失败：{type(e).__name__}")
                await asyncio_sleep(self.sleep * 0.5)

    async def _subs(self, root_id: str, start: str = "") -> list[Comment]:
        out: list[Comment] = []
        cursor = start
        for _ in range(5):  # 楼中楼最多 5 页
            params = {
                "note_id": "", "root_comment_id": root_id, "num": "10",
                "cursor": cursor, "image_formats": "jpg,webp,avif",
                "top_comment_id": "", "xsec_token": "",
            }
            resp = await self._client.get(
                SUB_COMMENT_URL, params=params,
                headers=self._headers(SUB_COMMENT_URL, params))
            payload = _unwrap(resp.json())
            batch = [_to_comment(c) for c in (payload.get("comments") or [])]
            if not batch:
                break
            out.extend(batch)
            if not payload.get("has_more") or not payload.get("cursor"):
                break
            cursor = str(payload.get("cursor"))
            await asyncio_sleep(self.sleep * 0.5)
        return out


async def asyncio_sleep(sec: float) -> None:
    import asyncio
    await asyncio.sleep(sec)


# ---------- 便于从笔记链接提取 id / token ----------

def parse_note_ref(url: str) -> dict:
    """从笔记链接里抽 note_id 与 xsec_token。

    >>> parse_note_ref("https://www.xiaohongshu.com/explore/abc123?xsec_token=XYZ")
    {'note_id': 'abc123', 'xsec_token': 'XYZ'}
    """
    from urllib.parse import parse_qs, urlparse
    u = urlparse(url)
    segs = [s for s in u.path.split("/") if s]
    note_id = ""
    for s in segs:
        if s in ("explore", "discovery"):
            continue
        if len(s) >= 20 and all(ch.isalnum() for ch in s):
            note_id = s
            break
    q = parse_qs(u.query)
    return {
        "note_id": note_id or (segs[-1] if segs else ""),
        "xsec_token": (q.get("xsec_token") or [""])[0],
    }


if __name__ == "__main__":
    import asyncio
    import sys

    if len(sys.argv) < 2:
        print("用法: python -m forensic.xhs_comments <笔记链接> [xsec_token]")
        raise SystemExit(1)
    ref = parse_note_ref(sys.argv[1])
    token = sys.argv[2] if len(sys.argv) > 2 else ref["xsec_token"]
    print(f"note_id={ref['note_id']}\nxsec_token={token[:24]}...")
    if not available():
        print("当前解释器缺少 curl_cffi / xhshow，请在 tools/.venv 下运行")
        raise SystemExit(2)
    with XhsComments() as c:
        result = asyncio.run(c.fetch(ref["note_id"], token, deep=True))
    print(json.dumps(result, ensure_ascii=False, indent=2)[:2000])

"""用括号配对提取 commentData.comments 数组并 json.loads。

这是最终方案。原因
----------------
SSR 里一级评论的 ``user`` 和 ``content`` 之间**隔着整个
subComments 数组**，实测距离 1000~1500 字。任何"最近距离配对"
在这种跨度下都会错配（前面 6 轮正则迭代全死于此）。

括号配对流程
------------
1. 反转义（只转 ``\\u002F``）
2. 定位 ``"commentData":{"`` 后的 ``"comments":[``
3. 从 ``[`` 开始做**括号深度扫描**，跳过字符串/转义，
   找到匹配的 ``]`` —— 这就是完整评论数组
4. ``json.loads`` 直接解析（数组内是标准 JSON，
   content 用的是中文引号 ``“”`` 不冲突）

如果 json.loads 失败，退化为正则（保底）。
"""

from __future__ import annotations

import json
import re
from typing import Any

from .ssr import prepare  # noqa: E402  复用只转斜杠的 prepare


def _extract_array(text: str, start: int) -> tuple[int, int] | None:
    """从 ``text[start] == '['`` 开始，找匹配的 ``]``。

    返回 (start, end) 或 None。正确跳过字符串内的括号与转义。
    """
    depth = 0
    in_str = False
    esc = False
    for i in range(start, len(text)):
        c = text[i]
        if in_str:
            if esc:
                esc = False
            elif c == "\\":
                esc = True
            elif c == '"':
                in_str = False
            continue
        if c == '"':
            in_str = True
        elif c in "[{":
            depth += 1
        elif c in "]}":
            depth -= 1
            if depth == 0:
                return start, i + 1
    return None


def parse_comments_raw(html: str) -> list[dict[str, Any]] | None:
    """括号配对 + json.loads，返回**未归一化**的原始评论数组。

    与 :func:`parse_comments_json` 的区别：这个不做字段名映射，
    保留 SSR 原样的 ``id`` / ``user`` / ``subComments`` / ``ipLocation``。
    给需要原字段的下游用（例如回填历史 ``data/`` 目录，
    其 ``comments.json`` 用的是 API 侧字段名 ``user_info`` /
    ``create_time``，归一化后的扁平结构丢失了这两项，写进去下游读不到）。
    """
    h = prepare(html)

    cd = h.find('"commentData"')
    if cd < 0:
        return None

    m = re.compile(r'"comments"\s*:\s*\[').search(h, cd)
    if not m:
        return None

    span = _extract_array(h, m.end() - 1)
    if not span:
        return None

    try:
        data = json.loads(h[span[0]:span[1]])
    except json.JSONDecodeError:
        return None
    if not isinstance(data, list):
        return None

    return [c for c in data if isinstance(c, dict)]


def parse_comments_json(html: str) -> list[dict[str, Any]] | None:
    """括号配对 + json.loads。失败返回 None（让调用方退化到正则）。"""
    data = parse_comments_raw(html)
    if data is None:
        return None

    rows: list[dict[str, Any]] = []
    for c in data:
        u = c.get("user") or {}
        rows.append({
            "user_id": str(u.get("userId") or u.get("user_id") or ""),
            "nickname": str(u.get("nickname") or u.get("nickName") or ""),
            "content": str(c.get("content") or ""),
            "ip_location": str(c.get("ipLocation") or c.get("ip_location") or ""),
            "like_count": _norm_like(c.get("likeCount")),
            "time": int(c.get("time") or 0),
            "is_author": "is_author" in (c.get("showTags")
                                         or c.get("show_tags") or []),
            "_is_reply": False,
            # 楼中楼内联在 subComments
            "_replies": _replies(c),
        })
    return rows


def _replies(parent: dict) -> list[dict[str, Any]]:
    out = []
    for r in (parent.get("subComments") or parent.get("sub_comments") or []):
        if not isinstance(r, dict):
            continue
        u = r.get("user") or {}
        out.append({
            "user_id": str(u.get("userId") or u.get("user_id") or ""),
            "nickname": str(u.get("nickname") or u.get("nickName") or ""),
            "content": str(r.get("content") or ""),
            "ip_location": str(r.get("ipLocation")
                               or r.get("ip_location") or ""),
            "like_count": _norm_like(r.get("likeCount")),
            "time": int(r.get("time") or 0),
            "is_author": "is_author" in (r.get("showTags")
                                         or r.get("show_tags") or []),
            "_is_reply": True,
            "_parent_id": str(parent.get("id") or ""),
        })
    return out


def _norm_like(v: Any) -> str:
    """likeCount 归一成字符串：可能是 int、str、"1千+"、"1万+"。"""
    if v is None:
        return "0"
    if isinstance(v, (int, float)):
        return str(int(v))
    s = str(v).strip()
    return s or "0"


def flatten(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """把带 _replies 的树形结构摊平，与旧版输出契约一致。"""
    out: list[dict[str, Any]] = []
    for r in rows:
        base = {k: v for k, v in r.items() if k != "_replies"}
        out.append(base)
        for sub in (r.get("_replies") or []):
            out.append({k: v for k, v in sub.items()})
    return out
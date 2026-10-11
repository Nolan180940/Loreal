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
    """括号配对 + json.loads。失败返回 None（让调用方退化到正则）。

    字段取舍（2026-10-11 实测后修正）
    --------------------------------
    SSR 原始对象里有 14 个键，早先只取了 6 个，丢了 4 个**下游要用**的：

    ==================  ================================================
    ``id``              评论 id。**父子配对的主键** —— 楼中楼的
                        ``targetComment.id`` 指向它。丢了它，
                        下游拿到的 ``_parent_id`` 就是悬空指针。
    ``likeViewCount``   **展示给用户看的点赞数**（实测 310/56/24 这种真值）。
                        早先取的是 ``likeCount``，它**恒为 0** ——
                        于是下游误以为「平台不填充点赞」。

                        〘语义怎么定的〙字段名有歧义（view 可能是「浏览」），
                        用数值分布排除：实测某帖 5373 赞 / 1980 评论，
                        其热评的 ``likeViewCount`` 只有 310/56/24，
                        且多条为 0。若它是**浏览量**，
                        热评不可能只有几百，更不可能为 0
                        （被展示过的评论必然有人看过）。
                        所以只能是点赞。
                        ⚠️ 仍建议在 UI 上人工比对一次（只需一篇）。
    ``subCommentCount`` 楼中楼声明数。可判断楼中楼是否抓全。
    ``status``          评论状态。实测 ``-2`` = 审核中/仅自己可见
                        （卖家帖 5/5 全是 -2），本身是个信号。
    ==================  ================================================

    ``like_count`` **保持原样不动**（就是 ``likeCount``，恒 0）。
    不改成 ``likeViewCount`` 是为了让新旧数据的字段含义不变 ——
    改字段含义会让「旧数据的 0」和「新数据的 310」无法区分。
    要真实点赞请读 ``like_view_count``。

    **一级与楼中楼字段集完全一致**（差异用空值/``_is_reply`` 表达）——
    这样下游不用写 ``if "id" in c`` 这类分支，漏一处就是静默错。
    代价：``_parent_id`` 不再能当「是不是楼中楼」的判据，
    但那本来该看 ``_is_reply``。
    """
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
            # ---- 2026-10-11 新增（见 docstring 的字段取舍）----
            "id": str(c.get("id") or ""),
            "like_view_count": _norm_like(c.get("likeViewCount")),
            "sub_comment_count": int(c.get("subCommentCount") or 0),
            "status": int(c.get("status") or 0),
            # 一级评论没有父 —— 空值而不是缺键（字段集要一致）
            "_parent_id": "",
            "target_id": "",
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
            # ---- 2026-10-11 新增 ----
            "id": str(r.get("id") or ""),
            "like_view_count": _norm_like(r.get("likeViewCount")),
            "sub_comment_count": int(r.get("subCommentCount") or 0),
            "status": int(r.get("status") or 0),
            # 楼中楼可以再嵌楼中楼（targetComment 指向另一条楼中楼）
            "target_id": str((r.get("targetComment") or {}).get("id") or ""),
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
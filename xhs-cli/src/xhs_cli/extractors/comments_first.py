"""评论归一化。

小红书在不同渲染路径下字段命名不一致，必须同时兼容：

- PC SSR / ``comment/page``：``user_info`` / ``sub_comment_count`` / ``like_count``
- App 分享 SSR：``userInfo`` / ``subCommentCount``

另外「笔记显示的评论数」= 一级评论 + 楼中楼总数，而 SSR 只内联首批，
所以 :func:`summarize` 会明确标注 ``partial`` 与缺口数，不伪装成完整数据。
"""

from __future__ import annotations

from typing import Any


def _get(obj: dict, *names: str, default: Any = None) -> Any:
    for n in names:
        if n in obj and obj[n] is not None:
            return obj[n]
    return default


def normalize_comment(raw: dict, *, is_reply: bool = False,
                      parent_id: str = "") -> dict:
    """把平台原始评论转成内部统一结构。"""
    user = _get(raw, "user_info", "userInfo", default={}) or {}
    out = {
        "id": str(_get(raw, "id", default="")),
        "content": str(_get(raw, "content", default="") or ""),
        "create_time": int(_get(raw, "create_time", "createTime", default=0) or 0),
        "ip_location": str(_get(raw, "ip_location", "ipLocation", default="") or ""),
        "like_count": str(_get(raw, "like_count", "likeCount", default="0")),
        "user_id": str(_get(user, "user_id", "userId", default="")),
        "user_name": str(_get(user, "nickname", "nickName", "name", default="")),
        "sub_comment_count": int(
            _get(raw, "sub_comment_count", "subCommentCount", default=0) or 0
        ),
        "_is_reply": bool(is_reply),
    }
    if parent_id:
        out["_parent_id"] = parent_id
    return out


def normalize_comments(raw_list: list[dict]) -> tuple[list[dict], list[dict]]:
    """把一批原始评论拆成 ``(一级列表, 楼中楼列表)``。

    楼中楼来自一级评论内联的 ``sub_comments``：匿名环境下
    ``comment/sub/page`` 被限流，这部分只能靠页面自带的内联数据
    （实测覆盖率约 84.5%）。
    """
    top: list[dict] = []
    replies: list[dict] = []

    for raw in raw_list or []:
        if not isinstance(raw, dict):
            continue
        # 兼容某些路径把回复平铺在同一个列表里的情况
        if raw.get("_is_reply") or raw.get("parent_id"):
            replies.append(
                normalize_comment(
                    raw,
                    is_reply=True,
                    parent_id=str(raw.get("parent_id") or raw.get("_parent_id") or ""),
                )
            )
            continue

        item = normalize_comment(raw, is_reply=False)
        subs_inlined = [
            s for s in (_get(raw, "sub_comments", "subComments", default=[]) or [])
            if isinstance(s, dict)
        ]
        item["_inline_replies"] = [
            normalize_comment(s, is_reply=True, parent_id=item["id"])
            for s in subs_inlined
        ]
        top.append(item)

        for sub in subs_inlined:
            replies.append(
                normalize_comment(sub, is_reply=True, parent_id=item["id"])
            )
    return top, replies


def inline_coverage(top: list[dict]) -> tuple[int, int]:
    """统计内联楼中楼覆盖率，返回 ``(实得, 期望)``。

    匿名环境下拿不到 ``comment/sub/page``，只能依赖一级评论自带的
    ``sub_comments``；这个比值说明还有多少楼中楼没抓到。
    """
    got = sum(len(c.get("_inline_replies") or []) for c in top)
    want = sum(int(c.get("sub_comment_count") or 0) for c in top)
    return got, want


def summarize(top: list[dict], replies: list[dict],
              note_reported: str = "") -> dict:
    """生成统计卡片，明确标注是否完整。"""
    total = len(top) + len(replies)
    expect = 0
    if note_reported not in ("", "-1", "0", None):
        try:
            expect = int(note_reported)
        except (TypeError, ValueError):
            expect = 0

    return {
        "top_level": len(top),
        "replies": len(replies),
        "total": total,
        "note_reported": expect,
        "note_reported_known": expect > 0,
        "matched": (total == expect) if expect > 0 else None,
        "diff": (expect - total) if expect > 0 else 0,
        "partial": expect > 0 and total < expect,
        "source": "share_page_ssr",
    }
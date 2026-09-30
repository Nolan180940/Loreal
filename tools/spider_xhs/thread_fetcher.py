# -*- coding: utf-8 -*-
"""楼中楼完整抓取（补全 sub/page 分页）。

为什么需要它
------------
小红书「评论数」= 一级评论 + 楼中楼。但接口对楼中楼只给**部分**内容：

- 一级评论响应里的 ``sub_comments`` 字段：只内联**前几条**；
- ``/api/sns/web/v2/comment/sub/page``：**每页仅 5 条**（实测），
  需按 cursor 翻页才能取全。

实测案例（笔记 6ab7946f...）：
    某楼 sub_comment_count = 29
    内联 sub_comments 只给 7 条
    sub/page 第 1、2 页各给 5 条（共 10）
    → 工具原版只取 7 条，漏 22 条

所以必须显式翻 sub/page，并与内联结果按 id 去重合并。
"""

from __future__ import annotations

import time

SUB_URL_PATH = "/api/sns/web/v2/comment/sub/page"

# 每页实测 5 条；给 10 是接口允许的上限，平台仍按 5 返回
PAGE_LIMIT = 10
MAX_PAGES = 30          # 单楼最多 30 页 = 150 条，安全阀
DEFAULT_SLEEP = 0.8     # 秒；风控友好


def _splice(api: str, params: dict) -> str:
    from xhs_utils.xhs_util import splice_str
    return splice_str(api, params)


def _request(apis, path: str, params: dict) -> dict:
    sp = _splice(path, params)
    headers, cookies, _ = apis._request_params(sp, "", "GET")
    resp = apis.http.get(apis.base_url + sp, headers=headers,
                         cookies=cookies, timeout=20)
    j = resp.json()
    if not j.get("success"):
        return {}
    return j.get("data") or {}


def _merge_by_id(*groups) -> list[dict]:
    """按 id 去重合并，保持首次出现顺序。"""
    seen, out = set(), []
    for g in groups:
        for item in g or []:
            i = item.get("id")
            if i and i not in seen:
                seen.add(i)
                out.append(item)
    return out


def fetch_replies(apis, note_id: str, root_id: str, xsec_token: str,
                  sleep: float = DEFAULT_SLEEP) -> list[dict]:
    """取某个楼下的全部回复（含翻页）。"""
    out, cursor, pages = [], "", 0
    while pages < MAX_PAGES:
        params = {
            "note_id": note_id,
            "root_comment_id": root_id,
            "num": str(PAGE_LIMIT),
            "cursor": cursor,
            "image_formats": "jpg,webp,avif",
            "top_comment_id": "",
            "xsec_token": xsec_token,
        }
        try:
            data = _request(apis, SUB_URL_PATH, params)
        except Exception:
            break
        batch = data.get("comments") or []
        out.extend(batch)
        pages += 1
        nxt = data.get("cursor")
        if not data.get("has_more") or not nxt or not batch:
            break
        cursor = str(nxt)
        if sleep:
            time.sleep(sleep)
    return out


def complete_threads(apis, top_comments: list, note_id: str,
                     xsec_token: str, sleep: float = DEFAULT_SLEEP,
                     verbose: bool = True) -> dict:
    """为所有「楼中楼未抓全」的一级评论补全回复。

    返回统计：{"filled": 补全条数, "gaps": 仍缺失的明细, "calls": 额外请求数}
    """
    filled = calls = 0
    gaps: list[dict] = []

    for c in top_comments:
        try:
            want = int(str(c.get("sub_comment_count") or 0) or 0)
        except ValueError:
            want = 0
        inline = c.get("sub_comments") or []
        if want <= len(inline):
            continue

        extra = fetch_replies(apis, note_id, c.get("id", ""), xsec_token,
                              sleep=sleep)
        calls += 1
        merged = _merge_by_id(inline, extra)
        c["sub_comments"] = merged
        got = len(merged)
        filled += max(0, got - len(inline))
        if got < want:
            gaps.append({
                "comment_id": c.get("id"),
                "expect": want,
                "got": got,
                "content": (c.get("content") or "")[:40],
            })
        if verbose:
            say(f"      楼 {c.get('id','')[-8:]}: "
                f"{len(inline)} -> {got} / 期望 {want}")
        if sleep:
            time.sleep(sleep)

    return {"filled": filled, "gaps": gaps, "calls": calls}


def summarize(note_obj: dict, top: list, replies: list) -> dict:
    """核对抓取数与笔记页显示数，明确报告差异（不静默丢数据）。"""
    try:
        expect = int(str((note_obj or {}).get("评论数量") or 0) or 0)
    except ValueError:
        expect = 0
    got = len(top) + len(replies)
    return {
        "note_reported": expect,
        "top_level": len(top),
        "replies": len(replies),
        "total": got,
        "matched": got == expect,
        "diff": expect - got,
    }

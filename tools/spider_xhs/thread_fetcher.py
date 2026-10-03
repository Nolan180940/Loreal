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

import json
import random
import time
from pathlib import Path

SUB_URL_PATH = "/api/sns/web/v2/comment/sub/page"

# 每页实测 5 条；给 10 是接口允许的上限，平台仍按 5 返回
PAGE_LIMIT = 10
MAX_PAGES = 30          # 单楼最多 30 页 = 150 条，安全阀
DEFAULT_SLEEP = 0.8     # 秒；风控友好


def _jitter() -> float:
    return random.uniform(0, 1.5)


def _splice(api: str, params: dict) -> str:
    from xhs_utils.xhs_util import splice_str
    return splice_str(api, params)


class RiskError(RuntimeError):
    """平台返回风控信号（HTTP 461 / code 300013「访问频繁」等）。"""


# 触发风控的 code 集合：300013=访问频繁，300012/-1 类为登录态异常
RISK_CODES = {300013, 300012, 300011, 300015}


def _request(apis, path: str, params: dict) -> dict:
    sp = _splice(path, params)
    headers, cookies, _ = apis._request_params(sp, "", "GET")
    resp = apis.http.get(apis.base_url + sp, headers=headers,
                         cookies=cookies, timeout=20)
    # 关键：461 响应体里 success 仍是 true、data 为空，
    # 若只看 success 会把「被限流」误判成「该楼没有更多回复」。
    if resp.status_code == 461:
        raise RiskError(f"HTTP 461 访问频繁 ({path})")
    j = resp.json()
    code = j.get("code")
    if code in RISK_CODES:
        raise RiskError(f"code {code} {j.get('msg','')} ({path})")
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


TOP_URL_PATH = "/api/sns/web/v2/comment/page"
MAX_TOP_PAGES = 200     # 一级评论最多 200 页（2000 条）
                        # 注意：实测大帖可达 1311 条评论 = 131 页，
                        # 上限设 60 会永远抓不全（60*10=600）
MAX_TOP_SECONDS = 900   # 单篇一级评论总耗时上限（秒）
MAX_FLOOR_SECONDS = 90  # 单个楼的楼中楼总耗时上限（秒）


def fetch_top_comments(apis, note_id: str, xsec_token: str,
                       sleep: float = DEFAULT_SLEEP, progress=None,
                       ckpt: Path | None = None, req=None) -> list[dict]:
    """分页取全部一级评论，**每页增量落盘**（断点续抓）。

    为什么必须增量落盘
    ------------------
    大帖动辄上千条评论 = 上百次请求。若只在全部抓完后才写盘，中途被风控或
    进程被杀就**整篇丢弃**，重跑又从第 1 页开始 → 必然再次触发风控，
    形成死循环。这里每页写一次 ``.partial.json``（含 cursor），重跑时从
    断点继续，已抓的不再请求。

    另外不能用 ``apis.get_note_all_out_comment``：它是 ``while True`` 且
    **没有翻页上限**，平台返回重复 cursor 且 ``has_more=true`` 时会死循环
    （症状：CPU 与 IO 全为 0，连接却仍是 Established，日志不再前进）。
    """
    out: list[dict] = []
    seen_ids: set = set()
    seen_cursors: set = set()
    cursor = ""

    # --- 断点恢复 ---
    if ckpt and ckpt.is_file():
        try:
            st = json.loads(ckpt.read_text(encoding="utf-8"))
            if st.get("note_id") == note_id:
                out = st.get("comments") or []
                cursor = str(st.get("cursor") or "")
                seen_ids = {c.get("id") for c in out if c.get("id")}
                seen_cursors = set(st.get("seen_cursors") or [])
                if out:
                    if progress:
                        progress(0, len(out), True, resumed=True)
        except Exception:
            out, cursor = [], ""

    deadline = time.monotonic() + MAX_TOP_SECONDS
    page = 0
    # req：可选的请求函数(req(path, params))，用于匿名会话轮换；
    # 缺省走固定 apis（主号模式，保持旧行为）。
    do_req = req or (lambda path, params: _request(apis, path, params))
    while page < MAX_TOP_PAGES:
        if time.monotonic() > deadline:
            break            # 单篇总耗时看门狗
        params = {
            "note_id": note_id,
            "cursor": cursor,
            "top_comment_id": "",
            "image_formats": "jpg,webp,avif",
            "xsec_token": xsec_token,
        }
        data = do_req(TOP_URL_PATH, params)   # 461 会抛 RiskError
        batch = data.get("comments") or []
        for c in batch:
            cid = c.get("id")
            if cid and cid not in seen_ids:
                seen_ids.add(cid)
                out.append(c)
        page += 1
        if progress:
            progress(page, len(out), bool(data.get("has_more")))
        nxt = data.get("cursor")
        more = bool(data.get("has_more")) and bool(nxt) and bool(batch)
        if ckpt:
            _save_ckpt(ckpt, note_id, out, str(nxt or cursor),
                       seen_cursors, more)
        if not more:
            break
        nxt = str(nxt)
        if nxt == cursor or nxt in seen_cursors:
            break            # cursor 不推进 = 平台在原地打转，停手
        seen_cursors.add(nxt)
        cursor = nxt
        if sleep:
            time.sleep(sleep)
    return out


def _save_ckpt(p: Path, note_id: str, comments: list, cursor: str,
               seen: set, more: bool, root_id: str = "") -> None:
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps({
            "note_id": note_id, "root_id": root_id, "cursor": cursor,
            "comments": comments, "seen_cursors": sorted(seen),
            "has_more": more,
            "saved_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        }, ensure_ascii=False), encoding="utf-8")
    except OSError:
        pass


def fetch_replies(apis, note_id: str, root_id: str, xsec_token: str,
                  sleep: float = DEFAULT_SLEEP, retry: int = 3,
                  ckpt: Path | None = None, req=None) -> list[dict]:
    """取某个楼下的全部回复（含翻页 + 退避重试 + 断点续抓）。"""
    out, cursor, pages = [], "", 0
    attempt = 0
    seen_cursors: set = set()

    if ckpt and ckpt.is_file():
        try:
            st = json.loads(ckpt.read_text(encoding="utf-8"))
            if st.get("root_id") == root_id:
                out = st.get("comments") or []
                cursor = str(st.get("cursor") or "")
                seen_cursors = set(st.get("seen_cursors") or [])
        except Exception:
            out, cursor = [], ""

    deadline = time.monotonic() + MAX_FLOOR_SECONDS
    do_req = req or (lambda path, params: _request(apis, path, params))
    while pages < MAX_PAGES:
        if time.monotonic() > deadline:
            break            # 单楼总耗时看门狗
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
            data = do_req(SUB_URL_PATH, params)
        except RiskError:
            attempt += 1
            if attempt > retry:
                break
            w = min(8.0 * (2 ** (attempt - 1)), 45.0) + _jitter()
            time.sleep(w)
            continue
        attempt = 0
        batch = data.get("comments") or []
        out.extend(batch)
        pages += 1
        nxt = data.get("cursor")
        more = bool(data.get("has_more")) and bool(nxt) and bool(batch)
        if ckpt:
            _save_ckpt(ckpt, note_id, out, str(nxt or cursor),
                       seen_cursors, more, root_id=root_id)
        if not more:
            break
        nxt = str(nxt)
        if nxt == cursor or nxt in seen_cursors:
            break            # cursor 不推进，停手
        seen_cursors.add(nxt)
        cursor = nxt
        if sleep:
            time.sleep(sleep)
    return out


def complete_threads(apis, top_comments: list, note_id: str,
                     xsec_token: str, sleep: float = DEFAULT_SLEEP,
                     verbose: bool = True, progress=None,
                     ckpt_dir: Path | None = None, req=None) -> dict:
    """为所有「楼中楼未抓全」的一级评论补全回复。

    返回统计：{"filled": 补全条数, "gaps": 仍缺失的明细, "calls": 额外请求数}
    """
    filled = calls = 0
    gaps: list[dict] = []
    todo = []
    for c in top_comments:
        try:
            want = int(str(c.get("sub_comment_count") or 0) or 0)
        except ValueError:
            want = 0
        inline = c.get("sub_comments") or []
        if want > len(inline):
            todo.append((c, want, len(inline)))

    for i, (c, want, n_inline) in enumerate(todo, 1):
        if progress:
            progress(i, len(todo), c.get("id", ""))
        ck = (ckpt_dir / f"floor_{c.get('id','')}.json") if ckpt_dir else None
        extra = fetch_replies(apis, note_id, c.get("id", ""), xsec_token,
                              sleep=sleep, ckpt=ck, req=req)
        calls += 1
        merged = _merge_by_id(c.get("sub_comments") or [], extra)
        c["sub_comments"] = merged
        got = len(merged)
        filled += max(0, got - n_inline)
        if got < want:
            gaps.append({
                "comment_id": c.get("id"),
                "expect": want,
                "got": got,
                "content": (c.get("content") or "")[:40],
            })
        if verbose:
            say(f"      楼 {c.get('id','')[-8:]}: "
                f"{n_inline} -> {got} / 期望 {want}")
        if sleep:
            time.sleep(sleep)

    if gaps:
        # 楼中楼没抓全通常是 sub/page 被限流；上抛让主循环退避后整篇重来，
        # 否则「访问频繁」会被静默固化成永久数据缺失。
        raise RiskError(
            f"{len(gaps)} 个楼的楼中楼未取全（共缺 "
            f"{sum(g['expect'] - g['got'] for g in gaps)} 条），疑似被限流")

    return {"filled": filled, "gaps": gaps, "calls": calls}


def summarize(note_obj: dict, top: list, replies: list) -> dict:
    """核对抓取数与笔记页显示数，明确报告差异（不静默丢数据）。

    注意：XHS-Downloader 抓 HTML 时「评论数量」偶尔会解析成 ``-1``
    （正则吃到无关数字），此时平台并未真正给出评论数，按「未知」处理，
    不能记成缺口。
    """
    try:
        expect = int(str((note_obj or {}).get("评论数量") or 0) or 0)
    except ValueError:
        expect = 0
    if expect < 0:
        expect = 0
    got = len(top) + len(replies)
    return {
        "note_reported": expect,
        "reported_known": expect > 0,
        "top_level": len(top),
        "replies": len(replies),
        "total": got,
        "matched": got == expect,
        "diff": expect - got,
    }

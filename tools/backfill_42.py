# -*- coding: utf-8 -*-
"""用 xhs-cli 的 HTTP 直连链路，补齐 ``data/`` 下 42 帖的缺件。

先把真实缺口说清楚
------------------
``data/`` 下 42 篇是**多轮、多工具**采集拼起来的，实测有四类缺口：

1. **``comments.json`` 是 ``browser_dom`` 残件**（24 篇）
   DOM 抓的 10 条一级评论，``user_info`` 是 **空对象** —— 昵称/作者 ID 全丢。
   下游 ``jev_guard.reader`` 的 ``author`` 因此全空，
   任何按作者维度的分析都失效。这是最严重的一类。
2. **``comments.txt`` 缺**（26 篇）人读版，早期脚本才写。
3. **``card.json`` 缺**（6 篇）评论对齐卡片。
4. **``note.json`` 部分字段空**（标题/正文/互动数，两套 schema 混存）。

重新全量抓一遍会浪费配额、还会覆盖已有的人工校对成果。
所以这里做**非破坏性回填**：只填空的；仅在「本地昵称全空 且 新抓有昵称」
时才升级 ``comments.json``，且**先备份**。

为什么不直接用 ``service.parse_link()``
---------------------------------------
它返回归一化扁平结构（``nickname`` 在顶层、丢掉 ``id``），
而历史 ``comments.json`` 用 API 侧字段名，下游
``jev_guard.reader.load_comment()`` 硬依赖 ``row["id"]`` 与
``row["user_info"]``。写扁平结构进去，下游一行都读不到。
所以走 ``ssr_json.parse_comments_raw()`` 拿原始数组再映射。

一个必须知道的限制
------------------
``commentData`` 里有 ``hasMore`` / ``cursor`` / ``commentCountL1``，
说明评论**确实分页**，但匿名访客拿不到下一页
（``/api/sns/web/v2/comment/page`` 对访客恒定 461，已实测）。
所以 HTTP 直连每篇只能拿到**首屏 4~5 条一级 + 内联楼中楼**。
这不影响本工具的价值：缺的就是首屏。

用法::

    python tools/backfill_42.py                 # 干跑，只报告
    python tools/backfill_42.py --apply         # 真回填
    python tools/backfill_42.py --apply --only 6abcc08e,6abc5bb8
    python tools/backfill_42.py --apply --no-images --no-upgrade
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
import time
import urllib.error
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "xhs-cli" / "src"))

from xhs_cli.core import fetch  # noqa: E402
from xhs_cli.core.ssr import parse_note  # noqa: E402
from xhs_cli.core.ssr_json import parse_comments_raw  # noqa: E402

DATA = ROOT / "data"
URLS = ROOT / "urls.txt"
BACKUP = DATA / ".backup"
REPORT = DATA / "_backfill_report.json"

NOTE_RE = re.compile(r"/(?:explore|discovery/item)/([0-9a-f]{24})")
IMG_EXTS = (".jpg", ".jpeg", ".png", ".webp", ".heic", ".avif")

#: 篇间隔。IP 有滑动窗口配额，抓太密会整批 461。
SLEEP_BETWEEN = 1.6

#: 单篇图片下载上限。
MAX_IMAGES = 24

SOURCE_TAG = "xhs-cli/core"

CST = timezone(timedelta(hours=8))

#: 真正影响下游的 note 字段（纯别名补写不算缺口）。
NOTE_KEY_FIELDS = (
    "title", "desc", "tags", "author", "author_id", "liked", "collected",
    "comment_count", "share_count", "published", "ip_location", "images",
    "作品标题", "作品描述", "作者昵称", "点赞数量", "收藏数量",
    "评论数量", "分享数量", "IP属地", "下载地址",
)


def force_utf8() -> None:
    """Windows 控制台默认 GBK，emoji 会 UnicodeEncodeError。"""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:  # noqa: BLE001
            pass


# --------------------------------------------------------------------- 工具
def has(v: Any) -> bool:
    """字段是否有真实值。与 ``jev/tools/audit_42.py`` 同口径。"""
    return v not in (None, "", [], {}, 0, "0", -1, "-1")


def read_json(p: Path) -> Any:
    if not p.is_file():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError, OSError):
        return None


def write_json(p: Path, obj: Any) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")


def norm_like(v: Any) -> str:
    if v is None:
        return "0"
    if isinstance(v, (int, float)):
        return str(int(v))
    return str(v).strip() or "0"


def to_int(v: Any, default: int = 0) -> int:
    """安全转 int。小红书的计数有 ``-1``（未公开）与 ``"1.2万"`` 两种坑。"""
    if v is None:
        return default
    if isinstance(v, (int, float)):
        return max(int(v), 0)
    s = str(v).strip().replace(",", "")
    if not s or s in {"-", "-1"}:
        return default
    mult = 1
    if s.endswith("万"):
        mult, s = 10000, s[:-1]
    elif s.endswith(("w", "W")):
        mult, s = 10000, s[:-1]
    try:
        return max(int(float(s) * mult), 0)
    except ValueError:
        return default


def nick_of(row: dict) -> str:
    return str((row.get("user_info") or {}).get("nickname") or "").strip()


# --------------------------------------------------------------- note.json
def bilingual_note(fresh: dict[str, Any], url: str) -> dict[str, Any]:
    """``ssr.parse_note()`` 结果 → **双 schema**。

    历史文件两套 key（中文 / 英文），下游 ``jev_guard.reader.pick()``
    靠别名表同时认两套。两边都写，避免再出现「看着空、其实有」的误判。
    """
    tags = [t for t in (fresh.get("tags") or []) if t]
    imgs = [u for u in (fresh.get("images") or []) if u]
    ts = to_int(fresh.get("time_ms"))
    published = ""
    if ts > 0:
        published = datetime.fromtimestamp(
            ts / 1000, CST).strftime("%Y-%m-%d %H:%M:%S")

    aid = fresh.get("author_id") or ""
    return {
        # ---- 英文 schema ----
        "note_id": fresh.get("note_id") or "",
        "title": fresh.get("title") or "",
        "desc": fresh.get("desc") or "",
        "tags": tags,
        "author": fresh.get("author") or "",
        "author_id": aid,
        "author_link": (f"https://www.xiaohongshu.com/user/profile/{aid}"
                        if aid else ""),
        "link": url,
        "published": published,
        "time_ms": ts,
        "ip_location": fresh.get("ip_location") or "",
        "liked": to_int(fresh.get("liked")),
        "collected": to_int(fresh.get("collected")),
        "comment_count": to_int(fresh.get("comment_count")),
        "share_count": to_int(fresh.get("share")),
        "image_count": len(imgs),
        "images": imgs,
        "source": SOURCE_TAG,
        # ---- 中文别名（历史 schema）----
        "作品标题": fresh.get("title") or "",
        "作品描述": fresh.get("desc") or "",
        "作品ID": fresh.get("note_id") or "",
        "作品链接": url,
        "作品类型": "normal",
        "发布时间": published,
        "时间戳": ts,
        "作者昵称": fresh.get("author") or "",
        "作者ID": aid,
        "作者链接": (f"https://www.xiaohongshu.com/user/profile/{aid}"
                     if aid else ""),
        "IP属地": fresh.get("ip_location") or "",
        "点赞数量": to_int(fresh.get("liked")),
        "收藏数量": to_int(fresh.get("collected")),
        "评论数量": to_int(fresh.get("comment_count")),
        "分享数量": to_int(fresh.get("share")),
        "作品标签": " ".join(tags),
        "下载地址": imgs,
    }


def fill_blanks(cur: dict[str, Any], fresh: dict[str, Any]) -> list[str]:
    """把 ``fresh`` 里 ``cur`` 为空/缺失的字段补上。只填空，不覆盖。"""
    filled: list[str] = []
    for k, v in fresh.items():
        if not has(v):
            continue
        if not has(cur.get(k)):
            if cur.get(k) != v:
                cur[k] = v
            filled.append(k)
    return filled


def note_reported(note: dict[str, Any]) -> int:
    """note.json 声称的评论数。两个 schema 都认。"""
    for k in ("comment_count", "评论数量"):
        v = note.get(k)
        if has(v):
            return to_int(v)
    return 0


def render_note_md(n: dict[str, Any]) -> str:
    return "\n".join([
        f"# {n.get('title') or n.get('作品标题') or ''}",
        "",
        f"作者：{n.get('author') or n.get('作者昵称') or ''}",
        f"发布：{n.get('published') or n.get('发布时间') or ''}",
        "互动："
        f"赞{n.get('liked', 0)} 藏{n.get('collected', 0)} "
        f"评{n.get('comment_count', 0)} 享{n.get('share_count', 0)}",
        "",
        "## 正文",
        str(n.get("desc") or n.get("作品描述") or ""),
        "",
        "## 标签",
        " ".join(n.get("tags") or (n.get("作品标签") or "").split()),
        "",
    ])


# ----------------------------------------------------------- comments.json
def legacy_user(u: dict[str, Any]) -> dict[str, Any]:
    """SSR 的 ``user`` 块 → 历史 ``user_info`` 块。"""
    return {
        "xsec_token": "",
        "user_id": str(u.get("userId") or u.get("user_id") or ""),
        "nickname": str(u.get("nickname") or u.get("nickName") or ""),
        "image": str(u.get("image") or ""),
        "ai_agent": bool(u.get("aiAgent") or False),
    }


def legacy_comment(c: dict[str, Any], note_id: str, *,
                   reply: bool = False, parent_id: str = "") -> dict[str, Any]:
    """SSR 原始评论 → 历史 ``comments.json`` 条目（API 侧字段名）。

    下游 ``jev_guard.reader`` 就按这套读：``id`` + ``user_info.nickname``
    + ``content`` + ``like_count``。
    """
    cid = str(c.get("id") or "")
    subs = [
        legacy_comment(s, note_id, reply=True, parent_id=cid)
        for s in (c.get("subComments") or []) if isinstance(s, dict)
    ]
    out = {
        "content": str(c.get("content") or ""),
        "like_count": norm_like(c.get("likeCount")),
        "user_info": legacy_user(c.get("user") or {}),
        "show_tags": [],
        "create_time": to_int(c.get("time")),
        "sub_comment_has_more": False,
        "invalid": False,
        "id": cid,
        "at_users": c.get("atUsers") or [],
        "liked": bool(c.get("liked") or False),
        "sub_comment_count": str(to_int(c.get("subCommentCount"))),
        "note_id": note_id,
        "status": int(c.get("status") or 0),
        "ip_location": str(c.get("ipLocation") or ""),
        "sub_comments": subs,
        "sub_comment_cursor": (subs[-1]["id"] if subs else ""),
    }
    if reply:
        out["_is_reply"] = True
        out["_parent_id"] = parent_id
    return out


def has_text(row: dict) -> bool:
    """该行是否有可用正文。

    SSR 里存在 ``content`` 为空的评论（纯图评论、已删评论占位）。
    下游 ``jev_guard.reader.load_comment()`` 遇到空 content 直接返回
    ``None``，所以这类行写进去只会让「文件行数」与「可读行数」不一致，
    没有任何价值 —— 直接不写。
    """
    return bool(str(row.get("content") or "").strip())


def fresh_comments(raw: list[dict], note_id: str) -> list[dict]:
    """SSR 原始数组 → 历史格式扁平列表（一级在前，楼中楼在后）。"""
    tops = [legacy_comment(c, note_id) for c in raw]
    replies = [s for c in tops for s in c["sub_comments"]]
    return [r for r in (tops + replies) if has_text(r)]


def merge_comments(local: list[dict], fresh: list[dict]) -> tuple[list[dict], int, int]:
    """把新抓结果**并**进本地（去重 + 只补空字段）。

    为什么不是二选一
    --------------
    实测两边 ``id`` 只**部分**重叠：``6ab6a30e`` 是 0/10，
    ``6abc9b7b`` 是 5/10 —— 因为 DOM 快照与新抓快照之间
    评论列表已经变了（按时间/热度排序）。所以：

    * 两边都有的 id ：保留本地行，只补它的空字段（如 nickname）
    * 只有本地有的    ：整行保留（不能丢）
    * 只有新抓有的    ：追加

    并集严格优于任一边：行数不减，且空昵称被填上。

    Returns
    -------
    (合并后的列表, 补空的行数, 追加的行数)
    """
    by_id: dict[str, dict] = {}
    order: list[str] = []
    for r in local:
        rid = str(r.get("id") or "")
        if not rid or rid in by_id:
            continue
        by_id[rid] = r
        order.append(rid)

    patched = added = 0
    for r in fresh:
        rid = str(r.get("id") or "")
        if not rid:
            continue
        if rid not in by_id:
            by_id[rid] = r
            order.append(rid)
            added += 1
            continue
        # 已有：只补空字段，不动非空值
        tgt = by_id[rid]
        for k, v in r.items():
            if k == "sub_comments":
                continue            # 嵌套楼中楼不在此层合并
            if not has(v):
                continue
            if not has(tgt.get(k)):
                tgt[k] = v
                patched += 1

    # 按原顺序输出：本地行在前，追加行在后
    return [by_id[i] for i in order], patched, added


def build_card(note_id: str, reported: int, arr: list[dict],
               source: str) -> dict[str, Any]:
    """按 ``tools/spider_xhs/thread_fetcher.summarize()`` 的口径造卡片。"""
    tops = [r for r in arr if not r.get("_is_reply")]
    replies = [r for r in arr if r.get("_is_reply")]
    got = len(arr)
    return {
        "note_id": note_id,
        "note_reported": reported,
        "reported_known": reported > 0,
        "top_level": len(tops),
        "replies": len(replies),
        "total": got,
        "matched": got == reported,
        "diff": reported - got,
        # 匿名访客拿不到评论翻页接口（sub/page 一律 461），
        # 所以固定 0 次补楼调用、无 gap 记录。
        "thread_fill_calls": 0,
        "thread_gaps": [],
        "anon_partial": got != reported,
        "source": source,
    }


def render_comments_txt(arr: list[dict], card: dict[str, Any]) -> str:
    """与 ``tools/spider_xhs/batch_fetch.py::_write_comments_txt`` 同格式。"""
    lines = [
        f"笔记页 {card['note_reported']} | 一级 {card['top_level']} + "
        f"楼中楼 {card['replies']} = {card['total']} | "
        f"{'已对齐' if card['matched'] else '差 %d' % card['diff']}",
        "",
    ]
    for c in arr:
        if c.get("_is_reply"):
            continue
        ui = c.get("user_info") or {}
        lines.append("- [%s] %s | %s | 赞%s" % (
            ui.get("nickname") or "?", c.get("ip_location") or "?",
            (c.get("content") or "").replace("\n", " ").strip()[:60],
            c.get("like_count", "0")))
        for s in (c.get("sub_comments") or []):
            sui = s.get("user_info") or {}
            lines.append("    └ [%s] %s" % (
                sui.get("nickname") or "?",
                (s.get("content") or "").replace("\n", " ").strip()[:52]))
    return "\n".join(lines)


# ------------------------------------------------------------------- 主流程
def load_targets(only: set[str] | None) -> list[tuple[str, str]]:
    """从 ``urls.txt`` 取目标。``only`` 支持 24 位全长或前 8 位前缀。"""
    out: list[tuple[str, str]] = []
    for line in URLS.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        m = NOTE_RE.search(line)
        if not m:
            continue
        nid = m.group(1)
        if only and not any(nid.startswith(p) for p in only):
            continue
        out.append((nid, line))
    return out


def probe(url: str, *, retries: int = 3) -> dict[str, Any]:
    """抓一次 HTML，返回该篇的新鲜数据。

    实测失败是**偶发限流**：同一篇上轮成功、下轮就 SSR 空壳。
    所以这里做短退避重试，不要一次失败就���成永久缺口。
    """
    last: Exception | None = None
    for i in range(max(1, retries)):
        try:
            html = fetch.fetch_html(url)
            note = parse_note(html)
            if not note.get("liked") and not note.get("desc"):
                raise fetch.FetchError("SSR 空壳（token 可能失效或限流）",
                                       kind="empty_data")
            return {"note": note, "raw": parse_comments_raw(html) or []}
        except Exception as e:  # noqa: BLE001
            last = e
            if i < retries - 1:
                time.sleep(2.0 * (i + 1))
    raise last if last else RuntimeError("probe 失败")


def decide(nid: str, fresh: dict[str, Any], *, want_images: bool,
           allow_upgrade: bool) -> dict[str, Any]:
    """算出该篇要做什么。**不改盘**，只决策。"""
    base = DATA / nid
    cdir = base / "comments"
    plan: dict[str, Any] = {"nid": nid, "actions": [], "upgrade": False}

    note = bilingual_note(fresh["note"], fresh["url"])
    plan["note"] = note
    plan["fresh_cmt"] = fresh_comments(fresh["raw"], nid)
    plan["raw_n"] = len(fresh["raw"])
    plan["raw_replies"] = sum(len(c.get("subComments") or [])
                              for c in fresh["raw"])

    # ---- content/note.json ----
    cur = read_json(base / "content" / "note.json")
    local_note = cur if isinstance(cur, dict) else {}
    if not local_note:
        plan["actions"].append("note.json(新建)")
    else:
        filled = [k for k in fill_blanks(dict(local_note), note)
                  if k in NOTE_KEY_FIELDS]
        if filled:
            plan["actions"].append(f"note.json(补{'/'.join(filled[:4])}"
                                   f"{'…' if len(filled) > 4 else ''})")

    # ---- content/note.md ----
    md = base / "content" / "note.md"
    if not md.is_file() or len(md.read_text(encoding="utf-8").strip()) < 10:
        plan["actions"].append("note.md")

    # ---- images ----
    img_urls = read_json(base / "images" / "urls.json")
    if not (isinstance(img_urls, list) and img_urls):
        plan["actions"].append("images/urls.json")
        plan["img_urls"] = note["images"]
    if want_images and note["images"]:
        imdir = base / "images"
        have = [f for f in imdir.iterdir()
                if f.is_file() and f.suffix.lower() in IMG_EXTS] \
            if imdir.is_dir() else []
        if not have:
            plan["actions"].append("images/*.jpeg")
            plan["img_urls"] = note["images"][:MAX_IMAGES]

    # ---- comments.json ----
    # 退化识别：整份评论的昵称**全空** = DOM 残件（实测只有这 24 篇如此）。
    # 只对退化的文件做合并，已经好好的文件一律不碰。
    local = read_json(cdir / "comments.json")
    local = local if isinstance(local, list) else []
    local = [r for r in local if isinstance(r, dict)]

    if not local:
        if plan["fresh_cmt"]:
            plan["actions"].append("comments.json(新建)")
            plan["write_cmt"] = plan["fresh_cmt"]
    else:
        degenerate = all(not nick_of(r) for r in local)
        merged: list[dict] | None = None
        patched = added = 0
        if allow_upgrade and plan["fresh_cmt"] and degenerate:
            merged, patched, added = merge_comments(
                [dict(r) for r in local], plan["fresh_cmt"])

        target = merged if merged is not None else [dict(r) for r in local]
        cleaned = [r for r in target if has_text(r)]
        dropped = len(target) - len(cleaned)

        acts = []
        if patched or added:
            acts.append(f"合并 补空{patched} 追加{added} "
                        f"{len(local)}→{len(cleaned)}")
        if dropped:
            acts.append(f"清空行{dropped}")
        if acts:
            plan["actions"].append(f"comments.json({' '.join(acts)})")
            plan["write_cmt"] = cleaned
            plan["upgrade"] = plan["upgrade"] or bool(patched or added)

    effective = plan.get("write_cmt") or local

    # ---- card.json ----
    card = read_json(cdir / "card.json")
    has_card = isinstance(card, dict) and "total" in card
    reported = note_reported(local_note) or note_reported(note)
    src = SOURCE_TAG if (plan["upgrade"] or not has_card) \
        else str(card.get("source") or SOURCE_TAG)
    plan["card"] = build_card(nid, reported, effective, src)
    if not has_card:
        plan["actions"].append("card.json(新建)")
    elif plan["upgrade"]:
        plan["actions"].append("card.json(重算)")
    plan["need_card"] = not has_card or plan["upgrade"]

    # ---- comments.txt ----
    if not (cdir / "comments.txt").is_file() or plan["upgrade"]:
        plan["actions"].append("comments.txt(派生)")
        plan["need_txt"] = True

    return plan


def apply(nid: str, plan: dict[str, Any]) -> dict[str, Any]:
    base = DATA / nid
    cdir = base / "comments"
    cdir.mkdir(parents=True, exist_ok=True)
    done: dict[str, Any] = {}

    # ---- note.json（只补空）----
    if any(a.startswith("note.json") for a in plan["actions"]):
        cur = read_json(base / "content" / "note.json")
        if isinstance(cur, dict):
            filled = fill_blanks(cur, plan["note"])
            write_json(base / "content" / "note.json", cur)
            done["note_filled"] = len(filled)
        else:
            write_json(base / "content" / "note.json", plan["note"])
            done["note_filled"] = "全量"

    if "note.md" in plan["actions"]:
        (base / "content").mkdir(parents=True, exist_ok=True)
        src = read_json(base / "content" / "note.json")
        (base / "content" / "note.md").write_text(
            render_note_md(src if isinstance(src, dict) else plan["note"]),
            encoding="utf-8")
        done["note_md"] = True

    # ---- images ----
    if "images/urls.json" in plan["actions"]:
        write_json(base / "images" / "urls.json", plan["img_urls"])
        done["image_urls"] = len(plan["img_urls"])

    if "images/*.jpeg" in plan["actions"]:
        ok = 0
        for i, u in enumerate(plan["img_urls"], start=1):
            try:
                blob = fetch.fetch_image(u)
            except (fetch.FetchError, urllib.error.URLError, OSError):
                continue
            if len(blob) < 1024:
                continue
            dst = base / "images" / f"{i:02d}.jpeg"
            dst.parent.mkdir(parents=True, exist_ok=True)
            dst.write_bytes(blob)
            ok += 1
            time.sleep(0.25)
        done["images_saved"] = ok

    # ---- comments.json（覆盖前先备份）----
    if "write_cmt" in plan:
        old = cdir / "comments.json"
        if old.is_file():
            bdir = BACKUP / nid / "comments"
            bdir.mkdir(parents=True, exist_ok=True)
            shutil.copy2(old, bdir / "comments.json")
            done["backup"] = str(bdir / "comments.json")
        write_json(old, plan["write_cmt"])
        done["comments"] = len(plan["write_cmt"])

    # ---- card.json ----
    if plan["need_card"]:
        write_json(cdir / "card.json", plan["card"])
        done["card"] = (f"{plan['card']['total']}/"
                        f"{plan['card']['note_reported']}")

    # ---- comments.txt（从**盘上**的 json 派生，保证同目录自洽）----
    if plan.get("need_txt"):
        arr = read_json(cdir / "comments.json")
        arr = arr if isinstance(arr, list) else []
        (cdir / "comments.txt").write_text(
            render_comments_txt(arr, plan["card"]), encoding="utf-8")
        done["comments_txt"] = True

    return done


def derive_local(nid: str, *, apply_: bool) -> dict[str, Any]:
    """**纯本地**派生 ``card.json`` / ``comments.txt``。

    这两份文件是 ``comments.json`` + ``note.json`` 的函数，本来就不需要
    网络。抓取失败（笔记被删/私密，匿名拿不到）时照样能把目录补成
    自洽状态，比留两个空洞好。
    """
    base = DATA / nid
    cdir = base / "comments"
    arr = read_json(cdir / "comments.json")
    arr = [r for r in arr if isinstance(r, dict)] \
        if isinstance(arr, list) else []
    note = read_json(base / "content" / "note.json")
    note = note if isinstance(note, dict) else {}
    reported = note_reported(note)

    acts: list[str] = []
    card = read_json(cdir / "card.json")
    has_card = isinstance(card, dict) and "total" in card
    if not has_card:
        acts.append("card.json(本地派生)")
    elif card.get("total") != len(arr):
        acts.append("card.json(重算)")
        has_card = False

    if not (cdir / "comments.txt").is_file():
        acts.append("comments.txt(本地派生)")
    if not arr and not (cdir / "comments.json").is_file():
        acts.append("comments.json(空占位)")

    # note.json 的图片字段：抓不到时用**本地** ``urls.json`` / ``下载地址`` 补。
    # 两者本来就是同一份数据的两种写法，合起来能填上 ``images``/``image_count``，
    # 让下游的 ``image_count`` 不再落成 0。
    img_urls = read_json(base / "images" / "urls.json")
    img_urls = img_urls if isinstance(img_urls, list) else []
    if not img_urls:
        dzd = note.get("下载地址")
        img_urls = dzd if isinstance(dzd, list) else []
    need_note_img = bool(img_urls) and not has(note.get("images"))

    done: dict[str, Any] = {}
    if not acts and not need_note_img:
        return {"actions": acts, "applied": done}
    if not apply_:
        if need_note_img:
            acts.append("note.json(图片字段本地补)")
        return {"actions": acts, "applied": done}

    cdir.mkdir(parents=True, exist_ok=True)
    new_card = build_card(nid, reported, arr, "local_derive")
    if not has_card:
        write_json(cdir / "card.json", new_card)
        done["card"] = f"{new_card['total']}/{reported}"
    if "comments.txt(本地派生)" in acts:
        (cdir / "comments.txt").write_text(
            render_comments_txt(arr, new_card), encoding="utf-8")
        done["comments_txt"] = True
    if "comments.json(空占位)" in acts:
        write_json(cdir / "comments.json", [])
        done["comments"] = 0
    if need_note_img:
        note.setdefault("images", img_urls)
        note["image_count"] = len(img_urls)
        write_json(base / "content" / "note.json", note)
        done["note_images"] = len(img_urls)
        acts.append("note.json(图片字段本地补)")
    return {"actions": acts, "applied": done}


def run_pass(targets: list[tuple[str, str]], *, args, want_images: bool,
             allow_upgrade: bool, attempts: int) -> tuple[list[dict], list]:
    """跑一轮。返回 (结果行, 仍然失败的 targets)。"""
    rows: list[dict[str, Any]] = []
    still: list[tuple[str, str]] = []
    total = len(targets)

    for i, (nid, url) in enumerate(targets, start=1):
        tag = f"[{i:>2}/{total}] {nid[:8]}"
        try:
            fresh = probe(url, retries=attempts)
        except Exception as e:  # noqa: BLE001
            # 抓不到（笔记被删/私密）时退化为纯本地派生：
            # card / txt 本来就不需要网络，别让目录留空洞。
            # 但仍然留在 pending 里，后续轮次继续试抓。
            loc = derive_local(nid, apply_=args.apply)
            note_parts = []
            if loc["actions"]:
                note_parts.append(f"本地派生: {'  '.join(loc['actions'])}")
            else:
                note_parts.append("本地无缺口")
            print(f"{tag}  FAIL {type(e).__name__}: {str(e)[:40]}"
                  f"  → {' | '.join(note_parts)}")
            still.append((nid, url))
            rows.append({"id": nid, "ok": False, "degraded": True,
                         "error": f"{type(e).__name__}: {e}",
                         "actions": loc["actions"],
                         "applied": loc["applied"]})
            time.sleep(args.sleep)
            continue

        fresh["url"] = url
        plan = decide(nid, fresh, want_images=want_images,
                      allow_upgrade=allow_upgrade)
        done: dict[str, Any] = {}
        if plan["actions"] and args.apply:
            done = apply(nid, plan)

        summary = "  ".join(plan["actions"]) if plan["actions"] else "OK 无缺口"
        print(f"{tag}  新抓 一级{plan['raw_n']:>2} 楼{plan['raw_replies']:>3}"
              f"  {summary}")
        rows.append({"id": nid, "ok": True, "actions": plan["actions"],
                     "applied": done, "top": plan["raw_n"],
                     "replies": plan["raw_replies"]})
        time.sleep(args.sleep)

    return rows, still


def main() -> int:
    ap = argparse.ArgumentParser(description="补齐 data/ 下 42 帖的缺件")
    ap.add_argument("--apply", action="store_true", help="真写盘（默认只报告）")
    ap.add_argument("--only", default="", help="只处理这些 note_id（逗号分隔）")
    ap.add_argument("--no-images", action="store_true", help="跳过图片下载")
    ap.add_argument("--no-upgrade", action="store_true",
                    help="不合并 comments.json（只补缺文件）")
    ap.add_argument("--sleep", type=float, default=SLEEP_BETWEEN,
                    help=f"篇间隔秒数（默认 {SLEEP_BETWEEN}）")
    ap.add_argument("--passes", type=int, default=3,
                    help="最多几轮（后轮只重试失败篇，默认 3）")
    args = ap.parse_args()
    force_utf8()

    only = {s.strip() for s in args.only.split(",") if s.strip()} or None
    targets = load_targets(only)
    want_images = not args.no_images
    allow_upgrade = not args.no_upgrade

    print(f"{'回填' if args.apply else '干跑'} | {len(targets)} 帖 | "
          f"间隔 {args.sleep}s | 图片 {'开' if want_images else '关'} | "
          f"合并评论 {'开' if allow_upgrade else '关'} | 最多 {args.passes} 轮\n")

    all_rows: list[dict[str, Any]] = []
    pending = targets
    for p in range(1, max(1, args.passes) + 1):
        if not pending:
            break
        if p > 1:
            wait = 20 * (p - 1)
            print(f"\n--- 第 {p} 轮：重试 {len(pending)} 篇 "
                  f"（先等 {wait}s 让配额滑窗过去）---")
            time.sleep(wait)
        rows, pending = run_pass(pending, args=args, want_images=want_images,
                                 allow_upgrade=allow_upgrade, attempts=2)
        by_id = {r["id"]: r for r in all_rows}
        for r in rows:
            by_id[r["id"]] = r          # 后轮覆盖前轮失败记录
        all_rows = list(by_id.values())

    ok = sum(1 for r in all_rows if r.get("ok"))
    fail = len(all_rows) - ok
    print(f"\n成功 {ok} / 失败 {fail}")
    if fail:
        print("仍失败: " + ", ".join(r["id"][:8]
                                   for r in all_rows if not r.get("ok")))
    if not args.apply:
        need = sum(1 for r in all_rows if r.get("actions"))
        print(f"需回填 {need} 帖（加 --apply 执行）")
    REPORT.write_text(json.dumps(all_rows, ensure_ascii=False, indent=1),
                      encoding="utf-8")
    print(f"报告 -> {REPORT}")
    return 0 if fail == 0 else 1


if __name__ == "__main__":
    sys.exit(main())

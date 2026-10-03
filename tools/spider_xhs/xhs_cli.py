# -*- coding: utf-8 -*-
"""小红书一键导出 CLI：一条命令拿到 正文 / 标签 / 图片 / 评论。

用法
----
    # 只看会抓什么（不落盘）
    .\\.venv\\Scripts\\python.exe xhs_cli.py "https://xhslink.cn/o/xxxx" --dry-run

    # 全量导出（默认）
    .\\.venv\\Scripts\\python.exe xhs_cli.py "https://xhslink.cn/o/xxxx"

    # 指定输出目录 / 跳过图片下载
    .\\.venv\\Scripts\\python.exe xhs_cli.py <url> -o D:/out --no-images
    .\\.venv\\Scripts\\python.exe xhs_cli.py <url> --no-comments

依赖：tools\\.venv（curl_cffi / PyExecJS / loguru）+ Node.js
Cookie：从项目根 .env 或环境变量 XHS_COOKIE 读取
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent          # tools/spider_xhs
TOOLS = HERE.parent                             # tools/（source 包在这里）
ROOT = TOOLS.parent                             # 项目根
for p in (str(HERE), str(TOOLS), str(ROOT)):
    if p not in sys.path:
        sys.path.insert(0, p)

DEFAULT_OUT = ROOT / "data" / "xhs"


# ---------- 输出工具（统一 UTF-8，避免 Windows 控制台乱码） ----------

def say(msg: str = "") -> None:
    print(msg, flush=True)


def save_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2),
                    encoding="utf-8")


def save_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


# ---------- cookie 读取（原先在 forensic 包，已移除，内联到此处） ----------

def _load_env(path: Path) -> dict:
    out = {}
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
    """优先级：系统环境变量 > 项目根 .env。"""
    import os
    c = os.environ.get("XHS_COOKIE")
    if c:
        return c.strip()
    return _load_env(HERE.parent.parent / ".env").get("XHS_COOKIE")


def cookie_has(cookie: str, name: str) -> bool:
    return any(p.strip().startswith(f"{name}=") for p in cookie.split(";"))


def parse_note_ref(url: str) -> dict:
    """从链接里抽 note_id 与 xsec_token。短链的真实 ID 要靠抓取后回填。"""
    from urllib.parse import parse_qs, urlparse
    u = urlparse(url)
    segs = [s for s in u.path.split("/") if s]
    note_id = ""
    for s in segs:
        if s in ("explore", "discovery", "item"):
            continue
        if len(s) >= 20 and s.replace("_", "").replace("-", "").isalnum():
            note_id = s
            break
    q = parse_qs(u.query)
    return {"note_id": note_id or (segs[-1] if segs else ""),
            "xsec_token": (q.get("xsec_token") or [""])[0]}


# ---------- 主流程 ----------

def _token_from(note_obj: dict) -> str:
    """从笔记数据里取 xsec_token（作品链接里带）。"""
    import re
    for u in ((note_obj or {}).get("下载地址") or []):
        m = re.search(r"xsec_token=([\w-]+)", str(u))
        if m:
            return m.group(1)
    m = re.search(r"xsec_token=([\w-]+)",
                  str((note_obj or {}).get("作品链接") or ""))
    return m.group(1) if m else ""


def _pick(note_obj: dict, *keys, default=""):
    for k in keys:
        v = note_obj.get(k)
        if v:
            return v
    return default


def fetch_one(url: str, out_root: Path, cookie: str, *,
              images: bool = True, comments: bool = True,
              prefix: str = "", dry_run: bool = False) -> dict:
    """抓单篇，落盘到 <out_root>/<note_id>/{content,images,comments}/。

    返回 {"note_id","ok","title","images","expected","fetched","complete","dir"}
    """
    from source import XHS

    say(f"\n{prefix}=== {url[:70]}")
    ref = parse_note_ref(url)
    note_id = ref.get("note_id") or ""
    xsec = ref.get("xsec_token") or ""
    if not note_id:
        say(f"{prefix}    [X] 链接里没解析出作品 ID")
        return {"note_id": "", "ok": False, "error": "no_note_id"}

    # --- 笔记（顺带展开短链，拿到真 note_id / token）---
    note_obj: dict = {}
    if not dry_run:
        say(f"{prefix}[1/3] 抓笔记...")
        try:
            import asyncio

            tmp = out_root / "_tmp"
            tmp.mkdir(parents=True, exist_ok=True)

            async def _pull():
                async with XHS(
                    cookie=cookie, work_path=str(tmp),
                    image_format="JPEG", record_data=False, note_format="",
                    download_record=False, write_mtime=True,
                    image_download=images, video_download=False,
                    timeout=20, max_retry=2,
                ) as xhs:
                    return await xhs.extract(url, download=images)

            res = asyncio.run(_pull())
            if isinstance(res, list) and res:
                note_obj = res[0]
            elif isinstance(res, dict):
                note_obj = res
        except Exception as e:
            say(f"{prefix}    [!] 笔记抓取失败：{type(e).__name__}: {e}")

    real_id = (note_obj.get("作品ID") or "").strip()
    if real_id:
        note_id = real_id
    xsec = _token_from(note_obj) or xsec

    if dry_run:
        say(f"{prefix}    note_id={note_id}")
        return {"note_id": note_id, "ok": True, "dry_run": True}

    # --- 建目录 ---
    base = out_root / note_id
    cdir, idir, mdir = base / "content", base / "images", base / "comments"
    for d in (cdir, idir, mdir):
        d.mkdir(parents=True, exist_ok=True)

    # --- content ---
    title = _pick(note_obj, "作品标题", "title")
    desc = _pick(note_obj, "作品描述", "desc", "作品描述")
    tags = _pick(note_obj, "作品标签", "tag_list", "作品标签")
    counts = {
        "点赞": _pick(note_obj, "点赞数量", "liked_count"),
        "收藏": _pick(note_obj, "收藏数量", "collected_count"),
        "评论": _pick(note_obj, "评论数量", "comment_count"),
        "分享": _pick(note_obj, "分享数量", "share_count"),
    }
    urls = _pick(note_obj, "下载地址", "image_list", default=[]) or []

    if note_obj:
        save_json(cdir / "note.json", note_obj)
    save_text(cdir / "note.md",
              f"# {title}\n\n## 正文\n{desc}\n\n## 标签\n{tags}\n\n"
              f"## 互动\n{json.dumps(counts, ensure_ascii=False)}\n")
    save_json(cdir / "urls.json", list(urls))
    save_json(cdir / "meta.json", {
        "note_id": note_id, "title": title,
        "author": _pick(note_obj, "作者昵称", "author"),
        "published_at": _pick(note_obj, "发布时间"),
        "counts": counts, "image_count": len(urls),
        "source_url": url,
        "fetched_at": __import__("datetime").datetime.now().isoformat(timespec="seconds"),
    })
    say(f"{prefix}    {title[:36]}")
    say(f"{prefix}    正文 {len(desc)} 字 | 赞{counts['点赞']} 藏{counts['收藏']} "
        f"评{counts['评论']} 转{counts['分享']} | 图片 {len(urls)} 张")

    # --- images：把上游下载的文件搬进 images/ 并规范命名 ---
    got = 0
    if images and note_obj:
        src_dir = out_root / "_tmp" / "Download"
        files = sorted([f for f in src_dir.glob("*")
                        if f.suffix.lower() in (".jpg", ".jpeg", ".png", ".webp")]) \
            if src_dir.is_dir() else []
        for i, f in enumerate(files, 1):
            shutil.copy2(f, idir / f"{i:02d}{f.suffix.lower()}")
            got += 1
        say(f"{prefix}    图片 {got} 张 -> images/")

    # --- comments ---
    expected = fetched = 0
    complete = False
    if comments and note_id and xsec:
        say(f"{prefix}[2/3] 抓评论...")
        try:
            from xhs_utils.xhs_pc import XHSPcAuth
            from apis.xhs_pc_apis import XHS_Apis
            from thread_fetcher import complete_threads, summarize

            auth = XHSPcAuth.from_cookie(cookie)
            apis = XHS_Apis(auth)
            apis.bootstrap()      # 必须：user_id 决定 xy-direction，缺则 406
            ok, msg, top = apis.get_note_all_out_comment(note_id, xsec)
            top = top or []
            stat = complete_threads(apis, top, note_id, xsec, verbose=False)
            if stat["filled"]:
                say(f"{prefix}    楼中楼补全 {stat['filled']} 条"
                    f"（{stat['calls']} 次）")

            threads, subs = [], []
            for c in top:
                replies = []
                for s in (c.get("sub_comments") or []):
                    s["_is_reply"] = True
                    replies.append(s)
                    subs.append(s)
                threads.append({
                    "id": c.get("id", ""),
                    "author": (c.get("user_info") or {}).get("nickname", ""),
                    "ip": c.get("ip_location", ""),
                    "text": (c.get("content") or "").strip(),
                    "likes": int(str(c.get("like_count") or 0) or 0),
                    "time": c.get("create_time", 0),
                    "replies": replies,
                })
            chk = summarize(note_obj, top, subs)
            expected, fetched, complete = (chk["note_reported"],
                                           chk["total"], chk["matched"])

            save_json(mdir / "threads.json", {
                "note_id": note_id, "expected": expected,
                "fetched": fetched, "complete": complete, "threads": threads})
            save_json(mdir / "raw.json", top)   # 上游原始结构，便于复查

            lines = []
            for t in threads:
                lines.append(f"- [{t['author']}] {t['ip']} | 赞{t['likes']} | "
                             f"{t['text'][:70]}")
                for s in t["replies"]:
                    lines.append("    └ [{}] {}".format(
                        (s.get("user_info") or {}).get("nickname", "?"),
                        (s.get("content") or "")[:60]))
            save_text(mdir / "comments.txt",
                      f"笔记页显示 {expected} | 实抓 {fetched} | "
                      f"{'已对齐' if complete else '有缺口'}\n\n"
                      + "\n".join(lines))
            say(f"{prefix}    评论 一级{len(top)}+楼中楼{len(subs)}"
                f"={fetched}（页面显示 {expected}，"
                f"{'已对齐' if complete else '差 %d' % (expected - fetched)}）")
        except Exception as e:
            say(f"{prefix}    [!] 评论抓取失败：{type(e).__name__}: {e}")
    else:
        say(f"{prefix}[2/3] 跳过评论")

    # --- 清理临时下载目录 ---
    tmp = out_root / "_tmp"
    if tmp.is_dir():
        shutil.rmtree(tmp, ignore_errors=True)

    say(f"{prefix}[3/3] 完成 -> {base}")
    return {"note_id": note_id, "ok": bool(note_obj), "title": title,
            "images": got, "expected": expected, "fetched": fetched,
            "complete": complete, "dir": str(base)}


def _update_index(root: Path, rows: list[dict]) -> None:
    """维护 <root>/index.csv：一行一篇，便于 Excel 直接打开筛选。"""
    import csv as _csv
    idx = root / "index.csv"
    header = ["note_id", "标题", "作者", "点赞", "收藏", "评论", "分享",
              "图片数", "评论实抓", "是否对齐", "抓取时间", "目录"]
    exist = {}
    if idx.is_file():
        with idx.open(encoding="utf-8") as f:
            for r in _csv.DictReader(f):
                exist[r["note_id"]] = r
    for r in rows:
        if not r.get("note_id"):
            continue
        exist[r["note_id"]] = {
            "note_id": r["note_id"], "标题": r.get("title", "")[:40],
            "作者": r.get("author", ""), "点赞": r.get("赞", ""),
            "收藏": r.get("藏", ""), "评论": r.get("评", ""),
            "分享": r.get("转", ""), "图片数": r.get("images", 0),
            "评论实抓": r.get("fetched", 0),
            "是否对齐": "是" if r.get("complete") else "否",
            "抓取时间": r.get("time", ""), "目录": r.get("dir", ""),
        }
    with idx.open("w", newline="", encoding="utf-8-sig") as f:
        w = _csv.DictWriter(f, fieldnames=header)
        w.writeheader()
        for nid in sorted(exist):
            w.writerow(exist[nid])


def main() -> int:
    ap = argparse.ArgumentParser(
        description="小红书笔记采集：导出 content / images / comments",
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("url", nargs="?", help="小红书链接（支持 xhslink 短链）")
    ap.add_argument("-o", "--out", default=str(DEFAULT_OUT), help="输出根目录")
    ap.add_argument("-i", "--input", help="批量模式：从 txt 读链接（一行一个）")
    ap.add_argument("--no-images", action="store_true")
    ap.add_argument("--no-comments", action="store_true")
    ap.add_argument("--delay", type=float, default=2.0, help="批量模式篇间间隔秒")
    ap.add_argument("--limit", type=int, default=0, help="批量模式最多抓几篇")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    if not args.url and not args.input:
        ap.error("需要提供 url 或 --input")

    cookie = get_cookie()
    if not cookie:
        say("[X] 未找到 cookie。请在项目根 .env 写入 XHS_COOKIE=...")
        return 2
    say(f"cookie OK（{len(cookie)} 字符，"
        f"web_session={'有' if cookie_has(cookie, 'web_session') else '无'}）")

    out_root = Path(args.out)
    out_root.mkdir(parents=True, exist_ok=True)

    urls = [args.url] if args.url else []
    if args.input:
        f = Path(args.input)
        if not f.is_file():
            say(f"[X] 找不到清单文件：{f}")
            return 3
        urls = [ln.strip() for ln in
                f.read_text(encoding="utf-8").splitlines()
                if ln.strip() and not ln.strip().startswith("#")]
        if args.limit:
            urls = urls[:args.limit]
        say(f"批量模式：{len(urls)} 个链接")

    import datetime
    import time
    results = []
    for i, u in enumerate(urls, 1):
        if i > 1 and args.delay:
            time.sleep(args.delay)
        r = fetch_one(u, out_root, cookie,
                      images=not args.no_images,
                      comments=not args.no_comments,
                      prefix=f"[{i}/{len(urls)}] ", dry_run=args.dry_run)
        if r.get("note_id") and not args.dry_run:
            meta_p = out_root / r["note_id"] / "content" / "meta.json"
            if meta_p.is_file():
                m = json.loads(meta_p.read_text(encoding="utf-8"))
                c = m.get("counts", {})
                r.update({"author": m.get("author", ""), "赞": c.get("点赞"),
                          "藏": c.get("收藏"), "评": c.get("评论"),
                          "转": c.get("分享"), "time": m.get("fetched_at", "")})
        results.append(r)

    if not args.dry_run and results:
        _update_index(out_root, results)
        ok = sum(1 for r in results if r.get("ok"))
        full = sum(1 for r in results if r.get("complete"))
        say("")
        say(f"[汇总] {len(results)} 篇 | 成功 {ok} | 评论完全对齐 {full}")
        say(f"[索引] {out_root / 'index.csv'}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

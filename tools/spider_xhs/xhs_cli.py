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


# ---------- 主流程 ----------

def main() -> int:
    ap = argparse.ArgumentParser(
        description="小红书一键导出：文案 + 图片 + 评论",
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("url", help="小红书链接（支持 xhslink 短链）")
    ap.add_argument("-o", "--out", default=str(DEFAULT_OUT), help="输出目录")
    ap.add_argument("--no-images", action="store_true", help="跳过图片下载")
    ap.add_argument("--no-comments", action="store_true", help="跳过评论抓取")
    ap.add_argument("--dry-run", action="store_true", help="只解析，不请求接口")
    args = ap.parse_args()

    out_dir = Path(args.out)
    note_dir = out_dir / "note"
    img_dir = out_dir / "images"
    cmt_dir = out_dir / "comments"

    # 0) cookie
    from forensic.xhs_comments import get_cookie, cookie_has
    cookie = get_cookie()
    if not cookie:
        say("[X] 未找到 cookie。请在项目根 .env 写入 XHS_COOKIE=...")
        return 2
    say(f"[1/4] cookie OK（{len(cookie)} 字符，"
        f"web_session={'有' if cookie_has(cookie, 'web_session') else '无'}）")

    # 1) 链接 -> note_id / xsec_token（短链需先展开）
    from source import XHS
    from forensic.xhs_comments import parse_note_ref
    short = args.url.strip()
    ref = parse_note_ref(short)
    note_id = ref.get("note_id") or ""
    xsec = ref.get("xsec_token") or ""
    say(f"[2/4] 短链解析: note_id = {note_id or '(待展开)'}")
    if not note_id:
        say("    [X] 链接里没解析出作品 ID，请确认链接完整")
        return 3

    if args.dry_run:
        say("    --dry-run：到此为止，不发请求")
        return 0

    # 2) 笔记：正文 / 标签 / 图片
    say("[3/4] 抓取笔记（正文 / 标签 / 图片）...")
    note_obj: dict = {}
    try:
        import asyncio

        async def _pull():
            async with XHS(
                cookie=cookie,
                work_path=str(out_dir),
                image_format="JPEG",
                record_data=True,
                note_format="all",
                download_record=False,
                write_mtime=True,
                image_download=not args.no_images,
                video_download=False,
                timeout=20,
                max_retry=2,
            ) as xhs:
                return await xhs.extract(args.url, download=not args.no_images)

        res = asyncio.run(_pull())
        if isinstance(res, list) and res:
            note_obj = res[0]
        elif isinstance(res, dict):
            note_obj = res
    except Exception as e:
        say(f"    [!] 笔记抓取失败：{type(e).__name__}: {e}")

    if note_obj:
        save_json(note_dir / "note.json", note_obj)
        # 短链展开后拿到的才是真 note_id / xsec_token（比短链里的可靠）
        real_id = (note_obj.get("作品ID") or "").strip()
        if real_id and len(real_id) > len(note_id or ""):
            note_id = real_id
        token = _token_from(note_obj) or xsec
        if token:
            xsec = token
        # 关键字段：XHS-Downloader 的字典键是中文
        def g(*keys, default=""):
            for k in keys:
                if k in note_obj and note_obj[k]:
                    return note_obj[k]
            return default
        title = g("作品标题", "title")
        desc = g("作品描述", "desc", "作品描述")
        tags = g("作品标签", "tag_list", "作品标签")
        counts = {
            "点赞": g("点赞数量", "liked_count"),
            "收藏": g("收藏数量", "collected_count"),
            "评论": g("评论数量", "comment_count"),
            "分享": g("分享数量", "share_count"),
        }
        urls = g("下载地址", "image_list", default=[]) or []
        save_text(note_dir / "note.md",
                  f"# {title}\n\n## 正文\n{desc}\n\n## 标签\n{tags}\n\n"
                  f"## 互动\n{json.dumps(counts, ensure_ascii=False)}\n")
        say(f"    标题: {title[:40]}")
        say(f"    正文: {len(desc)} 字 | 标签: {len(str(tags))} 字")
        say(f"    互动: 赞{counts['点赞']} 藏{counts['收藏']} "
            f"评{counts['评论']} 转{counts['分享']}")
        say(f"    图片: {len(urls)} 张 -> {img_dir}")
        if urls:
            save_json(note_dir / "image_urls.json", list(urls))

    # 3) 评论
    if args.no_comments:
        say("    (--no-comments：跳过评论)")
    else:
        say("[4/4] 抓取评论（全部，含楼中楼）...")
        try:
            from xhs_utils.xhs_pc import XHSPcAuth
            from apis.xhs_pc_apis import XHS_Apis

            auth = XHSPcAuth.from_cookie(cookie)
            apis = XHS_Apis(auth)
            apis.bootstrap()          # 必须：user_id 决定 xy-direction，缺则 406
            if not xsec:
                say("    [!] 缺 xsec_token，评论接口会拒绝；"
                    "请用浏览器分享得到的完整链接")
                raise RuntimeError("missing xsec_token")
            ok, msg, top = apis.get_note_all_out_comment(note_id, xsec)
            top = top or []
            # 笔记页显示的「评论数量」= 一级 + 楼中楼。工具只给一级评论，
            # 楼中楼以 sub_comments 内联返回，需显式展开。
            subs = []
            for c in top:
                for s in (c.get("sub_comments") or []):
                    s["_parent_id"] = c.get("id", "")
                    s["_is_reply"] = True
                    subs.append(s)
            comments = top + subs
            save_json(cmt_dir / "comments.json", comments)
            save_json(cmt_dir / "comments_top.json", top)
            if subs:
                save_json(cmt_dir / "comments_replies.json", subs)

            lines = []
            for c in top:
                ui = c.get("user_info") or {}
                txt = (c.get("content") or "").replace("\n", " ").strip()
                lines.append(
                    f"- [一级] {ui.get('nickname', '?')} | "
                    f"{c.get('ip_location', '?')} | 赞{c.get('like_count', '0')} | {txt[:60]}")
                for s in (c.get("sub_comments") or []):
                    sui = s.get("user_info") or {}
                    stxt = (s.get("content") or "").replace("\n", " ").strip()
                    lines.append(
                        f"    └ [{sui.get('nickname', '?')} 回复] {stxt[:52]}")
            header = (f"一级评论 {len(top)} 条 | 楼中楼 {len(subs)} 条 | "
                      f"合计 {len(comments)} 条\n")
            save_text(cmt_dir / "comments.txt", header + "\n" + "\n".join(lines))
            say(f"    一级 {len(top)} + 楼中楼 {len(subs)} = {len(comments)} 条"
                f" -> {cmt_dir}")
        except Exception as e:
            say(f"    [!] 评论抓取失败：{type(e).__name__}: {e}")

    say("")
    say(f"[OK] 全部产物在 {out_dir}")
    return 0


def _token_from(note_obj: dict) -> str:
    """从笔记数据里取 xsec_token（下载链接里通常带）。"""
    import re
    urls = (note_obj or {}).get("下载地址") or []
    for u in urls:
        m = re.search(r"xsec_token=([\w-]+)", str(u))
        if m:
            return m.group(1)
    link = (note_obj or {}).get("作品链接") or ""
    m = re.search(r"xsec_token=([\w-]+)", str(link))
    return m.group(1) if m else ""


if __name__ == "__main__":
    raise SystemExit(main())

"""xhs-cli 命令行入口。

用法::

    # 单个链接
    python -m xhs_cli "https://www.xiaohongshu.com/discovery/item/xxx?xsec_token=..."

    # 链接清单（每行一个，# 开头为注释）
    python -m xhs_cli --input urls.txt

    # 只审计已有数据
    python -m xhs_cli --audit-only

匿名保证：本入口不读取任何 cookie/env；每次请求前由 anonymity.assert_anonymous 校验。
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

from . import __version__
from .audit import print_report
from .extractors import comments_first, images as images_mod, note as note_mod
from .page import FetchError, _anon_browser, download_images, fetch_share_page, warmup
from .share import (ShortLinkError, UnsupportedLink, can_fetch,
                    expand_short_link, is_short_link, normalize)


def _force_utf8() -> None:
    """Windows 控制台默认 GBK，遇到 emoji 直接 UnicodeEncodeError。

    小红书昵称/内容高频出现 emoji，所以必须重配。
    """
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:  # noqa: BLE001
            pass


def cmd_parse(args) -> int:
    """``xhs-cli parse <链接>``：HTTP 直连解析，输出 JSON。

    不启动浏览器、不需要 Playwright。这是网站后端的同一条链路。
    """
    _force_utf8()
    import json
    from .core import FetchError, parse_link
    from .core.link import UnsupportedLink

    try:
        result = parse_link(args.link)
    except UnsupportedLink as exc:
        print(f"[X] {exc}", file=sys.stderr)
        return 2
    except FetchError as exc:
        print(f"[X] 抓取失败({exc.kind}): {exc}", file=sys.stderr)
        return 3

    payload = {
        "note": result["note"],
        "images": result["images"],
        "comments": result["comments"],
        "declared": result["declared"],
        "got": result["got"],
        "complete": result["complete"],
        "note_id": result["note_id"],
        "elapsed_ms": result["elapsed_ms"],
    }

    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2, default=str))
    else:
        n = result["note"]
        print(f"note_id  : {result['note_id']}")
        print(f"作者     : {n['author']}  IP {n['ip_location'] or '(未提供)'}")
        print(f"赞/藏/评/享: {n['liked']} {n['collected']} "
              f"{n['comment_count']} {n['share']}")
        print(f"标题     : {n['title']}")
        print(f"正文     : {n['desc'][:80]}")
        print(f"图片     : {len(result['images'])} 张")
        print(f"评论     : {result['got']} 条"
              f"（页面声明 {result['declared']}，"
              f"{'完整' if result['complete'] else '首屏数据'}）")
        for c in result["comments"]:
            tag = ("[作者]" if c["is_author"] else "") + \
                  ("(回复)" if c["_is_reply"] else "")
            print(f"  {tag:<9}{c['nickname'][:14]:<15}"
                  f"{c['content'][:34]:<36}{c['ip_location'] or '-':<6}"
                  f"赞{c['like_count']}")
        if args.save:
            out = Path(args.save)
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(json.dumps(payload, ensure_ascii=False, indent=2),
                           encoding="utf-8")
            print(f"[saved] {out}", file=sys.stderr)
    return 0
from .storage.layout import NoteLayout

DEFAULT_OUT = Path(__file__).resolve().parents[2] / "xhs_data"


def _log(msg: str) -> None:
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    print(msg, flush=True)


def collect_one(ref, out_root: Path, *, skip_images: bool = False,
                proxy: str | None = None, page=None, navigated: bool = False,
                engine: str = "chromium",
                cookies_file: str | None = None) -> dict:
    """采集单篇，返回结果记录。

    ``page``        为复用页面；不传则自建（仅单篇调试用）。
    ``navigated``   True 表示页面已停在目标详情页（短链展开后），无需再跳转。
    """
    lay = NoteLayout(out_root, ref.note_id).ensure()

    # 分项判断：content / images / comments 各自独立补全，
    # 任一缺失都要继续抓，不能因为 content 存在就整体跳过。
    have_note = bool(lay.read_note())
    have_imgs = bool(lay.image_files()) or skip_images
    have_cmts = lay.has_comments()
    if have_note and have_imgs and have_cmts:
        _log(f"  [skip] 数据齐全 {ref.note_id[:12]}")
        return {"note_id": ref.note_id, "status": "skipped"}

    todo = []
    if not have_note:
        todo.append("content")
    if not have_imgs:
        todo.append("images")
    if not have_cmts:
        todo.append("comments")
    _log(f"  待补: {'/'.join(todo)}")

    if page is not None:
        page_data = fetch_share_page(ref.url, ref.note_id, page=page,
                                     navigated=navigated)
    else:
        with _anon_browser(proxy, engine=engine,
                           cookies_file=cookies_file) as (_br, pg):
            page_data = fetch_share_page(ref.url, ref.note_id, page=pg)

    if not have_note:
        lay.write_note(note_mod.to_note_dict(page_data))
        _log(f"  content ok | 正文{len(page_data.desc)}字 | 标签{len(page_data.tags)}个")
    else:
        _log("  content 已存在，跳过")

    img_stats: dict = {"declared": 0, "downloaded": 0, "complete": False}
    urls = images_mod.image_urls(page_data.images)
    if urls:
        lay.write_image_urls(urls)
        img_stats["declared"] = len(urls)
        if not have_imgs:
            results = download_images(urls, lay.images, proxy=proxy, page=page)
            img_stats = images_mod.summarize(results, len(urls))
            _log(f"  images ok | {img_stats['downloaded']}/{img_stats['declared']} 张 "
                 f"({img_stats['bytes'] // 1024} KB)")
        else:
            img_stats["downloaded"] = len(lay.image_files())
            img_stats["complete"] = img_stats["downloaded"] >= img_stats["declared"]
            _log(f"  images 已存在 ({img_stats['downloaded']} 张)，跳过")

    if not have_cmts:
        top, replies = comments_first.normalize_comments(page_data.comments)
        card = comments_first.summarize(top, replies, page_data.comment_count)
        inline_got, inline_want = comments_first.inline_coverage(top)
        card["inline_replies"] = f"{inline_got}/{inline_want}"
        card["note_id"] = ref.note_id
        card["image_stats"] = img_stats

        lay.write_comments(top, card, replies)
        _log(f"  comments ok | 一级{card['top_level']} + 楼中楼{card['replies']} "
             f"= {card['total']}"
             + (f" (平台显示 {card['note_reported']}, 首批数据)"
                if card["partial"] else ""))
    else:
        card = lay.read_card()
        _log("  comments 已存在，跳过")

    return {
        "note_id": ref.note_id,
        "status": "ok",
        "desc_len": len(page_data.desc),
        "images": img_stats["downloaded"],
        "comments": int(card.get("total") or 0),
        "partial": bool(card.get("partial")),
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="xhs",
        description="匿名免登录采集小红书笔记（文案/图片/首批评论）",
    )
    # 注意：不能用位置参数 nargs="?" —— 它会抢走子命令名 'parse'。
    ap.add_argument("--url", dest="url", help="单个分享链接")
    ap.add_argument("--input", help="链接清单文件（每行一个）")
    ap.add_argument("--out", default=str(DEFAULT_OUT), help="输出根目录")
    ap.add_argument("--skip-images", action="store_true", help="不下载图片")
    ap.add_argument("--audit-only", action="store_true", help="只审计已有数据")
    ap.add_argument("--proxy", default=None, help="代理，如 http://127.0.0.1:7890")
    ap.add_argument("--sleep", type=float, default=2.0, help="篇间间隔（秒）")
    ap.add_argument("--engine", default="chromium", choices=["chromium", "chrome"],
                    help="浏览器引擎：chromium=自带内核(默认)，"
                         "chrome=本机Chrome(TLS指纹更像真人，仍匿名隔离)")
    ap.add_argument("--no-headless", action="store_true",
                    help="显示浏览器窗口（调试用）")
    ap.add_argument("--cookies", default=None, metavar="FILE",
                    help="注入 cookie JSON（非匿名模式，token 失效时补救用）")
    ap.add_argument("--version", action="version", version=f"xhs-cli {__version__}")
    ps = ap.add_subparsers(dest="cmd")
    pp = ps.add_parser("parse", help="HTTP 直连解析一个链接（不启动浏览器）")
    pp.add_argument("link", help="小红书短链或长链")
    pp.add_argument("--json", action="store_true", help="输出机器可读 JSON")
    pp.add_argument("--save", metavar="FILE", help="同时落盘 JSON")

    args = ap.parse_args(argv)

    if args.cmd == "parse":
        return cmd_parse(args)

    out_root = Path(args.out)

    if args.audit_only:
        print_report(out_root)
        return 0

    urls: list[str] = []
    if getattr(args, "url", None):
        urls.append(args.url)
    if args.input:
        p = Path(args.input)
        if not p.is_file():
            _log(f"[X] 找不到输入文件: {p}")
            return 2
        # 兼容两种换行：真实换行 与 字面量 "\n"（某些 shell 写文件时会转义失败）
        raw_text = p.read_text(encoding="utf-8-sig", errors="replace")
        raw_text = raw_text.replace("\\r\\n", "\n").replace("\\n", "\n")
        for line in raw_text.splitlines():
            line = line.strip().lstrip("\ufeff")
            if line and not line.startswith("#"):
                urls.append(line)

    if not urls:
        ap.print_help()
        return 2

    _log(f"[..] 待采集 {len(urls)} 条 | 输出 {out_root} | "
          f"{'注入cookie:' + args.cookies if args.cookies else '匿名模式（无 cookie）'}"
          f" | 引擎={args.engine}")

    ok = skipped = failed = 0
    # 全程复用同一个「全新匿名」浏览器上下文：既保证不携带登录态，
    # 也避免每篇重启浏览器的开销。
    with _anon_browser(args.proxy, engine=args.engine,
                       headless=not args.no_headless,
                       cookies_file=args.cookies) as (_br, page):
        _log("[..] 预热访客会话（访问首页）…")
        if warmup(page):
            _log("[OK] 访客会话就绪")
        else:
            _log("[!] 预热未成功，仍继续尝试")

        for i, raw in enumerate(urls, 1):
            _log(f"\n[{i}/{len(urls)}] {raw[:76]}")
            navigated = False
            try:
                if is_short_link(raw):
                    # 短链：用匿名浏览器跟随跳转，拿新鲜 token
                    ref = expand_short_link(page, raw)
                    navigated = True
                    _log(f"  短链已展开 note_id={ref.note_id} source={ref.source}")
                else:
                    ref = normalize(raw)
            except (UnsupportedLink, ShortLinkError) as exc:
                _log(f"  [FAIL] 链接不支持: {exc}")
                failed += 1
                continue

            feasible, why = can_fetch(ref)
            if not feasible:
                _log(f"  [SKIP] {why}")
                skipped += 1
                continue
            if not navigated:
                _log(f"  note_id={ref.note_id} source={ref.source}")

            try:
                result = collect_one(ref, out_root,
                                     skip_images=args.skip_images,
                                     proxy=args.proxy, page=page,
                                     navigated=navigated,
                                     engine=args.engine,
                                     cookies_file=args.cookies)
                if result["status"] == "skipped":
                    skipped += 1
                else:
                    ok += 1
            except FetchError as exc:
                _log(f"  [FAIL] {exc} (kind={exc.kind})")
                failed += 1
            except Exception as exc:  # noqa: BLE001
                _log(f"  [FAIL] {type(exc).__name__}: {exc}")
                failed += 1

            if args.sleep:
                page.wait_for_timeout(int(args.sleep * 1000))

    _log(f"\n[完成] 成功 {ok} | 跳过 {skipped} | 失败 {failed}")
    _log(f"[审计] 输出目录: {out_root}")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
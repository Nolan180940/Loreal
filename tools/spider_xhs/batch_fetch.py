# -*- coding: utf-8 -*-
"""批量抓取：按 note_id 落盘，目录结构 data/<note_id>/{content,images,comments}

用法（tools\\.venv 解释器）：
    .\\.venv\\Scripts\\python.exe batch_fetch.py
    .\\.venv\\Scripts\\python.exe batch_fetch.py --limit 5
    .\\.venv\\Scripts\\python.exe batch_fetch.py --resume
    .\\.venv\\Scripts\\python.exe batch_fetch.py --input my_urls.txt

风控策略
--------
- 串行，不并发；每篇之间 SLEEP 秒，每页评论 PAGE_SLEEP 秒
- 连续失败 FAIL_LIMIT 次即整体停止（避免把账号跑废）
- 429/风控类响应触发指数退避（BACKOFF_BASE * 2^n，上限 60s）
- 每篇抓完立刻写 .state/done.json，中断可 --resume 续跑
"""

from __future__ import annotations

import argparse
import json
import random
import re
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
TOOLS = HERE.parent
ROOT = TOOLS.parent
for p in (str(HERE), str(TOOLS)):
    if p not in sys.path:
        sys.path.insert(0, p)

DATA = ROOT / "data"
STATE = DATA / ".state" / "done.json"
RUNS = DATA / ".state" / "runs.jsonl"

SLEEP = 3.0          # 篇与篇之间（秒）
PAGE_SLEEP = 1.0     # 评论翻页之间（秒）
BACKOFF_BASE = 20.0  # 退避基数
MAX_BACKOFF = 180.0
FAIL_LIMIT = 3       # 连续失败上限
RETRY = 2            # 单请求重试次数
NOTE_RETRY = 2       # 单篇因熔断失败后的重试次数（461 是 note 级熔断，重试少）
COOLDOWN = 45.0      # 熔断后静置（秒）


def _force_utf8() -> None:
    """控制台默认 GBK，遇到 emoji/生僻字会 UnicodeEncodeError 直接崩掉。"""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


# 直接持有日志文件句柄：外部 shell 管道（`2>&1 | Tee-Object`）会先按控制台
# 代码页（中文 Windows 是 GBK/936）解码 Python 的 UTF-8 字节，再重新编码写盘，
# 于是中文全部变成「绛惧悕灏辩华」这类 mojibake。绕开管道由本脚本自己落盘。
_LOG_FH = None
LOG_PATH = ROOT / "batch_log.txt"


def _open_log() -> None:
    global _LOG_FH
    if _LOG_FH is None:
        _LOG_FH = open(LOG_PATH, "a", encoding="utf-8", errors="replace")


def log(msg: str) -> None:
    """同时写控制台与 UTF-8 日志文件；日志文件是唯一可信的输出源。"""
    _open_log()
    if _LOG_FH is not None:
        try:
            _LOG_FH.write(msg + "\n")
            _LOG_FH.flush()
        except OSError:
            pass
    try:
        print(msg, flush=True)
    except UnicodeEncodeError:
        enc = getattr(sys.stdout, "encoding", None) or "gbk"
        print(msg.encode(enc, errors="replace").decode(enc, errors="replace"),
              flush=True)


def read_cookie() -> str:
    env = ROOT / ".env"
    if env.is_file():
        for ln in env.read_text(encoding="utf-8", errors="replace").splitlines():
            if ln.startswith("XHS_COOKIE="):
                return ln.split("=", 1)[1].strip()
    raise SystemExit("[X] 未找到 .env 里的 XHS_COOKIE")


def load_state() -> set:
    if STATE.is_file():
        try:
            return set(json.loads(STATE.read_text(encoding="utf-8")))
        except Exception:
            return set()
    return set()


def save_state(done: set) -> None:
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(sorted(done), ensure_ascii=False, indent=1),
                     encoding="utf-8")


def log_run(rec: dict) -> None:
    RUNS.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(rec, ensure_ascii=False) + "\n"
    # 追加模式每次开合，进程被杀可能留下半行；读侧需容错。
    # 这里统一用 "a" 且不换行符问题——jsonl 本身允许按行解析。
    with RUNS.open("a", encoding="utf-8") as f:
        f.write(line)
        f.flush()


def is_risk(exc: Exception) -> bool:
    s = str(exc).lower()
    return any(k in s for k in ("3000", "频繁", "risk", "limit", "登录已过期"))


def load_targets(input_file: str | None) -> list[dict]:
    """优先读 brand_posts.json；也支持纯链接清单（一行一个 URL）。

    过滤非法 note_id：XHS 笔记 ID 恒为 24 位小写 hex。搜索结果里偶有
    ``<uuid>#<ts>`` 形态的空壳条目（title/author 全空），ID 不合法且
    抓下来必然报「笔记数据为空」，直接剔除，不浪费配额也不污染失败列表。
    """
    p = DATA / "search" / "brand_posts.json"
    if input_file:
        rows = []
        for ln in Path(input_file).read_text(encoding="utf-8").splitlines():
            ln = ln.strip()
            if not ln or ln.startswith("#"):
                continue
            rows.append({"note_id": "", "url": ln,
                         "xsec_token": _tok(ln), "title": "", "author": "",
                         "likes": "", "comments": ""})
        return rows
    if not p.is_file():
        raise SystemExit(f"[X] 缺少 {p}")
    rows = json.loads(p.read_text(encoding="utf-8"))
    ok, bad = [], []
    for r in rows:
        nid = (r.get("note_id") or "")
        m = re.search(r"/explore/([0-9a-f]{24})", r.get("url") or "")
        if m:
            nid = m.group(1)          # 以 URL 里的 24 位 hex 为准
        if re.fullmatch(r"[0-9a-f]{24}", nid):
            r["note_id"] = nid
            ok.append(r)
        else:
            bad.append(r)
    if bad:
        log(f"[..] 剔除 {len(bad)} 条非法 note_id（{len(rows) - len(bad)} 条有效）")
    return ok


def _tok(url: str) -> str:
    import re
    m = re.search(r"xsec_token=([\w-]+)", url)
    return m.group(1) if m else ""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0, help="只抓前 N 篇")
    ap.add_argument("--resume", action="store_true", help="跳过已完成的")
    ap.add_argument("--input", default=None, help="链接清单文件（每行一个 URL）")
    ap.add_argument("--no-images", action="store_true", help="不下载图片")
    ap.add_argument("--only", default="", help="只抓指定 note_id（调试用）")
    ap.add_argument("--content-only", action="store_true",
                    help="只抓正文与图片，跳过评论（评论区被限流时用）")
    ap.add_argument("--anon", action="store_true",
                    help="评论走匿名会话轮换（零账号，主号零参与零风险）")
    args = ap.parse_args()
    _force_utf8()

    from thread_fetcher import (RiskError, complete_threads, fetch_top_comments,
                                summarize)
    from xhs_utils.xhs_pc import XHSPcAuth
    from apis.xhs_pc_apis import XHS_Apis
    from source import XHS

    cookie = read_cookie()
    apis = auth = None
    if not args.anon or not args.content_only:
        # 主号仅用于 content（HTML 抓取）或非匿名评论；纯匿名评论不需要它
        try:
            auth = XHSPcAuth.from_cookie(cookie)
            apis = XHS_Apis(auth)
            apis.bootstrap()
            log(f"[OK] 签名就绪 uid={auth.user_id}")
        except Exception as e:
            if args.anon:
                log(f"[..] 主号 bootstrap 失败（{str(e)[:50]}），"
                    f"评论走匿名不受影响；content 已抓过的可继续")
            else:
                raise

    pool = None
    if args.anon:
        from anon_pool import AnonPool
        pool = AnonPool(log=log)
        log("[..] 匿名模式：评论走访客会话轮换，主号仅用于 content（HTML）")

    targets = load_targets(args.input)
    done = load_state() if args.resume else set()
    if not args.resume and STATE.is_file():
        # 非 resume 模式也跳过已存在的目录内容，避免重复抓取
        for t in targets:
            nid = t.get("note_id") or ""
            if nid and (DATA / nid / "content" / "note.json").is_file():
                done.add(nid)
    log(f"[..] 目标 {len(targets)} 篇，已完成 {len(done)} 篇")

    if args.only:
        only_ids = {(t.get("note_id") or "") for t in targets
                    if (t.get("note_id") or "").startswith(args.only)}
        targets = [t for t in targets
                   if (t.get("note_id") or "").startswith(args.only)]
        done = {n for n in done if n not in only_ids}
        if not targets:
            log(f"[X] --only {args.only} 未匹配到目标")
            return 1
        log(f"[..] --only {args.only} → 只抓 {len(targets)} 篇")

    ok_n = fail_n = 0
    fails: list[str] = []
    backoff = 0
    note_try = 0
    i = 0
    total = len(targets)

    while i < total:
        idx = i + 1
        t = targets[i]
        nid = t.get("note_id") or ""
        url = t.get("url") or ""
        if not nid:
            i += 1
            continue
        if nid in done:
            log(f"[{idx}/{total}] skip {nid}")
            i += 1
            continue
        if args.limit and ok_n + fail_n >= args.limit:
            log(f"[..] 达到 --limit {args.limit}，停止")
            break

        base = DATA / nid
        (base / "content").mkdir(parents=True, exist_ok=True)
        (base / "images").mkdir(parents=True, exist_ok=True)
        (base / "comments").mkdir(parents=True, exist_ok=True)

        log(f"\n[{idx}/{len(targets)}] {nid} {t.get('title','')[:24]}")
        t0 = time.time()
        rec = {"note_id": nid, "title": t.get("title", ""), "ts": time.strftime("%Y-%m-%d %H:%M:%S")}

        try:
            # --- content ---
            if not (base / "content" / "note.json").is_file():
                import asyncio

                async def _note():
                    async with XHS(cookie=cookie, work_path=str(base),
                                   image_format="JPEG", record_data=False,
                                   note_format="", download_record=False,
                                   write_mtime=True,
                                   image_download=not args.no_images,
                                   video_download=False, timeout=25,
                                   max_retry=RETRY) as x:
                        return await x.extract(url, download=not args.no_images)

                notes = asyncio.run(_note())
                note = (notes or [{}])[0] if isinstance(notes, list) else (notes or {})
                if not note:
                    raise RuntimeError("笔记数据为空（可能 xsec_token 过期）")
                (base / "content" / "note.json").write_text(
                    json.dumps(note, ensure_ascii=False, indent=2), encoding="utf-8")
                (base / "content" / "note.md").write_text(
                    f"# {note.get('作品标题','')}\n\n"
                    f"作者：{note.get('作者昵称','')}\n"
                    f"发布：{note.get('发布时间','')}\n"
                    f"互动：赞{note.get('点赞数量','')} 藏{note.get('收藏数量','')} "
                    f"评{note.get('评论数量','')} 转{note.get('分享数量','')}\n\n"
                    f"## 正文\n{note.get('作品描述','')}\n\n"
                    f"## 标签\n{note.get('作品标签','')}\n", encoding="utf-8")
                imgs = note.get("下载地址") or []
                (base / "images" / "urls.json").write_text(
                    json.dumps(list(imgs), ensure_ascii=False, indent=2),
                    encoding="utf-8")
                n_img = _collect_images(base)
                rec["images"] = n_img
                log(f"    content ok | 正文{len(str(note.get('作品描述','')))}字 "
                    f"| 图片{n_img}张")

            # --- comments ---
            if not args.content_only and not (base / "comments" / "card.json").is_file():
                tok = t.get("xsec_token") or _tok(url)
                if not tok:
                    raise RuntimeError("缺 xsec_token")

                # 进度日志必须够密：限速调保守后（每页 2.5s），若按「每 5 页」
                # 打印，中间会有十几秒无输出，看起来就像卡死。改为按时间心跳。
                def _pg(page, n, more, resumed=False, _t=[time.time()]):
                    now = time.time()
                    if resumed:
                        log(f"      断点续抓，已载入 {n} 条")
                        _t[0] = now
                    elif page == 1 or not more or now - _t[0] >= 8:
                        log(f"      一级评论 第{page}页 累计{n}条"
                            f"{'（还有更多）' if more else '（已到底）'}"
                            f"  {now - _t[0]:.0f}s")
                        _t[0] = now

                ck_dir = base / "comments" / ".ckpt"
                req = pool.request if pool else None
                tops = fetch_top_comments(apis, nid, tok, sleep=PAGE_SLEEP,
                                          progress=_pg,
                                          ckpt=ck_dir / "top.json", req=req)
                log(f"      一级评论抓完，共 {len(tops)} 条")

                need = sum(1 for c in tops
                           if int(str(c.get("sub_comment_count") or 0) or 0)
                           > len(c.get("sub_comments") or []))
                if need and not pool:
                    def _tg(i, tot, cid, _t=[time.time()]):
                        now = time.time()
                        if i == 1 or i == tot or now - _t[0] >= 15:
                            log(f"      楼中楼 {i}/{tot}（{cid[-8:]}）"
                                f"  {now - _t[0]:.0f}s")
                            _t[0] = now

                    stat = complete_threads(apis, tops, nid, tok,
                                            sleep=PAGE_SLEEP, verbose=False,
                                            progress=_tg, ckpt_dir=ck_dir,
                                            req=req)
                else:
                    # 匿名模式：sub/page 对访客会话完全关闭（首请求即 461），
                    # 跳过补楼，直接用一级响应自带的 inline sub_comments
                    # （实测覆盖率 84.5%）。缺口等主号限流解除后补。
                    if need and pool:
                        n_inline = sum(len(c.get("sub_comments") or [])
                                       for c in tops)
                        n_want = sum(int(str(c.get("sub_comment_count") or 0) or 0)
                                     for c in tops)
                        log(f"      楼中楼: 匿名跳过 sub 接口，用 inline "
                            f"{n_inline}/{n_want}（{n_inline/max(n_want,1):.0%}）")
                    stat = {"filled": 0, "gaps": [], "calls": 0}

                replies = []
                for c in tops:
                    for s in (c.get("sub_comments") or []):
                        s["_parent_id"] = c.get("id", "")
                        s["_is_reply"] = True
                        replies.append(s)
                chk = summarize(note if (note := _safe_json(base)) else {}, tops, replies)
                shown = (f"笔记显示 {chk['note_reported']}" if chk["reported_known"]
                         else "笔记未给出评论数")
                (base / "comments" / "comments.json").write_text(
                    json.dumps(tops + replies, ensure_ascii=False, indent=2),
                    encoding="utf-8")
                (base / "comments" / "card.json").write_text(json.dumps({
                    "note_id": nid, **chk,
                    "thread_fill_calls": stat["calls"],
                    "thread_gaps": stat["gaps"],
                    "anon_partial": bool(pool) and not chk["matched"],
                }, ensure_ascii=False, indent=2), encoding="utf-8")
                _write_comments_txt(base, tops, replies, chk)
                # 成功后清掉断点，避免脏数据影响下次重抓
                if ck_dir.is_dir():
                    for f in ck_dir.glob("*.json"):
                        try:
                            f.unlink()
                        except OSError:
                            pass
                    try:
                        ck_dir.rmdir()
                    except OSError:
                        pass
                rec["comments"] = chk["total"]
                rec["expected"] = chk["note_reported"]
                rec["complete"] = chk["matched"] or bool(pool)
                rec["anon_partial"] = bool(pool) and not chk["matched"]
                log(f"    comments ok | 一级{chk['top_level']} + 楼中楼"
                    f"{chk['replies']} = {chk['total']} "
                    f"({shown}, "
                    f"{'已对齐' if chk['matched'] else '差 %d' % chk['diff']}"
                    f"{' [匿名部分]' if rec['anon_partial'] else ''})")

            if args.content_only:
                # 只抓内容不算完成，否则 --resume 会永久跳过其评论
                rec["status"] = "content_only"
                rec["sec"] = round(time.time() - t0, 1)
                log(f"    [内容完成] 评论待限流解除后补抓")
                log_run(rec)
                i += 1
                time.sleep(SLEEP + random.uniform(0, 1.5))
                continue

            done.add(nid)
            save_state(done)
            ok_n += 1
            backoff = 0
            note_try = 0
            rec["status"] = "ok"
            rec["sec"] = round(time.time() - t0, 1)
            log(f"    [OK] {rec['sec']}s")
            fails.clear()

        except RiskError as e:
            # 主号模式（2026-09-30 实测）：461 一旦出现就是**账号级限流**，
            # 继续抓只会连续 461 并加深限制 → 立即整体停止。
            # 匿名模式：AnonPool 每次请求都用新会话，理论上不应 461；
            # 若出现说明平台收紧了匿名配额 → 同样停止，避免浪费会话。
            rec["status"] = "throttled"
            rec["error"] = f"RiskError: {e}"[:200]
            rec["sec"] = round(time.time() - t0, 1)
            mode = "匿名会话" if pool else "账号级"
            log(f"    [{mode}限流] {str(e)[:70]}")
            log_run(rec)
            log(f"\n[X] 评论接口被限流（{'匿名' if pool else '主号'}），停止。")
            log(f"    断点已保存，稍后重跑即可自动续抓：")
            log(f"    .\\.venv\\Scripts\\python.exe batch_fetch.py --resume"
                f"{' --anon' if pool else ''}")
            return 2

        except Exception as e:  # noqa: BLE001
            fail_n += 1
            fails.append(nid)
            note_try = 0
            rec["status"] = "fail"
            rec["error"] = f"{type(e).__name__}: {e}"[:200]
            log(f"    [FAIL] {type(e).__name__}: {str(e)[:110]}")
            log_run(rec)
            if is_risk(e):
                backoff += 1
                w = min(BACKOFF_BASE * (2 ** (backoff - 1)), MAX_BACKOFF)
                w += random.uniform(0, 3)
                log(f"    [风控] 退避 {w:.0f}s")
                time.sleep(w)
            if len(fails) >= FAIL_LIMIT:
                log(f"[X] 连续失败 {FAIL_LIMIT} 次，停止（保护账号）")
                break

        i += 1
        time.sleep(SLEEP + random.uniform(0, 1.5))

    log(f"\n[完成] 成功 {ok_n} 失败 {fail_n} | 失败: {fails}")
    return 0


def _safe_json(base: Path) -> dict:
    p = base / "content" / "note.json"
    if p.is_file():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


_IMG_EXT = (".jpg", ".jpeg", ".png", ".webp", ".heic", ".avif")


def _collect_images(base: Path) -> int:
    """把 XHS-Downloader 落在 Download/ 的图片改名后归位到 images/。

    工具内部按「时间_作者_标题_N.扩展名」命名，且带中文与空格；这里重命名为
    01.jpg / 02.jpg…，与 urls.json 顺序一致，便于后续按序号引用。
    """
    src = base / "Download"
    dst = base / "images"
    if not src.is_dir():
        return 0
    files = sorted([f for f in src.iterdir()
                    if f.is_file() and f.suffix.lower() in _IMG_EXT])
    for i, f in enumerate(files, 1):
        target = dst / f"{i:02d}{f.suffix.lower()}"
        if not target.exists():
            try:
                f.replace(target)
            except OSError:
                pass
    n = len([f for f in dst.iterdir() if f.suffix.lower() in _IMG_EXT])
    # 清理工具留下的数据库与空目录
    for junk in list(src.glob("*.db")) + list(src.glob("*.md")) + list(src.glob("*.txt")):
        try:
            junk.unlink()
        except OSError:
            pass
    try:
        src.rmdir()
    except OSError:
        pass
    return n


def _write_comments_txt(base: Path, tops, replies, chk) -> None:
    lines = [f"笔记页 {chk['note_reported']} | 一级 {chk['top_level']} + "
             f"楼中楼 {chk['replies']} = {chk['total']} | "
             f"{'已对齐' if chk['matched'] else '差 %d' % chk['diff']}", ""]
    for c in tops:
        ui = c.get("user_info") or {}
        lines.append("- [%s] %s | %s | 赞%s" % (
            (ui.get("nickname") or "?"), c.get("ip_location") or "?",
            (c.get("content") or "").replace("\n", " ").strip()[:60],
            c.get("like_count", "0")))
        for s in (c.get("sub_comments") or []):
            sui = s.get("user_info") or {}
            lines.append("    └ [%s] %s" % (
                (sui.get("nickname") or "?"),
                (s.get("content") or "").replace("\n", " ").strip()[:52]))
    (base / "comments" / "comments.txt").write_text(
        "\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())

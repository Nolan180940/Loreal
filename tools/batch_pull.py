# -*- coding: utf-8 -*-
"""批量拉取 brand_posts.json 里的笔记，落盘 ``data/<note_id>/``。

用 xhs-cli 现有链路（``core.parse_link`` + ``cli.write_post_dir``），
不复制任何采集逻辑 —— 这里只负责：读清单、控节奏、重试、出报告。

风控应对
--------
1. **控节奏**：每篇之间 sleep（默认 3s），不连续轰炸。
2. **多轮重试**：失败的不当场死磕，留到下一轮（风控多是瞬时的）。
3. **UA 轮换**：``parse_link`` 内部已实现 —— 短链被跳登录/验证码时自动换
   下一个 UA 再试。

用法::

    python tools/batch_pull.py                # 看计划
    python tools/batch_pull.py --apply        # 真拉
    python tools/batch_pull.py --apply --only 6ab8e804
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "xhs-cli" / "src"))

from xhs_cli.cli import write_post_dir          # noqa: E402
from xhs_cli.core import FetchError, parse_link  # noqa: E402
from xhs_cli.core.link import UnsupportedLink    # noqa: E402

SRC = ROOT / "legacy-data" / "search" / "brand_posts.json"
OUT_ROOT = ROOT / "data"
REPORT = ROOT / "docs" / "BATCH_PULL.md"
HEX24 = re.compile(r"^[0-9a-f]{24}$")

#: 轮数。第 1 轮全量；后面几轮只补失败的。
ROUNDS = 3


def load_targets(only: str | None = None) -> list[dict]:
    arr = json.loads(SRC.read_text(encoding="utf-8"))
    seen: set[str] = set()
    out: list[dict] = []
    for x in arr:
        nid = str(x.get("note_id") or "")
        if not HEX24.match(nid):
            continue                     # 搜索结果空壳（note_id 带 #）
        if nid in seen:
            continue
        if only and not nid.startswith(only):
            continue
        seen.add(nid)
        out.append({"note_id": nid, "query": x.get("query") or "",
                    "url": x.get("url") or "", "title": x.get("title") or ""})
    return out


def make_payload(result: dict) -> dict:
    """与 ``cmd_parse`` 构造的 payload 完全一致（字段名只有一套）。"""
    return {
        "note": result["note"],
        "images": result["images"],
        "comments": result["comments"],
        "declared": result["declared"],
        "got": result["got"],
        "complete": result["complete"],
        "note_id": result["note_id"],
        "elapsed_ms": result["elapsed_ms"],
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="真拉（默认只看计划）")
    ap.add_argument("--only", metavar="PREFIX", help="只处理某个 note_id 前缀")
    ap.add_argument("--sleep", type=float, default=3.0, help="篇间间隔（秒）")
    ap.add_argument("--no-images", action="store_true", help="不下载图片")
    args = ap.parse_args()

    targets = load_targets(args.only)
    print(f"目标 {len(targets)} 篇 | 输出 {OUT_ROOT} | 间隔 {args.sleep}s")
    if not args.apply:
        by_q: dict[str, int] = {}
        for t in targets:
            by_q[t["query"]] = by_q.get(t["query"], 0) + 1
        for q, n in by_q.items():
            print(f"  {q:<16} {n} 篇")
        print("\n加 --apply 才真拉。")
        return 0

    R: list[str] = []
    w = R.append
    w("# 批量拉取报告")
    w("")
    w(f"目标 {len(targets)} 篇 · 间隔 {args.sleep}s · 最多 {ROUNDS} 轮")
    w("")

    done: set[str] = set()
    results: dict[str, dict] = {}
    t_all = time.monotonic()

    for rnd in range(1, ROUNDS + 1):
        todo = [t for t in targets if t["note_id"] not in done]
        if not todo:
            break
        print(f"\n=== 第 {rnd} 轮：{len(todo)} 篇 ===")
        for i, t in enumerate(todo, 1):
            nid = t["note_id"]
            t0 = time.monotonic()
            try:
                result = parse_link(t["url"])
                info = write_post_dir(result, OUT_ROOT, make_payload(result))
                done.add(nid)
                results[nid] = {
                    "ok": True, "title": result["note"].get("title") or "",
                    "images": info["images"], "urls": info["urls"],
                    "got": result["got"], "declared": result["declared"],
                    "ua": result["ua"], "attempts": result["attempts"],
                }
                print(f"[{i}/{len(todo)}] {nid[:8]} OK | "
                      f"图 {info['images']}/{info['urls']} | "
                      f"评论 {result['got']}/{result['declared']} | "
                      f"{time.monotonic() - t0:.1f}s")
            except UnsupportedLink as exc:
                results[nid] = {"ok": False, "kind": "unsupported",
                                "error": str(exc)}
                print(f"[{i}/{len(todo)}] {nid[:8]} 链接不支持: {exc}")
            except FetchError as exc:
                results[nid] = {"ok": False, "kind": exc.kind,
                                "error": str(exc)}
                print(f"[{i}/{len(todo)}] {nid[:8]} FAIL({exc.kind}) {exc}")
            except Exception as exc:  # noqa: BLE001
                results[nid] = {"ok": False, "kind": type(exc).__name__,
                                "error": str(exc)}
                print(f"[{i}/{len(todo)}] {nid[:8]} FAIL "
                      f"{type(exc).__name__}: {exc}")

            if i < len(todo):
                time.sleep(args.sleep)

        failed = [t for t in targets if t["note_id"] not in done]
        if failed:
            wait = 8.0 * rnd
            print(f"第 {rnd} 轮后剩 {len(failed)} 篇失败，等 {wait:.0f}s 再试")
            time.sleep(wait)

    ok = [t for t in targets if t["note_id"] in done]
    bad = [t for t in targets if t["note_id"] not in done]

    w("## 结果")
    w("")
    w(f"- 成功 **{len(ok)}/{len(targets)}**")
    w(f"- 失败 **{len(bad)}**")
    w(f"- 总耗时 **{time.monotonic() - t_all:.0f}s**")
    w("")
    if bad:
        w("### 失败清单")
        w("")
        w("| 帖 | query | 标题 | kind | 错误 |")
        w("|---|---|---|---|---|")
        for t in bad:
            r = results.get(t["note_id"], {})
            w(f"| `{t['note_id'][:8]}` | {t['query']} | {t['title'][:18]} | "
              f"{r.get('kind', '?')} | {str(r.get('error', ''))[:60]} |")
        w("")
    w("### 成功清单")
    w("")
    w("| 帖 | query | 标题 | 图 | 评论 | UA | 尝试 |")
    w("|---|---|---|---:|---|---|---:|")
    for t in sorted(ok, key=lambda x: x["query"]):
        r = results[t["note_id"]]
        ua = r.get("ua", "")
        ios = ua.split("OS ")[1].split(" like")[0] if "OS " in ua else "?"
        w(f"| `{t['note_id'][:8]}` | {t['query']} | {r['title'][:16]} | "
          f"{r['images']}/{r['urls']} | {r['got']}/{r['declared']} | "
          f"iOS {ios} | {r['attempts']} |")
    w("")

    REPORT.write_text("\n".join(R) + "\n", encoding="utf-8")
    print(f"\n成功 {len(ok)}/{len(targets)} | 失败 {len(bad)}")
    print(f"报告: {REPORT}")
    return 0 if not bad else 1


if __name__ == "__main__":
    raise SystemExit(main())

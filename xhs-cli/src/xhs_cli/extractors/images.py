"""图片 URL 提取与校验。"""

from __future__ import annotations

from typing import Any


def image_urls(page_images: list[dict]) -> list[str]:
    """按页面原顺序返回图片 URL（保持与原帖一致的序号）。"""
    return [it["url"] for it in page_images if it.get("url")]


def summarize(results: list[dict[str, Any]], declared: int) -> dict[str, Any]:
    """汇总下载结果。

    ``declared`` 是页面声明的图片数；``downloaded`` 是真正落盘的数量，
    两者不等说明 CDN 有失败，审计时必须暴露出来。
    """
    ok = sum(1 for r in results if r.get("status") in ("ok", "skipped"))
    failed = [
        {"file": r.get("file"), "status": r.get("status")}
        for r in results
        if r.get("status") not in ("ok", "skipped")
    ]
    total_bytes = sum(int(r.get("bytes") or 0) for r in results)
    return {
        "declared": declared,
        "downloaded": ok,
        "failed": failed,
        "bytes": total_bytes,
        "complete": declared == 0 or ok == declared,
    }
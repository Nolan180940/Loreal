# -*- coding: utf-8 -*-
"""本地接收服务：浏览器抓到的数据 POST 到这里，落盘成标准目录结构。

用法：
    python recv_server.py <out_root> [port]

浏览器侧用 fetch('http://127.0.0.1:8765/save', {method:'POST', body: JSON}) 推送。

**双 schema 落盘**：现有 32 篇是 Spider_XHS 的中文 schema（``作品标题``/``点赞数量``…），
本服务写出的数据若只用英文 key 会让下游读取不一致。因此每份 note.json 同时写
中文 key（与历史数据对齐）和英文 key（xhs-cli 约定），``gaps.py`` 两者都能读。
"""

from __future__ import annotations

import json
import sys
import time
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

OUT_ROOT = Path(sys.argv[1] if len(sys.argv) > 1 else r"D:\LOreal-ai\data")
PORT = int(sys.argv[2] if len(sys.argv) > 2 else 8765)

IMAGE_EXTS = (".jpg", ".jpeg", ".png", ".webp", ".heic", ".avif")
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")

# 英文 key -> 中文 key（与Spider_XHS 历史产物对齐）
# 不含note_id / tags / image_count / images / source：这几个在下面单独处理
ZH = {
    "title": "作品标题",
    "desc": "作品描述",
    "author": "作者昵称",
    "author_id": "作者ID",
    "author_link": "作者链接",
    "link": "作品链接",
    "type": "作品类型",
    "published": "发布时间",
    "updated": "最后更新时间",
    "time_ms": "时间戳",
    "ip_location": "IP属地",
    "liked": "点赞数量",
    "collected": "收藏数量",
    "comment_count": "评论数量",
    "share_count": "分享数量",
}


def _dump(p: Path, obj) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")


def _ts(ms) -> str:
    try:
        return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(int(ms) / 1000))
    except (TypeError, ValueError):
        return ""


def build_note(note_id: str, p: dict, images: list, source: str) -> dict:
    """构造双 schema 的 note dict。"""
    published = _ts(p.get("time_ms"))
    tags = p.get("tags") or []
    en = {
        "note_id": note_id,
        "title": p.get("title", ""),
        "desc": p.get("desc", ""),
        "tags": tags,
        "author": p.get("author", ""),
        "author_id": p.get("author_id", ""),
        "author_link": p.get("author_link", ""),
        "link": p.get("link", ""),
        "type": p.get("type", "图文"),
        "published": published,
        "updated": published,
        "time_ms": p.get("time_ms"),
        "ip_location": p.get("ip_location", ""),
        "liked": p.get("liked", ""),
        "collected": p.get("collected", ""),
        "comment_count": p.get("comment_count", ""),
        "share_count": p.get("share_count", ""),
        "image_count": len(images),
        "images": images,
        "source": source,
    }
    out = dict(en)
    for k, zh in ZH.items():
        out[zh] = en[k]
    # 历史数据里 作品标签 是空格分隔的字符串，不是数组
    out["作品标签"] = " ".join(t for t in tags if t)
    out["作品ID"] = note_id
    # 动图/封面：历史数据有这三个 key，缺失会让下游 KeyError
    out["下载地址"] = [i.get("url") for i in images]
    out["动图地址"] = [None] * len(images)
    out["封面地址"] = (images[0].get("url") if images else None)
    return out


def write_md(root: Path, note: dict) -> None:
    md = [
        f"# {note.get('作品标题', '')}",
        "",
        f"作者：{note.get('作者昵称', '')}",
        f"发布：{note.get('发布时间', '')}",
        f"互动：赞{note.get('点赞数量', '')} 藏{note.get('收藏数量', '')} "
        f"评{note.get('评论数量', '')} 享{note.get('分享数量', '')}",
        "",
        "## 正文",
        str(note.get("作品描述", "")),
        "",
        "## 标签",
        str(note.get("作品标签", "")),
        "",
    ]
    (root / "content" / "note.md").write_text("\n".join(md), encoding="utf-8")


def download_images(root: Path, images: list, timeout: int = 20) -> int:
    """下载图片；已存在且非空则跳过。返回成功张数。"""
    d = root / "images"
    d.mkdir(parents=True, exist_ok=True)
    ok = 0
    for i, item in enumerate(images, 1):
        url = item.get("url") if isinstance(item, dict) else item
        if not url:
            continue
        dest = d / f"{i:02d}.jpeg"
        if dest.is_file() and dest.stat().st_size > 0:
            ok += 1
            continue
        try:
            req = urllib.request.Request(url, headers={
                "User-Agent": UA,
                "Referer": "https://www.xiaohongshu.com/",
            })
            with urllib.request.urlopen(req, timeout=timeout) as r:
                data = r.read()
            if not data:
                print(f"  [img-empty] {i:02d}", flush=True)
                continue
            dest.write_bytes(data)
            ok += 1
        except Exception as exc:  # noqa: BLE001
            print(f"  [img-fail] {i:02d} {type(exc).__name__}", flush=True)
    return ok


def save_note(note_id: str, payload: dict) -> dict:
    root = OUT_ROOT / note_id
    for sub in ("content", "images", "comments"):
        (root / sub).mkdir(parents=True, exist_ok=True)

    raw = payload.get("note") or {}
    images = payload.get("images") or []
    comments = payload.get("comments") or []
    source = payload.get("source") or "browser_dom"
    pages = payload.get("pages") or 1

    note = build_note(note_id, raw, images, source)
    _dump(root / "content" / "note.json", note)
    write_md(root, note)
    _dump(root / "images" / "urls.json", [i.get("url") for i in images])
    got_imgs = download_images(root, images)

    top = [c for c in comments if not c.get("_is_reply")]
    reps = [c for c in comments if c.get("_is_reply")]
    try:
        expect = int(str(note.get("评论数量") or 0) or 0)
    except ValueError:
        expect = 0
    total = len(top) + len(reps)

    _dump(root / "comments" / "comments.json",
          [dict(c, _is_reply=False) for c in top]
          + [dict(c, _is_reply=True) for c in reps])
    _dump(root / "comments" / "card.json", {
        "note_id": note_id,
        "top_level": len(top),
        "replies": len(reps),
        "total": total,
        "note_reported": expect,
        "note_reported_known": expect > 0,
        "matched": (total == expect) if expect > 0 else None,
        "diff": (expect - total) if expect > 0 else 0,
        "partial": expect > 0 and total < expect,
        "pages_fetched": pages,
        "images_downloaded": got_imgs,
        "source": source,
    })
    return {"note_id": note_id, "images": got_imgs, "comments": total,
            "expect": expect}


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args) -> None:
        pass

    def _send(self, code: int, body: bytes, ctype: str = "application/json") -> None:
        self.send_response(code)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Type", ctype)
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802
        """提供 browser_inject.js，供浏览器 addInitScript 拉取。"""
        if self.path.rstrip("/") in ("/inject", "/browser_inject.js"):
            js = Path(__file__).with_name("browser_inject.js")
            try:
                self._send(200, js.read_text(encoding="utf-8"),
                           "application/javascript; charset=utf-8")
            except OSError as exc:
                self._send(404, f"no inject script: {exc}".encode())
            return
        self._send(404, b"not found")

    def do_POST(self) -> None:  # noqa: N802
        try:
            n = int(self.headers.get("Content-Length") or 0)
            data = json.loads(self.rfile.read(n).decode("utf-8"))
        except Exception as exc:  # noqa: BLE001
            self._send(400, f"bad body: {exc}".encode())
            return

        note_id = str(data.get("note_id") or "")
        if len(note_id) != 24:
            self._send(400, b"bad note_id")
            return

        try:
            r = save_note(note_id, data)
        except Exception as exc:  # noqa: BLE001
            import traceback
            traceback.print_exc()
            self._send(500, f"save error: {exc}".encode())
            return

        print(f"[SAVED] {note_id} imgs={r['images']} "
              f"cmts={r['comments']}/{r['expect']}", flush=True)
        self._send(200, json.dumps(r).encode())

    def do_OPTIONS(self) -> None:  # noqa: N802
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "*")
        self.end_headers()


if __name__ == "__main__":
    OUT_ROOT.mkdir(parents=True, exist_ok=True)
    print(f"[recv] http://127.0.0.1:{PORT}/save -> {OUT_ROOT}", flush=True)
    ThreadingHTTPServer(("127.0.0.1", PORT), Handler).serve_forever()
# -*- coding: utf-8 -*-
"""真实评论抓取（Spider_XHS 签名实现）+ 落盘。

必须用 tools\\.venv 的解释器运行（需要 curl_cffi / PyExecJS / node）。
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent.parent))

OUT_DIR = Path(r"D:\LOreal-ai\data\xhs")
NOTE_ID = "6a4cc2cd000000001101daf1"
XSEC_TOKEN = "CBzj7RPSlGq4mj5dZrkKRC4dHUhMRsg277nNCC2DPFur0="


def main() -> int:
    from forensic.xhs_comments import get_cookie
    from xhs_utils.xhs_pc import XHSPcAuth
    from apis.xhs_pc_apis import XHS_Apis

    cookie = get_cookie()
    if not cookie:
        print("no cookie")
        return 2

    auth = XHSPcAuth.from_cookie(cookie)
    apis = XHS_Apis(auth)
    apis.bootstrap()
    ok, msg, comments = apis.get_note_all_out_comment(NOTE_ID, XSEC_TOKEN)
    comments = comments or []

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "comments_raw.json").write_text(
        json.dumps(comments, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [f"ok={ok} n={len(comments)}", ""]
    for c in comments:
        ui = c.get("user_info") or {}
        content = (c.get("content") or "").replace("\n", " ").strip()
        lines.append(
            f"- {ui.get('nickname', '?')} | {c.get('ip_location', '?')} | "
            f"like={c.get('like_count', '0')} | "
            f"sub={c.get('sub_comment_count', '0')} | {content[:58]}")
    (OUT_DIR / "comments_preview.txt").write_text(
        "\n".join(lines), encoding="utf-8")
    print(f"fetched={len(comments)} saved={OUT_DIR / 'comments_raw.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

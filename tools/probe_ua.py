# -*- coding: utf-8 -*-
"""实测各 UA 当前是否可用 —— 决定要不要做轮换。只读（各发一次 GET）。"""
from __future__ import annotations

import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "xhs-cli" / "src"))

from xhs_cli.core.fetch import MOBILE_UAS, _headers  # noqa: E402

# 拿一条短链和一条长链各测一次
LINK = sys.argv[1] if len(sys.argv) > 1 else "https://xhslink.cn/o/7KJDrvRh4Pa"

lines: list[str] = []
w = lines.append
w(f"探测链接: {LINK}")
w("")

for i, ua in enumerate(MOBILE_UAS):
    tag = f"UA[{i}] iOS {ua.split('OS ')[1].split(' like')[0]}"
    try:
        req = urllib.request.Request(LINK, headers=_headers(ua))
        with urllib.request.urlopen(req, timeout=15) as resp:
            final = resp.url
            status = resp.status
    except urllib.error.HTTPError as exc:
        w(f"{tag}: HTTPError {exc.code}")
        w("")
        continue
    except Exception as exc:  # noqa: BLE001
        w(f"{tag}: {type(exc).__name__}: {exc}")
        w("")
        continue

    has_tok = "xsec_token=" in final
    is_login = "/login" in final
    is_captcha = "/captcha" in final or "verifyBiz=" in final
    verdict = ("OK" if (has_tok and not is_login and not is_captcha)
               else "被风控（" + ("验证码页" if is_captcha else
                                 "登录页" if is_login else "无 token") + "）")
    w(f"{tag}: status={status} -> {verdict}")
    w(f"    final: {final[:130]}")
    w("")

out = ROOT / "docs" / "UA_PROBE.md"
out.write_text("\n".join(lines) + "\n", encoding="utf-8")
print("\n".join(lines))

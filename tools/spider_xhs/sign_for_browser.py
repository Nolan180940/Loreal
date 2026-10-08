# -*- coding: utf-8 -*-
"""为「集成浏览器会话」生成签名头（a1 替换法）。

思路
----
浏览器 cookie 里只有 a1 等非 HttpOnly 项能读（web_session 是 HttpOnly）。

但我们**不需要** web_session 来算签名 —— 签名只需要 a1 + 路径 + 时间戳。
请求由浏览器发出，它会自动带上自己的全部 cookie（含 web_session）。

所以：
  1. Python 先建一个合法会话（拿到 profile 所需的 gid/loadts 等结构）
  2. 把 a1 / webId 替换成浏览器的真实值
  3. 用替换后的 profile 算签名
  4. 浏览器带此签名 + 自己的 cookie 发请求 -> 三者对齐

用法
----
    python sign_for_browser.py <cookie_json_file> <api_path>
cookie_json_file 里是 {"a1": "...", "webId": "...", ...}
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent))

from apis.xhs_pc_login_apis import XHSLoginApi  # noqa: E402
from xhs_utils.xhs_pc import XHSPcAuth  # noqa: E402
from xhs_utils.xhs_pc.params import generate_xs_xs_common  # noqa: E402

ck_file = Path(sys.argv[1])
browser_ck = json.loads(ck_file.read_text(encoding="utf-8"))
api = sys.argv[2]

# 1. 建合法会话
base = XHSLoginApi().generate_init_cookies()
# 2. 用浏览器的关键 cookie 覆盖
for k in ("a1", "webId", "gid", "loadts", "ets", "websectiga",
          "sec_poison_id", "xsecappid", "webBuild"):
    if browser_ck.get(k):
        base[k] = browser_ck[k]

cstr = "; ".join(f"{k}={v}" for k, v in base.items())
auth = XHSPcAuth.from_cookie(cstr)
print(f"a1 已替换为浏览器值: {base['a1'][:20]}...", file=sys.stderr)

out = {}
# 3. 为每个接口算签名
for target in (api, api.replace("/v2/", "/v1/")):
    sc = auth.next_sign_context(target)
    now = sc["now"]
    xs, xt, xsc = generate_xs_xs_common(
        base["a1"], target, data="", method="GET",
        b1=auth.current_b1(now),
        dsl_pair=auth.dsl_pair,
        cookie=cstr,
        sign_context=sc,
    )
    out[target] = {"x-s": xs, "x-t": str(xt), "x-s-common": xsc,
                   "tier": sc.get("tier")}

p = HERE / "_sig.json"
p.write_text(json.dumps({"a1": base["a1"], "sigs": out},
                        ensure_ascii=False), encoding="utf-8")
print(json.dumps({k: {"tier": v["tier"], "x-s": v["x-s"][:50] + "..."}
                  for k, v in out.items()}, ensure_ascii=False, indent=2))
print(f"[written] {p}")
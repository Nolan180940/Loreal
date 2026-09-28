# -*- coding: utf-8 -*-
"""从本机浏览器读取小红书 Cookie（含 HttpOnly 的 web_session），写入 .env。

为什么需要这个
--------------
`web_session` 是 HttpOnly cookie。浏览器**故意禁止 JavaScript 读取**它
（防 XSS 的设计），所以 Console 脚本和 `document.cookie` 都拿不到。
可行路线只有两条：
  1. 从浏览器的加密 Cookie 库直读（**Windows 需管理员权限**）
  2. 手动从 F12 → Application → Cookies 里复制 Value

本脚本走路线 1，复用 XHS-Downloader 内置的 BrowserCookie（底层是 rookiepy）。

用法（建议以管理员身份运行 PowerShell）：
    .\\.venv\\Scripts\\python.exe read_my_cookie.py
    .\\.venv\\Scripts\\python.exe read_my_cookie.py --browser Edge
    .\\.venv\\Scripts\\python.exe read_my_cookie.py --print-only
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
ENV_FILE = ROOT / ".env"

DOMAINS = [".xiaohongshu.com", "xiaohongshu.com", ".xhslink.com"]


def save_env(cookie: str) -> None:
    line = f"XHS_COOKIE={cookie}"
    if ENV_FILE.is_file():
        lines = ENV_FILE.read_text(encoding="utf-8").splitlines()
        hit = False
        for i, ln in enumerate(lines):
            if ln.startswith("XHS_COOKIE="):
                lines[i] = line
                hit = True
        if not hit:
            lines.append(line)
        ENV_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")
    else:
        ENV_FILE.write_text(
            "# 本地私密配置（已被 .gitignore 排除）\n" + line + "\n",
            encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--browser", default="", help="浏览器名，如 Chrome / Edge")
    ap.add_argument("--print-only", action="store_true", help="只打印，不写 .env")
    args = ap.parse_args()

    try:
        from source.expansion.browser import BrowserCookie
    except Exception as e:  # noqa: BLE001
        print(f"无法导入 BrowserCookie：{type(e).__name__}: {e}")
        print("请确认在 tools 目录、且用的是 tools\\.venv 的解释器。")
        return 2

    names = list(BrowserCookie.SUPPORT_BROWSER.keys())
    order = ([args.browser] if args.browser else []) + [
        n for n in names if not args.browser or n.lower() != args.browser.lower()
    ]

    for name in order:
        print(f"--- 尝试读取 {name} ---")
        try:
            ck = BrowserCookie.get(name, DOMAINS)
        except Exception as e:  # noqa: BLE001
            print(f"  失败：{type(e).__name__}: {e}")
            continue
        ck = (ck or "").strip()
        has_a1 = "a1=" in ck
        has_ws = "web_session=" in ck
        print(f"  {len(ck)} 字符 | a1: {has_a1} | web_session: {has_ws}")
        if not ck:
            continue
        if has_ws:
            print("\n=== 完整 Cookie（已含 web_session）===")
            print(ck)
            if not args.print_only:
                save_env(ck)
                print(f"\n[已写入] {ENV_FILE}")
            return 0
        if has_a1 and not args.print_only:
            save_env(ck)
            print(f"[已写入 a1 部分 cookie] {ENV_FILE}")

    print("\n=== 未读到 web_session ===")
    print("原因通常是：浏览器未登录小红书，或终端不是管理员权限。")
    print("手动方案：F12 -> Application -> Storage -> Cookies ->")
    print("  https://www.xiaohongshu.com -> 找 web_session -> 复制 Value")
    print("然后把 .env 中 XHS_COOKIE= 后面补成完整 cookie 串。")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

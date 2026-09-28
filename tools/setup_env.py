# -*- coding: utf-8 -*-
"""重建 tools 环境（首次使用必跑）。

背景：`tools/.venv` 不入库（146MB，且可由 requirements 重建）。
本脚本负责在干净克隆后一键重建出可用的运行环境。

用法（项目根目录执行）：
    python tools/setup_env.py

它会做四件事：
1. 建 tools/.venv（若不存在）
2. 装 XHS-Downloader 依赖（curl-cffi 等）
3. 装评论抓取所需的额外依赖（PyExecJS / loguru）
4. 自检：Node.js、关键包、签名模块是否就绪
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
VENV = HERE / ".venv"
PY = VENV / "Scripts" / "python.exe"

XHS_DEPS = [
    "curl-cffi>=0.16.0",
    "click>=8.4.2",
    "aiofiles>=25.1.0",
    "aiosqlite>=0.22.1",
    "emoji>=2.15.0",
    "lxml>=6.1.2",
    "pyyaml>=6.0.3",
    "rich>=13.0.0",
    "fastapi>=0.141.1",
    "uvicorn>=0.52.4",
    "textual>=8.2.8",
    "pyperclip>=1.11.0",
    "pywebview>=6.2.1",
    "websockets>=17.0.1",
    "fastmcp>=3.4.7",
]

EXTRA_DEPS = [
    "PyExecJS>=1.5.1",   # Spider_XHS 签名依赖（内部走 node）
    "loguru>=0.7.0",      # Spider_XHS 日志
    "xhshow>=0.2.0",      # XHS-Downloader 的签名器（官方 pyproject 未声明）
]


def run(cmd: list[str], **kw) -> subprocess.CompletedProcess:
    print("$", " ".join(cmd))
    return subprocess.run(cmd, **kw)


def main() -> int:
    # 1) Node.js 自检（PyExecJS 依赖）
    if not shutil.which("node"):
        print("[X] 未找到 node。PyExecJS 需要 Node.js 才能执行签名脚本。")
        print("    请安装 Node.js 18+：https://nodejs.org/")
        return 2
    ver = run(["node", "--version"], capture_output=True, text=True)
    print("[OK] Node.js", ver.stdout.strip())

    # 2) 建 venv
    if not PY.is_file():
        print("[..] 创建虚拟环境 tools/.venv")
        run([sys.executable, "-m", "venv", str(VENV)], check=True)
    else:
        print("[OK] 虚拟环境已存在")

    # 3) 装依赖
    print("[..] 安装依赖（首次较慢）")
    run([str(PY), "-m", "pip", "install", "--upgrade", "pip", "-q"], check=True)
    run([str(PY), "-m", "pip", "install", *XHS_DEPS], check=True)
    run([str(PY), "-m", "pip", "install", *EXTRA_DEPS], check=True)

    # 4) 自检
    print("[..] 自检")
    code = (
        "import curl_cffi, xhshow, loguru; "
        "import sys; sys.path.insert(0, r'%s'); "
        "from xhs_utils.xhs_pc import XHSPcAuth; "
        "from apis.xhs_pc_apis import XHS_Apis; "
        "print('deps OK')" % (HERE / "spider_xhs")
    )
    r = run([str(PY), "-c", code], capture_output=True, text=True,
            cwd=str(HERE / "spider_xhs"))
    if r.returncode != 0:
        print("[X] 自检失败：")
        print(r.stdout)
        print(r.stderr[-1500:])
        return 1
    print("[OK]", r.stdout.strip())

    # 5) cookie 检查
    env = HERE.parent / ".env"
    has_env = env.is_file() and "XHS_COOKIE=" in env.read_text(
        encoding="utf-8", errors="replace")
    print(f"[{'OK' if has_env else '!!'}] cookie: "
          f"{'已配置 .env' if has_env else '未配置，请复制 .env.example 为 .env 并填入'}")

    print("")
    print("环境就绪。使用：")
    print(f'  cd {HERE / "spider_xhs"}')
    print(f'  {PY} xhs_cli.py "https://xhslink.cn/o/xxxx"')
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

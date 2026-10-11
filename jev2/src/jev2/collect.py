"""进料：分享链接 → ``data/<note_id>/``。

这是**产品入口的第一步**。完整链路::

    链接  →  collect.py  →  data/<note_id>/{图片, notes.json}
                             ↓
                          loader.py  →  signals + semantic  →  fuse
                             ↓
                          out/<note_id>/{scores.json, report.md}

为什么用 subprocess 而不是 import
---------------------------------
采集和判定是两种**不同的失败模式**：

- 采集会挂：短链过期、反爬、验证码、网络抖动
- 判定会挂：模型 451、key 失效、数据格式变了

放进同一个进程就得写一套混合的异常处理，而且采集器一旦卡死
（urllib 挂起、验证码风控），判定器也被一起拖住。进程边界把
「采集崩了」变成一个退出码，处置方式立刻明确。

顺带的好处是换采集器成本为零 —— 只要它满足下面的 JSON 契约。

JSON 契约（来自 ``xhs-cli parse --json``）
-----------------------------------------
``stdout``
    纯 JSON（可 json.loads），字段见 :func:`_payload_to_collected`
``stderr``
    进度信息（人读的，可忽略）
退出码
    0 成功 · 2 链接不支持 · 3 抓取失败 · 4 目录写入失败

这个契约是**实测**的：``--json`` 的 stdout 无任何杂质前缀，
所以调用方可以放心地 ``json.loads(stdout)``。
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from .core.errors import CollectError, ConfigError

__all__ = ["Collected", "collect", "collector_available",
           "collector_hint"]

_DEFAULT_TIMEOUT = 180

# 采集器退出码 → 人话。与 xhs-cli/README.md 的约定一一对应。
_EXIT_HINT = {
    2: "链接不被支持（只认小红书短链 / explore 长链 / 缺协议头长链）",
    3: "抓取失败（网络、反爬或短链过期）—— 重试或换一个新分享链接",
    4: "落盘失败（目录不可写？）",
}


def collector_available() -> bool:
    """采集器（``xhs_cli``）在当前解释器里是否可用。"""
    try:
        return importlib.util.find_spec("xhs_cli") is not None
    except (ImportError, ValueError):
        return False


def collector_hint(python: str | None = None) -> str:
    """采集器缺失时给一条能直接跑的命令，而不是一句「请先安装」。"""
    return (f"  cd xhs-cli\n"
            f"  \"{python or sys.executable}\" -m pip install -e . --no-deps")


@dataclass(frozen=True, slots=True)
class Collected:
    """一次采集的结果（落盘之后）。"""

    note_id: str
    dir: Path
    link: str = ""
    title: str = ""
    author: str = ""
    images: int = 0            # 笔记声明的图片数（URL 个数）
    image_files: int = 0       # 实际落盘的图片文件数（--no-images 时为 0）
    image_errors: int = 0
    comments: int = 0          # 实得评论数
    declared: int = 0          # 页面声明的评论数
    comments_complete: bool = False
    elapsed_ms: int = 0

    @property
    def notes_json(self) -> Path:
        return self.dir / "notes.json"

    def to_dict(self) -> dict[str, Any]:
        return {
            "note_id": self.note_id,
            "dir": str(self.dir),
            "link": self.link,
            "title": self.title,
            "author": self.author,
            "images": self.images,
            "image_files": self.image_files,
            "image_errors": self.image_errors,
            "comments": self.comments,
            "declared": self.declared,
            "comments_complete": self.comments_complete,
            "elapsed_ms": self.elapsed_ms,
        }

    def describe(self) -> str:
        """一行摘要（终端用）。"""
        bits = [self.note_id, (self.title or "（无标题）")[:26]]
        if self.images:
            bits.append(f"图 {self.image_files}/{self.images}")
        got = f"评论 {self.comments}"
        if self.declared:
            got += f"/{self.declared}"
        bits.append(got)
        if self.image_errors:
            bits.append(f"图失败 {self.image_errors}")
        return " · ".join(bits)


def collect(link: str, out_dir: Path | str, *,
            images: bool = True,
            timeout: int = _DEFAULT_TIMEOUT,
            python: str | None = None,
            log: Callable[[str], None] | None = None) -> Collected:
    """抓一个链接，落到 ``<out_dir>/<note_id>/``。

    Parameters
    ----------
    link
        小红书短链 / 长链 / 缺协议头长链。
    out_dir
        落盘根目录（通常就是 ``data/``）。
    images
        是否下载图片。``False`` 时只落 ``notes.json``（判定不需要图，
        但人工复核需要 —— 所以默认 True）。
    timeout
        整个采集进程的超时（秒）。采集器内部有自己的重试，
        这里是兜底：宁可失败也别挂死。
    python
        跑采集器的解释器，默认当前解释器（同一 venv 里装了 xhs-cli）。

    Raises
    ------
    ConfigError
        采集器不可用。
    CollectError
        链接 / 网络 / 落盘失败，或采集器吐出的东西不合契约。
    """
    if not collector_available():
        raise ConfigError(
            "找不到采集器 xhs_cli（jev2 不负责采集，只负责判定）。\n"
            "装一下：\n" + collector_hint(python))

    cmd = [python or sys.executable, "-m", "xhs_cli"]
    if not images:
        cmd.append("--skip-images")          # 顶层参数，必须在子命令前
    cmd += ["parse", link, "--out", str(out_dir), "--json"]

    if log:
        log("xhs-cli " + " ".join(cmd[3:]))

    try:
        proc = subprocess.run(
            cmd, capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=timeout)
    except subprocess.TimeoutExpired:
        raise CollectError(
            f"采集超时（>{timeout}s）。链接可能需要登录/已被风控：{link}"
        ) from None
    except OSError as exc:
        raise CollectError(f"采集器起不来: {exc}") from None

    if proc.returncode != 0:
        hint = _EXIT_HINT.get(proc.returncode, "")
        tail = [ln for ln in (proc.stderr or "").strip().splitlines()
                if ln.strip()][-3:]
        msg = f"采集失败（退出码 {proc.returncode}）"
        if hint:
            msg += f"\n  {hint}"
        for ln in tail:
            msg += f"\n  {ln}"
        # 带上退出码：调用方要能区分「链接不对」和「抓取失败」
        raise CollectError(msg, code=proc.returncode)

    return _parse_stdout(proc.stdout, Path(out_dir), link, log=log)


def _parse_stdout(stdout: str, out_dir: Path, link: str, *,
                  log: Callable[[str], None] | None = None) -> Collected:
    """把采集器的 ``--json`` 输出变成 :class:`Collected`。

    单独拆出来是为了能脱离 subprocess 测：契约好不好的唯一标准
    是「一段 stdout 能不能正确变成对象」。
    """
    s = (stdout or "").strip()
    if not s:
        raise CollectError("采集器没有输出（stdout 为空）")

    try:
        d = json.loads(s)
    except json.JSONDecodeError as exc:
        # 能走到这里说明 stdout 里混进了非 JSON 的东西（进度信息之类）。
        # 报「不是纯 JSON」而不是只抛 JSONDecodeError —— 前者直接指向
        # 契约被破坏，后者会让人去查数据而不是查输出流。
        raise CollectError(
            "采集器 stdout 不是纯 JSON（--json 契约被破坏）\n"
            f"  前 80 字符: {s[:80]!r}\n"
            f"  解析失败: {exc}") from None

    if not isinstance(d, dict):
        # 合法 JSON 但结构不对 —— 和「不是 JSON」是两回事，
        # 排查方向完全不同（看采集器版本 vs 看输出流）。
        raise CollectError(
            f"采集器输出顶层是 {type(d).__name__}，应为对象"
            "（--json 的契约是单个 object）")

    nid = str(d.get("note_id") or "").strip()
    if not nid:
        raise CollectError("采集器没有返回 note_id，无法定位数据目录")

    note = d.get("note") or {}
    if not isinstance(note, dict):
        note = {}
    comments = d.get("comments") or []
    files = d.get("image_files") or []
    errors = d.get("image_errors") or []

    got = Collected(
        note_id=nid,
        dir=out_dir / nid,
        link=link,
        title=str(note.get("title") or ""),
        author=str(note.get("author") or note.get("nickname") or ""),
        images=len(d.get("images") or []),
        image_files=len(files) if isinstance(files, list) else 0,
        image_errors=len(errors) if isinstance(errors, list) else 0,
        comments=len(comments) if isinstance(comments, list) else 0,
        declared=_int(d.get("declared")),
        comments_complete=bool(d.get("complete")),
        elapsed_ms=_int(d.get("elapsed_ms")),
    )

    if not got.notes_json.is_file():
        # 采集器报成功但文件不在 —— 比「抓取失败」更糟，因为
        # 调用方会以为可以继续。必须在这里拦住。
        raise CollectError(
            f"采集器报成功，但 {got.notes_json} 不存在。\n"
            "  可能是 --out 没生效（检查采集器版本）")

    if log:
        log(f"落盘 {got.dir}")
    return got


def _int(v: Any) -> int:
    try:
        return int(v)
    except (TypeError, ValueError):
        return 0

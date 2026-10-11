"""进料层测试：链接 → ``data/<note_id>/``。

为什么这一层要单独测
--------------------
采集是链路上**唯一跨进程**的一步，也是出错方式最多的一步：

- 链接不支持（短链过期、不是小红书链接）
- 网络 / 反爬 / 验证码
- 采集器压根没装
- 采集器版本对不上（报成功但没落盘）

这些如果都变成一句「抓取失败」，产品入口就没法用 —— 用户不知道该
换链接、重试、还是去装东西。所以每个失败路径都要有自己的报错。

另外钉住两件容易悄悄坏掉的事：

1. **``--skip-images`` 必须在子命令之前** —— 它是顶层参数，
   放到 ``parse`` 后面会变成 ``unrecognized arguments`` 直接失败
   （实测踩过）。
2. **采集器报成功 ≠ 文件存在** —— 必须在进料层拦住，
   否则会带着一个不存在的路径继续往下跑。
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

_HERE = Path(__file__).resolve()
for _p in (_HERE.parents[1] / "src", _HERE.parents[2] / "jev2" / "src"):
    if _p.is_dir() and str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from jev2.collect import (Collected, collect, collector_available,   # noqa: E402
                          _parse_stdout)
from jev2.core.errors import CollectError, ConfigError              # noqa: E402

NID = "69d8c8a6000000002301d991"
LINK = "https://xhslink.cn/o/3O20COBNbS1"


# ------------------------------------------------------------------ 造数据

def _payload(**over):
    d = {
        "note_id": NID,
        "note": {"title": "上海微调升级美貌", "author": "张玲｜Yestar"},
        "images": ["u1", "u2", "u3", "u4", "u5"],
        "image_files": ["01.jpg", "02.jpg", "03.jpg", "04.jpg", "05.jpg"],
        "image_errors": [],
        "comments": [{"content": "a"}, {"content": "b"}],
        "declared": 100,
        "got": 2,
        "complete": False,
        "elapsed_ms": 1234,
    }
    d.update(over)
    return d


def _stdout(tmp_path: Path, *, write_json: bool = True,
            **over) -> str:
    d = _payload(**over)
    root = tmp_path / str(d.get("note_id") or "x")
    root.mkdir(parents=True, exist_ok=True)
    if write_json:
        (root / "notes.json").write_text("{}", encoding="utf-8")
    return json.dumps(d, ensure_ascii=False)


def _fake_run(returncode: int = 0, stdout: str = "", stderr: str = ""):
    """替换 ``subprocess.run``，顺便记下真实构造出来的 argv。"""
    calls: list[list[str]] = []

    def run(cmd, **kw):
        calls.append(list(cmd))
        return subprocess.CompletedProcess(cmd, returncode, stdout, stderr)

    run.calls = calls          # type: ignore[attr-defined]
    return run


# --------------------------------------------------------------- 契约解析

def test_parse_stdout_ok(tmp_path: Path) -> None:
    c = _parse_stdout(_stdout(tmp_path), tmp_path, LINK)
    assert isinstance(c, Collected)
    assert c.note_id == NID
    assert c.title == "上海微调升级美貌"
    assert c.author == "张玲｜Yestar"
    assert c.images == 5
    assert c.image_files == 5
    assert c.comments == 2
    assert c.declared == 100
    assert c.comments_complete is False
    assert c.elapsed_ms == 1234
    assert c.notes_json == tmp_path / NID / "notes.json"


def test_parse_stdout_describe_is_one_line(tmp_path: Path) -> None:
    s = _parse_stdout(_stdout(tmp_path), tmp_path, LINK).describe()
    assert "\n" not in s
    assert NID in s
    assert "图 5/5" in s
    assert "评论 2/100" in s


def test_parse_stdout_without_images(tmp_path: Path) -> None:
    """``--no-images`` 时 image_files 为空，但声明的图片数仍要知道。"""
    c = _parse_stdout(_stdout(tmp_path, image_files=[]),
                      tmp_path, LINK)
    assert c.images == 5          # 声明 5 张
    assert c.image_files == 0     # 一张没落
    assert "图 0/5" in c.describe()


def test_parse_stdout_counts_image_errors(tmp_path: Path) -> None:
    c = _parse_stdout(
        _stdout(tmp_path, image_errors=[{"index": 2, "error": "404"}]),
        tmp_path, LINK)
    assert c.image_errors == 1
    assert "图失败 1" in c.describe()


def test_parse_stdout_tolerates_missing_note(tmp_path: Path) -> None:
    """采集器没给 ``note`` 也要能跑 —— 只有 note_id 是硬要求。"""
    c = _parse_stdout(_stdout(tmp_path, note=None), tmp_path, LINK)
    assert c.note_id == NID
    assert c.title == ""
    assert "（无标题）" in c.describe()


def test_parse_stdout_rejects_empty(tmp_path: Path) -> None:
    with pytest.raises(CollectError, match="没有输出"):
        _parse_stdout("   \n ", tmp_path, LINK)


def test_parse_stdout_rejects_non_json(tmp_path: Path) -> None:
    """stdout 被污染 = 契约破坏，要立刻发现而不是等 json.loads 报错。"""
    with pytest.raises(CollectError, match="不是纯 JSON"):
        _parse_stdout("[out] 进度信息混进来了\n{}", tmp_path, LINK)


def test_parse_stdout_rejects_broken_json(tmp_path: Path) -> None:
    with pytest.raises(CollectError, match="解析失败"):
        _parse_stdout('{"note_id": "abc", ', tmp_path, LINK)


def test_parse_stdout_rejects_non_object(tmp_path: Path) -> None:
    with pytest.raises(CollectError, match="应为对象"):
        _parse_stdout('["a", "b"]', tmp_path, LINK)


def test_parse_stdout_rejects_missing_note_id(tmp_path: Path) -> None:
    with pytest.raises(CollectError, match="没有返回 note_id"):
        _parse_stdout(json.dumps({"note": {"title": "x"}}), tmp_path, LINK)


def test_parse_stdout_rejects_missing_notes_json(tmp_path: Path) -> None:
    """最阴的一种失败：采集器报成功，但没落盘。

    此时调用方会以为可以继续，一路带着不存在的路径走到 loader
    才报「文件不存在」—— 那时已经看不出是采集的问题了。
    """
    with pytest.raises(CollectError, match="notes.json 不存在"):
        _parse_stdout(_stdout(tmp_path, write_json=False), tmp_path, LINK)


# ----------------------------------------------------------- collect()

def test_collect_raises_when_collector_missing(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("jev2.collect.collector_available", lambda: False)
    with pytest.raises(ConfigError, match="找不到采集器"):
        collect(LINK, tmp_path)


def test_collect_missing_hint_is_actionable(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """「请先安装」不够 —— 要给出能直接复制执行的命令。"""
    monkeypatch.setattr("jev2.collect.collector_available", lambda: False)
    with pytest.raises(ConfigError) as ei:
        collect(LINK, tmp_path)
    assert "pip install -e ." in str(ei.value)
    assert "xhs-cli" in str(ei.value)


def test_collect_command_shape(tmp_path: Path,
                               monkeypatch: pytest.MonkeyPatch) -> None:
    fake = _fake_run(stdout=_stdout(tmp_path))
    monkeypatch.setattr("jev2.collect.subprocess.run", fake)
    c = collect(LINK, tmp_path)
    cmd = fake.calls[0]          # type: ignore[attr-defined]
    assert cmd[1:4] == ["-m", "xhs_cli", "parse"]
    assert LINK in cmd
    assert "--out" in cmd and str(tmp_path) in cmd
    assert "--json" in cmd
    assert c.note_id == NID


def test_skip_images_must_precede_subcommand(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """``--skip-images`` 是**顶层**参数。

    放到 ``parse`` 后面会变成 ``xhs: error: unrecognized arguments``
    —— 实测踩过。这条测试就是钉住它。
    """
    fake = _fake_run(stdout=_stdout(tmp_path))
    monkeypatch.setattr("jev2.collect.subprocess.run", fake)
    collect(LINK, tmp_path, images=False)
    cmd = fake.calls[0]          # type: ignore[attr-defined]
    assert "--skip-images" in cmd
    assert cmd.index("--skip-images") < cmd.index("parse"), \
        "--skip-images 必须在子命令之前，否则 argparse 直接拒收"
    # 下载图片时不该出现这个开关
    fake2 = _fake_run(stdout=_stdout(tmp_path))
    monkeypatch.setattr("jev2.collect.subprocess.run", fake2)
    collect(LINK, tmp_path, images=True)
    assert "--skip-images" not in fake2.calls[0]  # type: ignore[attr-defined]


def test_collect_exit_code_gets_hint(tmp_path: Path,
                                     monkeypatch: pytest.MonkeyPatch) -> None:
    """退出码要翻译成人话 —— 「退出码 3」本身没有任何指导意义。"""
    for code, kw in ((2, "链接"), (3, "抓取失败"), (4, "落盘")):
        fake = _fake_run(returncode=code, stderr="[X] 原始错误\n")
        monkeypatch.setattr("jev2.collect.subprocess.run", fake)
        with pytest.raises(CollectError) as ei:
            collect(LINK, tmp_path)
        msg = str(ei.value)
        assert f"退出码 {code}" in msg
        assert kw in msg, f"退出码 {code} 的提示应含 {kw!r}"
        assert "原始错误" in msg, "采集器的原始报错要带出来"


def test_collect_error_carries_exit_code(tmp_path: Path,
                                         monkeypatch: pytest.MonkeyPatch) -> None:
    """退出码要**带出来**，不能丢。

    产品场景下调用方（脚本 / 服务）靠退出码决定要不要重试：
    「链接不对」（2）重试一万次也没用，「抓取失败」（3）值得重试。
    统一成 3 就把这个区分抹掉了。
    """
    for code in (2, 3, 4):
        monkeypatch.setattr("jev2.collect.subprocess.run",
                            _fake_run(returncode=code, stderr="x"))
        with pytest.raises(CollectError) as ei:
            collect(LINK, tmp_path)
        assert ei.value.code == code


def test_collect_error_default_code_is_zero(tmp_path: Path) -> None:
    """非退出码来源的失败（超时、契约破坏）code 为 0，
    由 CLI 决定兜底成 3。"""
    with pytest.raises(CollectError) as ei:
        _parse_stdout("", tmp_path, LINK)
    assert ei.value.code == 0


def test_collect_unknown_exit_code_still_reports(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    fake = _fake_run(returncode=9, stderr="boom")
    monkeypatch.setattr("jev2.collect.subprocess.run", fake)
    with pytest.raises(CollectError, match="退出码 9"):
        collect(LINK, tmp_path)


def test_collect_timeout(tmp_path: Path,
                         monkeypatch: pytest.MonkeyPatch) -> None:
    def hang(*a, **k):
        raise subprocess.TimeoutExpired(cmd="xhs", timeout=1)

    monkeypatch.setattr("jev2.collect.subprocess.run", hang)
    with pytest.raises(CollectError, match="超时"):
        collect(LINK, tmp_path, timeout=1)


def test_collect_oserror(tmp_path: Path,
                         monkeypatch: pytest.MonkeyPatch) -> None:
    def boom(*a, **k):
        raise OSError("no such file")

    monkeypatch.setattr("jev2.collect.subprocess.run", boom)
    with pytest.raises(CollectError, match="起不来"):
        collect(LINK, tmp_path)


def test_collect_logs_progress(tmp_path: Path,
                               monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("jev2.collect.subprocess.run",
                        _fake_run(stdout=_stdout(tmp_path)))
    logs: list[str] = []
    collect(LINK, tmp_path, log=logs.append)
    assert any("xhs-cli" in m for m in logs)
    assert any("落盘" in m for m in logs)


def test_collector_available_matches_reality() -> None:
    """环境里装了 xhs-cli 就该是 True —— 这个函数是产品入口的开关。"""
    import importlib.util
    expect = importlib.util.find_spec("xhs_cli") is not None
    assert collector_available() is expect


# --------------------------------------------------------------- CLI

def test_intake_subcommand_registered() -> None:
    from jev2.cli import build_parser
    ap = build_parser()
    args = ap.parse_args(["intake", LINK])
    assert args.link == LINK
    assert args.no_images is False
    assert args.no_semantic is False
    assert callable(args.func)


def test_intake_help_mentions_full_chain(capsys) -> None:
    from jev2.cli import build_parser
    ap = build_parser()
    with pytest.raises(SystemExit):
        ap.parse_args(["intake", "--help"])
    out = capsys.readouterr().out
    assert "采集" in out and "链接" in out


def test_intake_exit_code_follows_collector(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """CLI 层必须沿用采集器的退出码。

    这是产品化最关键的一点：脚本拿 exit code 决定要不要重试。
    全都返回 3 的话，「链接不对」会被无限重试。
    """
    from jev2.cli import main
    from jev2.config.schema import Config

    cfg = Config()
    cfg.paths.data_root = tmp_path / "data"
    cfg.paths.out_dir = tmp_path / "out"
    cfg.api_key = "sk-test-never-used"
    monkeypatch.setattr("jev2.cli.load_config", lambda **kw: cfg)

    for code in (2, 3, 4):
        def boom(*a, _c=code, **kw):
            raise CollectError(f"采集失败（退出码 {_c}）", code=_c)

        monkeypatch.setattr("jev2.collect.collect", boom)
        assert main(["intake", "https://example.com/foo"]) == code


def test_intake_returns_2_when_collector_missing(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """采集器没装 → 配置错误（2）。这是环境问题，不是链接问题。"""
    from jev2.cli import main
    from jev2.config.schema import Config

    cfg = Config()
    cfg.paths.data_root = tmp_path / "data"
    cfg.paths.out_dir = tmp_path / "out"
    cfg.api_key = "sk-test-never-used"
    monkeypatch.setattr("jev2.cli.load_config", lambda **kw: cfg)
    monkeypatch.setattr("jev2.collect.collector_available", lambda: False)
    assert main(["intake", "https://xhslink.cn/o/abc"]) == 2

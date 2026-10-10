"""pipeline + store + config 测试。

重点
----
1. **store 幂等**：同 note_id 覆盖，不重复追加
2. **元信息进产物**：run_id / config_hash 能区分「不同阈值跑的结果」
3. **语义层失败不伪装**：semantic_ok=False 要进产物
4. **路径解析**：从仓库根与 jev2/ 都指向同一处（踩过嵌套目录）
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

_HERE = Path(__file__).resolve()
for _p in (_HERE.parents[1] / "src", _HERE.parents[2] / "jev2" / "src"):
    if _p.is_dir() and str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from jev2.config import config_hash, load_config, mask, resolve_path  # noqa: E402
from jev2.config.schema import Config, FuseConfig                     # noqa: E402
from jev2.core.errors import ConfigError, DataError                   # noqa: E402
from jev2.core.types import Level                                     # noqa: E402
from jev2.pipeline.store import ResultStore, RunMeta                  # noqa: E402
from jev2.report import render_markdown, render_console, summarize    # noqa: E402


# --------------------------------------------------------------- 凭据掩码

def test_mask_never_leaks() -> None:
    key = "sk-abcdefghijklmnopqrstuvwxyz0123456789"
    m = mask(key)
    assert key not in m
    assert m.startswith("sk-a") and "len=" in m
    assert mask("") == "<空>"
    assert mask("short") == "*****"          # 太短就全遮


def test_config_to_dict_always_masks_key() -> None:
    """回归：``to_dict(mask_key=False)`` 曾能返回**明文 key**。

    一个能返回密钥的口子迟早会被误用（比如顺手写进日志），
    所以直接去掉这个参数 —— 需要 key 的地方读 ``cfg.api_key``。
    """
    cfg = Config()
    cfg.api_key = "sk-SECRET-VALUE-12345"
    d = cfg.to_dict()
    assert d["api_key"] == "***"
    assert "SECRET" not in json.dumps(d)
    # 确认没有 mask_key 这个口子
    import inspect
    assert "mask_key" not in inspect.signature(Config.to_dict).parameters
    # 空 key 时是空字符串（而不是星号）
    assert Config().to_dict()["api_key"] == ""


# --------------------------------------------------------------- 路径解析

def test_resolve_path_absolute_passthrough(tmp_path: Path) -> None:
    assert resolve_path(tmp_path) == tmp_path


def test_resolve_path_root_first_prefers_repo() -> None:
    """``root_first`` 时优先仓库根 —— 配置里的路径不该随 CWD 漂移。

    回归：``jev2/out`` 从 ``jev2/`` 跑曾解析成 ``jev2/jev2/out``。
    """
    p = resolve_path(Path("jev2"), root_first=True)
    assert p.name == "jev2"
    assert p.parent.name == "LOreal-ai"        # 仓库根下的 jev2


def test_resolve_path_nonexistent_stays_stable() -> None:
    """两条都不存在时也要返回确定结果（不能一会儿 CWD 一会儿仓库根）。"""
    a = resolve_path(Path("__no_such_dir_xyz__"), root_first=True)
    b = resolve_path(Path("__no_such_dir_xyz__"), root_first=True)
    assert a == b


# --------------------------------------------------------------- config

def test_default_config_has_sane_thresholds() -> None:
    cfg = Config()
    assert 0 < cfg.fuse.low < cfg.fuse.high < 1
    assert cfg.fuse.veto.get("is_ad") == 0.85
    assert abs(sum(cfg.fuse.weights.values()) - 1.0) < 1e-9


def test_config_from_dict_ignores_unknown_keys() -> None:
    """向前兼容：新配置里有旧代码不认识的项时不能炸。"""
    cfg = Config.from_dict({
        "schema_version": 1,
        "paths": {"data_root": "data", "future_option": True},
        "fuse": {"high": 0.8, "brand_new_knob": 42},
        "totally_unknown_section": {},
    })
    assert cfg.fuse.high == 0.8


def test_config_rejects_bad_thresholds(tmp_path: Path) -> None:
    p = tmp_path / "c.toml"
    p.write_text("[fuse]\nhigh = 0.2\nlow = 0.8\n", encoding="utf-8")
    with pytest.raises(ConfigError):
        load_config(path=p)


def test_config_rejects_future_schema(tmp_path: Path) -> None:
    p = tmp_path / "c.toml"
    p.write_text("schema_version = 999\n", encoding="utf-8")
    with pytest.raises(ConfigError):
        load_config(path=p)


def test_config_rejects_bad_l2_aggregate(tmp_path: Path) -> None:
    p = tmp_path / "c.toml"
    p.write_text('[fuse]\nl2_aggregate = "medianx"\n', encoding="utf-8")
    with pytest.raises(ConfigError):
        load_config(path=p)


def test_config_hash_changes_with_thresholds() -> None:
    a, b = Config(), Config()
    b.fuse.high = 0.9
    assert config_hash(a) != config_hash(b)


def test_config_hash_ignores_api_key() -> None:
    """key 不进 hash —— 否则换台机器同一份配置的产物就对不上了。"""
    a, b = Config(), Config()
    a.api_key = "sk-AAA"
    b.api_key = "sk-BBB"
    assert config_hash(a) == config_hash(b)


def test_load_config_require_key_raises_when_missing(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("JEV2_API_KEY", raising=False)
    monkeypatch.setattr("jev2.config.resolve_api_key", lambda: "")
    p = tmp_path / "c.toml"
    p.write_text("schema_version = 1\n", encoding="utf-8")
    with pytest.raises(ConfigError):
        load_config(path=p, require_key=True)


# --------------------------------------------------------------- store

def _row(nid: str, total: float = 0.5, level: str = "medium",
         **kw) -> dict:
    d = {"note_id": nid, "total": total, "level": level,
         "dimensions": {}, "signals": {}, "trace": [], "notes": []}
    d.update(kw)
    return d


def test_store_upsert_is_idempotent(tmp_path: Path) -> None:
    s = ResultStore(tmp_path)
    s.upsert(_row("a", 0.1, "low"))
    s.upsert(_row("a", 0.9, "high"))
    rows = s.load()
    assert len(rows) == 1 and rows[0]["total"] == 0.9


def test_store_upsert_many_merges(tmp_path: Path) -> None:
    s = ResultStore(tmp_path)
    s.upsert_many([_row("a"), _row("b")])
    assert len(s.load()) == 2
    s.upsert_many([_row("b", 0.7), _row("c")])
    rows = {r["note_id"]: r for r in s.load()}
    assert len(rows) == 3 and rows["b"]["total"] == 0.7


def test_store_upsert_many_no_merge_replaces(tmp_path: Path) -> None:
    s = ResultStore(tmp_path)
    s.upsert_many([_row("a"), _row("b")])
    s.upsert_many([_row("c")], merge=False)
    assert [r["note_id"] for r in s.load()] == ["c"]


def test_store_append_lines(tmp_path: Path) -> None:
    s = ResultStore(tmp_path)
    assert s.append_lines([_row("a"), _row("b")]) == 2
    assert s.append_lines([_row("c")]) == 1
    assert len(s.load()) == 3


def test_store_requires_note_id(tmp_path: Path) -> None:
    with pytest.raises(DataError):
        ResultStore(tmp_path).upsert({"total": 1})


def test_store_skips_broken_lines(tmp_path: Path) -> None:
    """一行坏了不该让整个报告出不来。"""
    p = tmp_path / "scores.jsonl"
    p.write_text('{"note_id":"a","total":0.1,"level":"low"}\n'
                 "{broken\n"
                 '{"note_id":"b","total":0.2,"level":"low"}\n',
                 encoding="utf-8")
    rows, bad = ResultStore(tmp_path).load_checked()
    assert len(rows) == 2 and len(bad) == 1


def test_store_existing_ids_and_reset(tmp_path: Path) -> None:
    s = ResultStore(tmp_path)
    s.upsert_many([_row("a"), _row("b")])
    assert s.existing_ids() == {"a", "b"}
    s.reset()
    assert s.load() == []


def test_store_atomic_write_leaves_valid_file(tmp_path: Path) -> None:
    """写盘用「临时文件 + 原子替换」—— 不会留下半个文件。"""
    s = ResultStore(tmp_path)
    s.upsert_many([_row("a")])
    assert not list(tmp_path.glob("*.tmp"))
    json.loads(s.path.read_text(encoding="utf-8").strip())


def test_store_summary_detects_mixed_runs(tmp_path: Path) -> None:
    s = ResultStore(tmp_path)
    s.upsert(_row("a", run_id="r1", config_hash="h1"))
    s.upsert(_row("b", run_id="r2", config_hash="h2"))
    info = s.summary()
    assert info["mixed_runs"] is True
    assert len(info["config_hashes"]) == 2
    assert info["level_counts"] == {"medium": 2}


def test_run_meta_has_all_provenance_fields() -> None:
    m = RunMeta.create(config_hash="abc", model="jev-1.13",
                       rule_set="default")
    d = m.to_dict()
    for k in ("schema_version", "run_id", "config_hash", "model",
              "rule_set", "scored_at"):
        assert k in d
    assert d["config_hash"] == "abc"


# --------------------------------------------------------------- report

def test_summarize_counts_levels() -> None:
    rows = [_row("a", 0.1, "low"), _row("b", 0.5, "medium"),
            _row("c", 0.9, "high"), _row("d", 1.0, "high", vetoed_by="ad_gate")]
    info = summarize(rows)
    assert info["total"] == 4
    assert info["levels"] == {"low": 1, "medium": 1, "high": 2}
    assert info["vetoed"] == 1


def test_summarize_empty() -> None:
    assert summarize([]) == {"total": 0}
    assert "没有结果" in render_markdown([])


def test_summarize_flags_semantic_failure() -> None:
    rows = [_row("a", semantic_ok=False)]
    assert summarize(rows)["semantic_failed"] == 1


def test_render_markdown_warns_on_mixed_config() -> None:
    rows = [_row("a", run_id="r1", config_hash="h1"),
            _row("b", run_id="r2", config_hash="h2")]
    md = render_markdown(rows)
    assert "混了" in md and "h1" in md


def test_render_markdown_has_trace_section() -> None:
    rows = [_row("a", 0.9, "high", trace=[
        {"rule": "ad_gate", "action": "veto", "value": 0.91,
         "weight": 0.0, "contribution": 0.0, "skipped": False,
         "reason": "is_ad=0.910 ≥ 0.85"}])]
    md = render_markdown(rows)
    assert "判定过程" in md and "ad_gate" in md and "0.910" in md


def test_render_console_one_line() -> None:
    rows = [_row("a", 0.1, "low"), _row("b", 0.9, "high")]
    s = render_console(rows)
    assert "2 篇" in s and "高风险 1" in s and "\n" not in s


def test_summarize_signal_missing_counts() -> None:
    rows = [_row("a", signals={
        "x": {"name": "x", "value": None, "missing": True, "n": 0},
        "y": {"name": "y", "value": 0.5, "missing": False, "n": 3}})]
    info = summarize(rows)
    assert info["signal_missing"]["x"] == 1
    assert info["signals"]["y"]["n"] == 1

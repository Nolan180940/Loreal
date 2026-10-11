"""单篇产物测试：``render_note_detail`` / ``write_note_bundle`` / ``per_note``。

为什么单篇产物需要单独测
------------------------
汇总 `scores.jsonl` 和单篇 `scores.json` 曾经共用渲染路径，很容易
写出「看着是单篇、实际把 40 篇全塞进去」的产物。所以这里钉死三条：

1. **单篇就是单篇** —— 目录里不能出现第二篇的 ``note_id``
2. **``scores.json`` 是 JSON 不是 JSONL** —— 顶层必须是 object，
   不是「一行一行拼起来」的数组
3. **``--note`` 与 ``--per-note`` 落盘一致** —— 两条路径产出同名文件

另外 `semantic_ok=False` 必须在单篇报告里显式警告，不能静默出分。
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

from jev2.config.schema import Config                                # noqa: E402
from jev2.core.types import (CommentRow, DimScore, Level, NoteRecord,  # noqa: E402
                             RuleTrace, SignalResult, Verdict)
from jev2.pipeline.runner import JudgeResult, Pipeline               # noqa: E402
from jev2.pipeline.store import RunMeta                              # noqa: E402
from jev2.report import (render_note_console, render_note_detail,     # noqa: E402
                         write_note_bundle)

NID = "6a7ebdfe00000000080122b8"
OTHER = "0f3c1a2b00000000010203ff"


# ------------------------------------------------------------------- 造数据

def _note(nid: str = NID, title: str = "后悔没早知道") -> NoteRecord:
    return NoteRecord(
        note_id=nid,
        title=title,
        desc="正文" * 40,
        author="别叫我小趴菜",
        liked=978,
        comment_count=94,
        images=("01.jpg",),
        comments=(
            CommentRow(cid="c1", content="好用", nickname="a",
                       ip_location="湖北", like_count="0", time_ms=1,
                       is_author=False, is_reply=False),
            CommentRow(cid="c2", content="多少钱", nickname="b",
                       ip_location="广东", like_count="0", time_ms=2,
                       is_author=False, is_reply=True),
        ),
    )


def _row(nid: str = NID, *, total: float = 0.7645,
         level: Level = Level.HIGH, vetoed: str = "",
         semantic_fail: bool = False) -> dict:
    """直接产出 scores.jsonl 形态的 row。"""
    v = Verdict(
        note_id=nid, total=total, level=level,
        dimensions=(
            DimScore("is_ad", 0.63),
            DimScore("has_risk", 0.86),
            DimScore("exaggeration", 0.983, confidence=0.95, qtype="score"),
            DimScore("is_cta", 0.11),
        ),
        signals=(
            SignalResult.ok("tag_count", 0.429, n=8,
                            detail={"tag_count": 8}),
            SignalResult.missing_("comment_like_rate",
                                  "16 条评论点赞全为 0，疑似匿名态未填充"),
        ),
        trace=(
            RuleTrace("ad_gate", "veto", 0.0, 0.0, 0.0),
            RuleTrace("is_ad", "contribute", 0.63, 0.25, 0.1575),
        ),
        vetoed_by=vetoed,
    )
    meta = RunMeta.create(config_hash="efe851c89c90", model="jev-1.13",
                          rule_set="default")
    return JudgeResult(note_id=nid, verdict=v,
                       semantic_ok=not semantic_fail,
                       elapsed_ms=866).to_row(meta=meta, note=_note(nid))


# ------------------------------------------------------ render_note_detail

def test_note_detail_has_all_sections() -> None:
    md = render_note_detail(_row(), title="后悔没早知道")
    for sec in ("## 结论", "## 笔记", "## 语义维度", "## 统计信号",
                "## 判定过程"):
        assert sec in md, f"缺章节 {sec}"
    assert NID in md
    assert "0.7645" in md
    assert "高风险" in md


def test_note_detail_only_mentions_this_note() -> None:
    """单篇报告里不能出现别的 note_id。"""
    md = render_note_detail(_row(), title="后悔没早知道")
    assert OTHER not in md
    # 只能出现一次自己的 id（标题行）
    assert md.count(NID) == 1


def test_note_detail_lists_missing_signal_with_reason() -> None:
    """缺失信号要列出**原因**，不能只是消失。"""
    md = render_note_detail(_row(), title="x")
    assert "comment_like_rate" in md
    assert "疑似匿名态未填充" in md


def test_note_detail_warns_semantic_failure() -> None:
    md = render_note_detail(_row(semantic_fail=True), title="x")
    assert "语义层失败" in md
    # 光有分数不够，得说清「偏低不是干净」
    assert "只含统计信号" in md
    # 正常的那篇不该出现这个警告
    assert "语义层失败" not in render_note_detail(_row(), title="x")


def test_note_detail_shows_veto() -> None:
    md = render_note_detail(_row(vetoed="ad_gate", level=Level.HIGH),
                            title="x")
    assert "一票否决" in md
    assert md.count("ad_gate") >= 2          # 结论 + trace 都该出现
    # 没被否决的就不该有这一行
    assert "一票否决" not in render_note_detail(_row(), title="x")


def test_note_detail_renders_trace_rows() -> None:
    md = render_note_detail(_row(), title="x")
    assert "ad_gate" in md and "is_ad" in md
    assert "contribute" in md


def test_note_detail_survives_empty_row() -> None:
    """极端情况不该抛异常 —— 报告生成失败比报告难看糟糕得多。"""
    assert render_note_detail({}, title="") is not None
    assert render_note_detail({"note_id": NID}, title="") is not None


# ------------------------------------------------------- write_note_bundle

def test_write_note_bundle_layout(tmp_path: Path) -> None:
    row = _row()
    info = write_note_bundle(tmp_path, row, title="后悔没早知道")
    d = tmp_path / NID
    assert Path(info["dir"]) == d
    assert Path(info["scores"]) == d / "scores.json"
    assert Path(info["report"]) == d / "report.md"
    assert (d / "scores.json").is_file()
    assert (d / "report.md").is_file()
    # 文件名就是约定的小写
    assert sorted(p.name for p in d.iterdir()) == ["report.md",
                                                   "scores.json"]


def test_write_note_bundle_scores_is_json_not_jsonl(tmp_path: Path) -> None:
    """``scores.json`` 必须是**单个 object**，不是 ndjson。"""
    write_note_bundle(tmp_path, _row(), title="x")
    raw = (tmp_path / NID / "scores.json").read_text(encoding="utf-8")
    d = json.loads(raw)                      # 整份能一次 parse
    assert isinstance(d, dict), "顶层应该是 object 而不是 list"
    assert d["note_id"] == NID
    # 缩进多行（pretty-print），不是压成一行
    assert "\n" in raw.strip()
    assert raw.lstrip().startswith("{\n")
    assert raw.rstrip().endswith("}")
    # 关键：整份文件只有一个 JSON 文档。若写成 jsonl（一行一篇），
    # 第一个 object 后面还会剩下另一个文档。
    dec = json.JSONDecoder()
    _, end = dec.raw_decode(raw)
    assert not raw[end:].strip(), "文件里还有第二个 JSON 文档（写成 jsonl 了）"


def test_write_note_bundle_single_note_only(tmp_path: Path) -> None:
    """连写两篇 → 两个目录，互不污染。"""
    write_note_bundle(tmp_path, _row(), title="第一篇")
    write_note_bundle(tmp_path, _row(OTHER, total=0.1, level=Level.LOW),
                      title="第二篇")
    a = (tmp_path / NID / "report.md").read_text(encoding="utf-8")
    b = (tmp_path / OTHER / "report.md").read_text(encoding="utf-8")
    assert OTHER not in a and NID not in b
    assert "第一篇" in a and "第二篇" in b
    ja = json.loads((tmp_path / NID / "scores.json").read_text("utf-8"))
    jb = json.loads((tmp_path / OTHER / "scores.json").read_text("utf-8"))
    assert ja["note_id"] == NID and jb["note_id"] == OTHER
    assert ja["total"] != jb["total"]


def test_write_note_bundle_is_idempotent(tmp_path: Path) -> None:
    """重跑覆盖，不追加。"""
    for _ in range(3):
        write_note_bundle(tmp_path, _row(), title="x")
    d = json.loads((tmp_path / NID / "scores.json").read_text("utf-8"))
    assert d["note_id"] == NID
    assert len(list((tmp_path / NID).iterdir())) == 2


def test_write_note_bundle_creates_missing_parents(tmp_path: Path) -> None:
    deep = tmp_path / "a" / "b" / "c"
    info = write_note_bundle(deep, _row(), title="x")
    assert (deep / NID / "scores.json").is_file()
    assert Path(info["report"]).is_file()


def test_write_note_bundle_rejects_row_without_id(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        write_note_bundle(tmp_path, {"total": 0.5}, title="x")


def test_bundle_json_matches_jsonl_row(tmp_path: Path) -> None:
    """单篇 json 必须和 jsonl 里那一行**完全一致** —— 否则看两份对不上。"""
    row = _row()
    write_note_bundle(tmp_path, row, title="x")
    d = json.loads((tmp_path / NID / "scores.json").read_text("utf-8"))
    assert d == row


# --------------------------------------------------------- render_note_console

def test_note_console_one_line() -> None:
    line = render_note_console(_row())
    assert "\n" not in line
    assert NID[:12] in line
    assert "高风险" in line
    assert "0.765" in line or "0.76" in line


def test_note_console_warns_on_semantic_failure() -> None:
    assert "语义" in render_note_console(_row(semantic_fail=True))


def test_note_console_shows_veto() -> None:
    assert "ad_gate" in render_note_console(_row(vetoed="ad_gate"))


# ------------------------------------------------- Pipeline.run(per_note=)

def _pipe(tmp_path: Path, rows: list[dict]) -> Pipeline:
    """构造一个不走网络的 Pipeline，judge_one 被替换成回放 rows。"""
    cfg = Config()
    cfg.paths.data_root = tmp_path / "data"
    cfg.paths.out_dir = tmp_path / "out"
    cfg.semantic.enabled = False
    pipe = Pipeline(cfg)
    pipe._replay = list(rows)                # type: ignore[attr-defined]

    def fake_judge(note: NoteRecord) -> JudgeResult:
        row = pipe._replay.pop(0)            # type: ignore[attr-defined]
        return JudgeResult(
            note_id=note.note_id,
            verdict=Verdict(note_id=note.note_id,
                            total=row["total"],
                            level=Level(row["level"]),
                            dimensions=tuple(
                                DimScore(k, v["value"])
                                for k, v in row["dimensions"].items()),
                            signals=tuple(
                                SignalResult.ok(k, v["value"] or 0.0)
                                for k, v in row["signals"].items()),
                            trace=tuple(
                                RuleTrace(t["rule"], t["action"],
                                          t.get("value"),
                                          t.get("weight", 0.0),
                                          t.get("contribution", 0.0))
                                for t in row["trace"])),
            semantic_ok=row.get("semantic_ok", True),
            elapsed_ms=1)

    pipe.judge_one = fake_judge                # type: ignore[method-assign]
    return pipe


def test_pipeline_per_note_writes_dirs(tmp_path: Path) -> None:
    rows = [_row(), _row(OTHER, total=0.1, level=Level.LOW)]
    notes = [_note(), _note(OTHER, title="第二篇")]
    pipe = _pipe(tmp_path, rows)
    stats = pipe.run(notes=notes, per_note=True)

    assert stats["ok"] == 2
    assert len(stats["note_dirs"]) == 2
    for nid in (NID, OTHER):
        d = tmp_path / "out" / nid
        assert (d / "scores.json").is_file(), f"{nid} 缺 scores.json"
        assert (d / "report.md").is_file(), f"{nid} 缺 report.md"
    # 汇总 jsonl 照旧
    assert (tmp_path / "out" / "scores.jsonl").is_file()


def test_pipeline_without_per_note_writes_no_dirs(tmp_path: Path) -> None:
    """默认不产生单篇目录 —— 避免 40 篇跑批刷出 40 个目录。"""
    pipe = _pipe(tmp_path, [_row()])
    stats = pipe.run(notes=[_note()])
    assert stats["note_dirs"] == []
    assert not (tmp_path / "out" / NID).exists()


def test_pipeline_per_note_survives_write_failure(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """单篇落盘失败不能拖垮整批 —— 汇总 jsonl 才是主产物。"""
    def boom(*a, **k):
        raise OSError("disk full")

    monkeypatch.setattr("jev2.pipeline.runner.write_note_bundle", boom)
    logs: list[str] = []
    pipe = _pipe(tmp_path, [_row()])
    pipe.log = logs.append
    stats = pipe.run(notes=[_note()], per_note=True)
    assert stats["ok"] == 1
    assert stats["note_dirs"] == []
    assert any("单篇产物写入失败" in m for m in logs)
    assert (tmp_path / "out" / "scores.jsonl").is_file()


# --------------------------------------------------------- 语义层熔断

def test_pipeline_aborts_on_consecutive_semantic_failures(
        tmp_path: Path) -> None:
    """上游 451 会让**每一篇**都失败。

    不熔断就会把整批写成「总分全 0 · semantic_ok=false」——
    那看着和「40 篇确实都干净」一模一样。所以宁可中止。
    """
    n = 6
    rows = [_row(f"{i:024x}", total=0.0, level=Level.LOW,
                 semantic_fail=True) for i in range(n)]
    notes = [_note(f"{i:024x}") for i in range(n)]
    logs: list[str] = []
    pipe = _pipe(tmp_path, rows)
    pipe.log = logs.append
    stats = pipe.run(notes=notes, max_consec_semantic_fail=3)

    assert stats["aborted"], "应该熔断"
    assert "连续 3 篇" in stats["aborted"]
    assert stats["ok"] == 3, "第 3 篇要落盘后再停（它本身是有效结果）"
    assert stats["semantic_failed"] == 3
    # 不能继续写后面那几篇
    assert not (tmp_path / "out" / f"{5:024x}").exists()
    assert any("未跑" in m for m in logs)


def test_pipeline_breaker_resets_on_success(tmp_path: Path) -> None:
    """偶发失败不熔断 —— 必须**连续**。"""
    rows = [
        _row(f"{0:024x}", semantic_fail=True),
        _row(f"{1:024x}"),
        _row(f"{2:024x}", semantic_fail=True),
        _row(f"{3:024x}", semantic_fail=True),
        _row(f"{4:024x}", total=0.1, level=Level.LOW),
        _row(f"{5:024x}", semantic_fail=True),
        _row(f"{6:024x}", semantic_fail=True),
    ]
    notes = [_note(f"{i:024x}") for i in range(len(rows))]
    pipe = _pipe(tmp_path, rows)
    stats = pipe.run(notes=notes, max_consec_semantic_fail=3)
    assert stats["aborted"] == ""
    assert stats["ok"] == len(rows)


def test_pipeline_breaker_disabled(tmp_path: Path) -> None:
    """``max_consec_semantic_fail=0`` = 关掉熔断（要跑完就显式关）。"""
    rows = [_row(f"{i:024x}", total=0.0, level=Level.LOW,
                 semantic_fail=True) for i in range(5)]
    notes = [_note(f"{i:024x}") for i in range(5)]
    pipe = _pipe(tmp_path, rows)
    stats = pipe.run(notes=notes, max_consec_semantic_fail=0)
    assert stats["aborted"] == ""
    assert stats["ok"] == 5


def test_pipeline_no_semantic_never_aborts(tmp_path: Path) -> None:
    """``--no-semantic`` 不调模型 → semantic_ok 恒 True → 永不熔断。"""
    rows = [_row(f"{i:024x}", total=0.0, level=Level.LOW)
            for i in range(5)]
    notes = [_note(f"{i:024x}") for i in range(5)]
    pipe = _pipe(tmp_path, rows)
    stats = pipe.run(notes=notes)
    assert stats["aborted"] == ""
    assert stats["semantic_failed"] == 0
    assert stats["ok"] == 5

"""loader 测试 —— 它是唯一认识数据结构的地方，必须锁死。

用**真实的字段形态**（从 40 篇里实测抄出来的）做断言，不是想象的 schema。
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

from jev2.core.errors import DataError                       # noqa: E402
from jev2.loader import (comment_key, iter_note_paths,       # noqa: E402
                         load_all, load_note, parse_count)


# --------------------------------------------------------------- 计数解析

@pytest.mark.parametrize(("raw", "expect"), [
    ("7546", 7546),
    (7546, 7546),
    ("1.2万", 12000),
    ("1万", 10000),
    ("2.5w", 25000),
    ("1千+", 1000),          # 评论 like_count 会出现；注意尾部 + 不能干扰单位识别
    ("2千+", 2000),
    ("3.5k", 3500),
    ("1,234", 1234),
    ("", 0),                 # 平台不公开
    ("-1", 0),               # 小乆书的「无」用 -1 表示
    ("-", 0),
    (None, 0),
    ("abc", 0),              # 脏数据不抛异常
    ("+", 0),
    (-5, 0),                 # 负数夹到 0
])
def test_parse_count(raw, expect) -> None:
    assert parse_count(raw) == expect


def test_parse_count_bool_not_confused() -> None:
    """``True`` 是 int 的子类 —— 别把「字段是 true」当成 1 之外的怪东西。"""
    assert parse_count(True) == 1
    assert parse_count(False) == 0


# --------------------------------------------------------------- 评论唯一键

def test_comment_key_prefers_id() -> None:
    assert comment_key({"id": "abc", "user_id": "u", "content": "x",
                        "time": 1}) == "abc"


def test_comment_key_falls_back_to_triple() -> None:
    """**新结构里没有评论 ``id``**（498/498 行都只有 user_id）。

    所以必须用 ``user_id|time|content[:20]`` 兜底 —— 实测这样组合
    在 498 行里 0 组重复。

    取前 20 字是为了避免超长文本参与比较，所以**超过 20 字**的
    正文只要前 20 字相同就算同键（同人同时且开头一致，
    实际就是同一条评论）。
    """
    head = "abcdefghij" * 3                    # 30 字，会触发截断
    k = comment_key({"user_id": "u1", "time": 123, "content": head})
    assert k == "u1|123|" + head[:20]
    # 前 20 字相同 → 同键（即使后面不同）
    assert comment_key({"user_id": "u1", "time": 123,
                        "content": head[:20] + "DIFFERENT"}) == k
    # 前 20 字不同 → 不同键
    assert comment_key({"user_id": "u1", "time": 123,
                        "content": "X" + head[:19] + "尾部"}) != k
    # 时间或用户不同 → 不同键
    assert comment_key({"user_id": "u2", "time": 123,
                        "content": head}) != k
    assert comment_key({"user_id": "u1", "time": 999,
                        "content": head}) != k


# --------------------------------------------------------------- 单篇

def _write(tmp_path: Path, payload: dict) -> Path:
    d = tmp_path / payload["note_id"]
    d.mkdir(parents=True, exist_ok=True)
    p = d / "notes.json"
    p.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return p


def _payload(**note_kw) -> dict:
    note = {
        "note_id": "a" * 24, "title": "标题", "desc": "正文",
        "author": "老王", "author_id": "u0",
        "liked": "100", "collected": "10", "comment_count": "5",
        "comment_count_l1": "3", "share": "2",
        "time_ms": "1700000000000", "ip_location": "上海",
        "tags": ["护肤", "笔记", "护肤"],       # 含假标签 + 重复
        "images": ["http://x/1.jpg"],
    }
    note.update(note_kw)
    return {"note_id": "a" * 24, "note": note,
            "images": ["http://x/1.jpg"], "comments": []}


def test_load_note_basic(tmp_path: Path) -> None:
    p = _write(tmp_path, _payload())
    n = load_note(p)
    assert n.note_id == "a" * 24
    assert n.liked == 100
    assert n.published_ms == 1_700_000_000_000
    # 「笔记」是界面文案（tabs 里的 name），必须剔除；重复项去掉
    assert n.tags == ("护肤",)


def test_load_note_hidden_counts_recorded(tmp_path: Path) -> None:
    """平台不公开的计数要记在 ``raw_counts`` 里 —— 值缺失 ≠ 值为 0。"""
    p = _write(tmp_path, _payload(collected="", share=""))
    n = load_note(p)
    assert n.collected == 0 and n.share == 0
    assert "collected" in n.raw_counts and "share" in n.raw_counts
    assert "liked" not in n.raw_counts


def test_load_note_comments_flat_and_author_derived(tmp_path: Path) -> None:
    """新结构没有评论 id，而且 ``is_author`` 恒 False —— loader 要兜底推导。"""
    pay = _payload()
    pay["comments"] = [
        {"user_id": "u1", "nickname": "读者", "content": "问题",
         "ip_location": "北京", "like_count": "0", "time": 1,
         "is_author": False, "_is_reply": False},
        {"user_id": "u0", "nickname": "老王", "content": "作者回复",
         "ip_location": "上海", "like_count": "0", "time": 2,
         "is_author": False, "_is_reply": True, "_parent_id": "p1"},
        {"user_id": "u2", "nickname": "路人", "content": "",
         "ip_location": "", "like_count": "0", "time": 3,
         "is_author": False, "_is_reply": False},          # 空正文 → 丢弃
    ]
    n = load_note(_write(tmp_path, pay))
    assert len(n.comments) == 2                              # 空正文被丢
    assert len(n.top_comments) == 1 and len(n.replies) == 1
    # 作者自评靠昵称推导出来（SSR 的 is_author 不可信）
    assert [c.nickname for c in n.author_comments] == ["老王"]
    assert n.replies[0].parent_id == "p1"


def test_load_note_dedupes_comments(tmp_path: Path) -> None:
    """同 (user_id, time, content) 的重复行要去掉。"""
    pay = _payload()
    row = {"user_id": "u1", "nickname": "x", "content": "同一条",
           "ip_location": "北京", "like_count": "0", "time": 1,
           "is_author": False, "_is_reply": False}
    pay["comments"] = [row, dict(row), row]
    n = load_note(_write(tmp_path, pay))
    assert len(n.comments) == 1


def test_load_note_flat_shape_without_note_wrapper(tmp_path: Path) -> None:
    """有的结构把字段直接摊在顶层（没有 ``note`` 包裹）。"""
    d = tmp_path / ("b" * 24)
    d.mkdir(parents=True)
    (d / "notes.json").write_text(json.dumps({
        "note_id": "b" * 24, "title": "T", "desc": "D", "liked": "7",
    }), encoding="utf-8")
    n = load_note(d / "notes.json")
    assert n.title == "T" and n.liked == 7


@pytest.mark.parametrize("bad", [
    {},                                     # 没有 note_id
    {"note": {}},                           # 有 note 但没 id
])
def test_load_note_rejects_without_id(tmp_path: Path, bad: dict) -> None:
    p = tmp_path / "x"
    p.mkdir()
    (p / "notes.json").write_text(json.dumps(bad), encoding="utf-8")
    with pytest.raises(DataError):
        load_note(p / "notes.json")


def test_load_note_rejects_missing_file(tmp_path: Path) -> None:
    with pytest.raises(DataError):
        load_note(tmp_path / "nope.json")


def test_load_note_rejects_broken_json(tmp_path: Path) -> None:
    p = tmp_path / "bad.json"
    p.write_text("{not json", encoding="utf-8")
    with pytest.raises(DataError):
        load_note(p)


# --------------------------------------------------------------- 批量

def test_iter_note_paths_filters_non_hex_dirs(tmp_path: Path) -> None:
    """只认 24 位 hex 目录 —— 数据目录里混着 ``.backup`` / ``search`` /
    ``<uuid>#<ts>`` 这类非笔记目录。"""
    for name in ("a" * 24, "b" * 24, ".backup", "search",
                 "f1881413-5d68-439e-9821-572dc5e65048#1790756154893"):
        (tmp_path / name).mkdir()
        (tmp_path / name / "notes.json").write_text("{}", encoding="utf-8")
    found = [p.parent.name for p in iter_note_paths(tmp_path)]
    assert sorted(found) == ["a" * 24, "b" * 24]


def test_load_all_skips_bad_and_reports(tmp_path: Path) -> None:
    """坏数据不中断批处理，但要如实返回。"""
    _write(tmp_path, _payload())
    d = tmp_path / ("c" * 24)
    d.mkdir()
    (d / "notes.json").write_text("{broken", encoding="utf-8")
    ok, bad = load_all(tmp_path)
    assert len(ok) == 1 and len(bad) == 1
    assert "c" * 24 in str(bad[0][0])


def test_load_all_raise_mode(tmp_path: Path) -> None:
    d = tmp_path / ("d" * 24)
    d.mkdir()
    (d / "notes.json").write_text("{broken", encoding="utf-8")
    with pytest.raises(DataError):
        load_all(tmp_path, on_error="raise")


def test_load_all_empty_dir(tmp_path: Path) -> None:
    assert load_all(tmp_path) == ([], [])
    assert load_all(tmp_path / "不存在") == ([], [])

"""xhs-cli 核心 HTTP 采集的单元测试。

覆盖
----
1. link.normalize 的 5 种输入形态
2. ssr.prepare / unescape 的转义边界（含 \\" 不被提前消费）
3. ssr_json 的括号配对 + json.loads
4. parse_comments 的快路径与慢路径一致性
5. 字段归一（likeCount 的 int / "1千+" / None）
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]
                      / "xhs-cli" / "src"))

from xhs_cli.core.link import LinkRef, normalize  # noqa: E402
from xhs_cli.core.ssr import parse, prepare, unescape  # noqa: E402
from xhs_cli.core.ssr_json import (  # noqa: E402
    _extract_array, _norm_like, flatten, parse_comments_json,
)

# ---------------------------------------------------------------- link

SHORT = "https://xhslink.cn/o/9E8z07rhA16"
LONG = ("https://www.xiaohongshu.com/discovery/item/6ac9205b0000000014001c57"
        "?xsec_token=CB00NUyp&xsec_source=app_share")


def test_normalize_short() -> None:
    ref = normalize(SHORT)
    assert ref.kind == "short"
    assert ref.needs_expand is True


def test_normalize_long_with_token() -> None:
    ref = normalize(LONG)
    assert ref.kind == "long"
    assert ref.note_id == "6ac9205b0000000014001c57"
    assert ref.token == "CB00NUyp"
    assert ref.needs_expand is False


def test_normalize_long_without_token_needs_expand() -> None:
    ref = normalize("https://www.xiaohongshu.com/explore/6ac9205b0000000014001c57")
    assert ref.kind == "long"
    assert ref.token == ""
    assert ref.needs_expand is True


def test_normalize_adds_scheme() -> None:
    ref = normalize("xiaohongshu.com/explore/6ac9205b0000000014001c57"
                    "?xsec_token=ABC")
    assert ref.url.startswith("https://")
    assert ref.note_id == "6ac9205b0000000014001c57"


@pytest.mark.parametrize("bad", [
    "",
    "   ",
    "https://example.com/foo",
    "https://www.xiaohongshu.com/explore/",   # 无 note id
])
def test_normalize_rejects(bad: str) -> None:
    from xhs_cli.core.link import UnsupportedLink
    with pytest.raises(UnsupportedLink):
        normalize(bad)


# ---------------------------------------------------------------- 转义

def test_prepare_only_unescapes_slashes() -> None:
    """prepare 绝不能把 \\" 变成真引号 —— 那会截断 content。"""
    raw = r'{"content":"他说\"你好\"","url":"http:\u002F\u002Fx.com\u002Fa"}'
    out = prepare(raw)
    assert '\\"' in out            # 引号仍是转义态
    assert "http://x.com/a" in out  # 斜杠已还原


def test_unescape_handles_quotes() -> None:
    assert unescape(r'他说\"你好\"') == '他说"你好"'
    assert unescape(r"line1\nline2") == "line1\nline2"


# ---------------------------------------------------------------- 括号配对

SSR = (
    r'"commentData":{"hasMore":true,"commentCountL1":9,"commentCount":16,'
    r'"comments":[{"status":0,'
    r'"user":{"userId":"613d769c000000000201fde2","nickname":"Lebesgue"},'
    r'"subCommentCount":2,"subComments":['
    r'{"atUsers":[{"userId":"633d4722000000001802dab6","nickname":"Claude"}],'
    r'"ipLocation":"北京","id":"6ac96ab200000000120034a6",'
    r'"user":{"userId":"5be6365a45d49c0001b6bc8a","nickname":"Scott"},'
    r'"content":"高思萌发狂了@Claude Lukas"},'
    r'{"content":"看来他家还是伪装成了私募","ipLocation":"浙江",'
    r'"user":{"userId":"56d122191c07df6826b5d78e","nickname":"葱油饼"},'
    r'"likeCount":"1千+"}],'
    r'"id":"6ac95d570000000011036337","ipLocation":"陕西",'
    r'"content":"是不是jukuan 加班风格像[doge]","likeCount":0}]}'
)


def test_extract_array_balanced() -> None:
    span = _extract_array(SSR, SSR.index("["))
    assert span is not None
    arr = SSR[span[0]:span[1]]
    assert arr.startswith("[") and arr.endswith("]")
    json.loads(arr)   # 必须是合法 JSON


def test_parse_comments_json_structure() -> None:
    rows = parse_comments_json(SSR)
    assert rows is not None
    assert len(rows) == 1                      # 只有 1 条一级
    top = rows[0]
    assert top["nickname"] == "Lebesgue"
    assert top["content"] == "是不是jukuan 加班风格像[doge]"
    assert top["ip_location"] == "陕西"
    assert top["_is_reply"] is False
    # 楼中楼
    assert len(top["_replies"]) == 2
    r0, r1 = top["_replies"]
    assert r0["nickname"] == "Scott"
    assert r0["content"] == "高思萌发狂了@Claude Lukas"
    assert r0["ip_location"] == "北京"
    assert r1["nickname"] == "葱油饼"
    assert r1["like_count"] == "1千+"
    assert r1["_is_reply"] is True
    assert r1["_parent_id"] == "6ac95d570000000011036337"


def test_parse_comments_json_rejects_garbage() -> None:
    assert parse_comments_json("<html>no state</html>") is None
    assert parse_comments_json('"commentData":{"comments":') is None


def test_flatten_order() -> None:
    rows = parse_comments_json(SSR)
    flat = flatten(rows)
    assert len(flat) == 3
    assert flat[0]["content"].startswith("是不是")
    assert flat[1]["_is_reply"] is True
    assert flat[2]["_is_reply"] is True


@pytest.mark.parametrize("val,expect", [
    (0, "0"), (12, "12"), (None, "0"), ("", "0"),
    ("1千+", "1千+"), ("1.2万", "1.2万"),
])
def test_norm_like(val, expect) -> None:
    assert _norm_like(val) == expect


# ---------------------------------------------------------------- 端到端 parse

def test_parse_full() -> None:
    r = parse(SSR)
    assert r["note"]["comment_count"] == "16"
    assert r["declared"] == 16
    assert r["got"] == 3
    assert r["complete"] is False
    flat = r["comments"]
    assert flat[0]["nickname"] == "Lebesgue"
    assert flat[1]["nickname"] == "Scott"
    assert flat[2]["like_count"] == "1千+"


def test_parse_falls_back_when_json_broken() -> None:
    """comments 数组损坏时，慢路径（正则）仍要出数据。"""
    broken = (
        r'"commentData":{"commentCount":5,"comments":['
        r'{"content":"第一 条","ipLocation":"北京","likeCount":3,'
        r'"user":{"userId":"aaaaaaaaaaaaaaaaaaaaaaaa","nickname":"用户A"}}'
        # 故意不闭合数组 —— json.loads 会失败
    )
    r = parse(broken)
    assert r["got"] >= 1
    assert any(c["content"].startswith("第一") for c in r["comments"])
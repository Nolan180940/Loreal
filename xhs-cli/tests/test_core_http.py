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

# 本文件在 xhs-cli/tests/ 下，包在 xhs-cli/src/xhs_cli/。
# 同时容忍被从仓库根目录调用（那时多一层）。
_HERE = Path(__file__).resolve()
for _p in (_HERE.parents[1] / "src",                 # <repo>/xhs-cli/src
           _HERE.parents[2] / "xhs-cli" / "src"):    # 兜底
    if _p.is_dir() and str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from xhs_cli.core.link import LinkRef, normalize  # noqa: E402
from xhs_cli.core.ssr import (  # noqa: E402
    _dedupe_images, _img_key, parse, prepare, unescape,
)
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


# --------------------------------------------------------------- 图片去重
#: 实测的 URL 形态（来自 6ab8e804）：同一张图两个 CDN 变换。
#: 注意 ``!`` 之前的 hash 目录**不同** —— 所以去重键必须取最后一段。
_IMG_A_H5 = ("http://sns-webpic-qc.xhscdn.com/202610102233/503ad482"
             "/notes_pre_post/1040g3kAAA!h5_1080jpg")
_IMG_A_STYLE = ("http://sns-webpic-qc.xhscdn.com/202610102233/ebac7d36"
                "/notes_pre_post/1040g3kAAA!style_d4c824bab532bfe9")
_IMG_B_H5 = ("http://sns-webpic-qc.xhscdn.com/202610102233/245e39b7"
             "/notes_pre_post/1040g3kBBB!h5_1080jpg")
_IMG_B_STYLE = ("http://sns-webpic-qc.xhscdn.com/202610102233/83641bad"
                "/notes_pre_post/1040g3kBBB!style_d4c824bab532bfe9")


def test_img_key_uses_last_segment_not_hash_dir() -> None:
    """两个变体的 ``!`` 前路径不同，但图片 ID 必须相同。"""
    assert _img_key(_IMG_A_H5) == _img_key(_IMG_A_STYLE) == "1040g3kAAA"
    assert _img_key(_IMG_A_H5) != _img_key(_IMG_B_H5)


#: 旧采集产物的形态：查询串 ``format/jpeg`` 里**含斜杠**。
#: 不先切掉 ``?`` 就会把整批图片都算成 ``"jpeg"``，误合成一张。
_IMG_OLD_A = ("https://ci.xiaohongshu.com/notes_pre_post/1040g3kAAA"
              "?imageView2/format/jpeg")
_IMG_OLD_B = ("https://ci.xiaohongshu.com/notes_pre_post/1040g3kBBB"
              "?imageView2/format/jpeg")


def test_img_key_ignores_slash_inside_query() -> None:
    """回归：``?imageView2/format/jpeg`` 曾让 7 张图被误合成 1 张。"""
    assert _img_key(_IMG_OLD_A) == "1040g3kAAA"
    assert _img_key(_IMG_OLD_B) == "1040g3kBBB"
    assert len(_dedupe_images([_IMG_OLD_A, _IMG_OLD_B])) == 2


def test_img_key_unifies_both_url_shapes() -> None:
    """同一张图的 sns-webpic 形态与 ci 形态必须归一到同一个 key。"""
    assert _img_key(_IMG_A_H5) == _img_key(_IMG_OLD_A) == "1040g3kAAA"


def test_dedupe_images_halves_the_count() -> None:
    """实测 6ab8e804 是 14 个 URL / 7 张图 —— 不去重会翻倍。"""
    urls = [_IMG_A_H5, _IMG_A_STYLE, _IMG_B_H5, _IMG_B_STYLE]
    assert len(_dedupe_images(urls)) == 2


def test_dedupe_prefers_display_variant() -> None:
    """``!style_*`` 是样式预览版，要选 h5 展示版。"""
    assert _dedupe_images([_IMG_A_STYLE, _IMG_A_H5]) == [_IMG_A_H5]
    # 反过来给也一样
    assert _dedupe_images([_IMG_A_H5, _IMG_A_STYLE]) == [_IMG_A_H5]


def test_dedupe_keeps_style_when_it_is_the_only_one() -> None:
    assert _dedupe_images([_IMG_A_STYLE]) == [_IMG_A_STYLE]


def test_dedupe_preserves_first_seen_order() -> None:
    """去重后保持首次出现的顺序 —— 图片顺序就是帖子里的顺序。"""
    urls = [_IMG_B_H5, _IMG_A_STYLE, _IMG_A_H5, _IMG_B_STYLE]
    assert _dedupe_images(urls) == [_IMG_B_H5, _IMG_A_H5]


def test_parse_note_images_deduped() -> None:
    """端到端：``parse()`` 出来的 images 必须是去重后的张数。"""
    html = (
        '"noteId":"6ab8e804000000000200d3cd","title":"t","desc":"d",'
        f'"url":"{_IMG_A_H5}","url":"{_IMG_A_STYLE}",'
        f'"url":"{_IMG_B_H5}","url":"{_IMG_B_STYLE}"'
    )
    assert len(parse(html)["note"]["images"]) == 2


# ------------------------------------------------------- --out 目录落盘
#: 各格式的最小合法头部（用于验证按内容判扩展名）。
_PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 16
_GIF = b"GIF89a" + b"\x00" * 16
_WEBP = b"RIFF\x00\x00\x00\x00WEBP" + b"\x00" * 16
_JPG = b"\xff\xd8\xff\xe0" + b"\x00" * 16
#: 认不出的字节流 —— 必须退回 .jpg，不能抛异常。
_UNKNOWN = b"\x00\x01\x02\x03" * 8


@pytest.mark.parametrize(("data", "expect"), [
    (_JPG, ".jpg"),
    (_PNG, ".png"),
    (_GIF, ".gif"),
    (_WEBP, ".webp"),
    (_UNKNOWN, ".jpg"),
])
def test_img_ext_sniffs_by_content(data: bytes, expect: str) -> None:
    """回归：小红书 CDN 的 URL 是 ``!h5_1080jpg`` 这种伪后缀。

    没有点号，``splitext`` 拿不到扩展名，所以**必须按内容判**。
    认不出的退回 ``.jpg``（绝大多数是 JPEG），不能崩。
    """
    from xhs_cli.cli import _img_ext

    assert _img_ext(data) == expect


def test_img_ext_ignores_lying_url_suffix() -> None:
    """URL 说 jpg、内容其实是 png 时，以内容为准。"""
    from xhs_cli.cli import _img_ext

    assert _img_ext(_PNG) == ".png"
    assert "1040g3kAAA!h5_1080jpg".endswith("jpg")   # URL 确实在说谎


def test_write_post_dir_creates_images_and_notes(tmp_path: Path) -> None:
    """``--out`` 的产物契约：``<DIR>/<note_id>/{01.jpg, notes.json}``。"""
    from unittest import mock

    from xhs_cli import cli

    result = {
        "note_id": "6ac3c7f4000000001b02fc03",
        "note": {"title": "t", "desc": "d"},
        "images": ["http://cdn/a!h5_1080jpg", "http://cdn/b!h5_1080jpg"],
        "comments": [{"id": "c1", "content": "hi"}],
        "declared": 10, "got": 1, "complete": False, "elapsed_ms": 5,
    }
    # 与 cmd_parse 构造 payload 的方式一致
    payload = {k: result[k] for k in ("note", "images", "comments",
                                     "declared", "got", "complete")}

    with mock.patch("xhs_cli.core.fetch.fetch_image",
                    side_effect=[_JPG, _PNG]) as m:
        info = cli.write_post_dir(result, tmp_path, payload)

    assert m.call_count == 2
    d = tmp_path / "6ac3c7f4000000001b02fc03"
    # 序号与 images 数组下标对齐，扩展名按内容判
    assert (d / "01.jpg").read_bytes() == _JPG
    assert (d / "02.png").read_bytes() == _PNG
    assert info["images"] == 2 and info["urls"] == 2

    saved = json.loads((d / "notes.json").read_text(encoding="utf-8"))
    assert saved["image_files"] == ["01.jpg", "02.png"]
    # notes.json 是 --save 那份 JSON 的超集：原有键一个不少
    for k in ("note", "images", "comments", "declared", "got", "complete"):
        assert k in saved
    assert saved["images"] == result["images"]   # 仍是 URL 列表，没被换掉


def test_write_post_dir_survives_image_failure(tmp_path: Path) -> None:
    """单张图挂了不能让整篇失败 —— JSON 比图片重要。"""
    from unittest import mock

    from xhs_cli import cli
    from xhs_cli.core.fetch import FetchError

    result = {
        "note_id": "6ac9205b0000000014001c57",
        "note": {"title": "t"}, "images": ["http://cdn/a", "http://cdn/b"],
        "comments": [], "declared": 0, "got": 0, "complete": True,
        "elapsed_ms": 1,
    }
    with mock.patch("xhs_cli.core.fetch.fetch_image",
                    side_effect=[FetchError("boom", kind="image_network"),
                                 _JPG]):
        info = cli.write_post_dir(result, tmp_path, {})

    d = tmp_path / "6ac9205b0000000014001c57"
    # 文件名按 **URL 数组下标** 命名，不重新编号 ——
    # 所以第 1 个失败时保留下来的就是 02.jpg，
    # 反查回去就能知道它是 images[1]。
    assert (d / "02.jpg").exists()
    assert not (d / "01.jpg").exists()
    assert info["images"] == 1 and info["urls"] == 2
    assert info["errors"][0]["index"] == 1

    saved = json.loads((d / "notes.json").read_text(encoding="utf-8"))
    assert saved["image_errors"][0]["url"] == "http://cdn/a"
    assert saved["image_files"] == ["02.jpg"]


def test_write_post_dir_requires_note_id(tmp_path: Path) -> None:
    """没有 note_id 就没法建目录，必须显式报错而不是写进一个怪名字。"""
    from xhs_cli import cli

    with pytest.raises(ValueError):
        cli.write_post_dir({"images": []}, tmp_path, {})
"""读取层的单元测试 —— 重点覆盖双 schema 兼容。

背景：``data/`` 目录里中英文两套 key 混存，读取层必须都认。
这个测试就是防止有人后来只认一套，把好数据读成空。
"""

from __future__ import annotations

import json
import sys
from dataclasses import fields
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from jev_guard.extractors.reader import (Subject, load_comments, load_note,
                                         note_ip_stats, pick, split_tags, to_int)

NID = "0123456789abcdef01234567"


@pytest.fixture()
def zh_dir(tmp_path: Path) -> Path:
    """中文 schema（旧 Spider_XHS 产物）。"""
    d = tmp_path / NID
    (d / "content").mkdir(parents=True)
    (d / "images").mkdir(parents=True)
    (d / "comments").mkdir(parents=True)
    (d / "content" / "note.json").write_text(json.dumps({
        "作品标题": "兰蔻小黑瓶眼霜",
        "作品描述": "专柜购入，中规中矩测评！",
        "作品标签": "兰蔻小黑瓶眼霜 眼霜",
        "作者昵称": "噜啦啦",
        "点赞数量": "126", "收藏数量": "43",
        "评论数量": "81", "分享数量": "36",
        "下载地址": ["https://ci.xiaohongshu.com/a.jpeg"],
        "作品ID": NID,
    }, ensure_ascii=False), encoding="utf-8")
    return tmp_path


@pytest.fixture()
def en_dir(tmp_path: Path) -> Path:
    """英文 schema（xhs-cli 产物）。"""
    d = tmp_path / NID
    (d / "content").mkdir(parents=True)
    (d / "images").mkdir(parents=True)
    (d / "comments").mkdir(parents=True)
    (d / "content" / "note.json").write_text(json.dumps({
        "note_id": NID, "title": "AGE面霜", "desc": "三个月真实感受",
        "tags": ["面霜", "抗老"], "author": "someone",
        "liked": "1047", "collected": "352",
        "comment_count": "273", "share_count": "185",
        "images": [{"url": "http://sns/x.webp"}],
    }, ensure_ascii=False), encoding="utf-8")
    return tmp_path


class TestPick:
    def test_prefers_english(self):
        assert pick({"desc": "EN", "作品描述": "ZH"}, "desc") == "EN"

    def test_falls_back_to_chinese(self):
        assert pick({"作品描述": "ZH"}, "desc") == "ZH"

    def test_missing_returns_default(self):
        assert pick({}, "desc", "缺省") == "缺省"

    def test_empty_string_is_not_a_value(self):
        """空字符串应继续回退，不能当成有效值。"""
        assert pick({"desc": "", "作品描述": "ZH"}, "desc") == "ZH"

    def test_zero_is_a_valid_value(self):
        assert pick({"desc": "", "作品描述": 0}, "desc") == 0


class TestToInt:
    def test_plain_int(self):
        assert to_int("126") == 126

    def test_minus_one_becomes_zero(self):
        """小红书用 -1 表示「无」，不是缺失。"""
        assert to_int("-1") == 0

    def test_wan_suffix(self):
        assert to_int("1.2万") == 12000

    def test_k_suffix(self):
        assert to_int("3.5k") == 3500

    def test_comma_separated(self):
        assert to_int("1,234") == 1234

    def test_dash_becomes_zero(self):
        assert to_int("-") == 0

    def test_garbage_becomes_zero(self):
        assert to_int("暂无") == 0

    def test_none_becomes_default(self):
        assert to_int(None, default=5) == 5


class TestSplitTags:
    def test_list_passthrough(self):
        assert split_tags(["a", "b"]) == ["a", "b"]

    def test_space_separated_string(self):
        """中文 schema 里 作品标签 是空格分隔字符串。"""
        assert split_tags("兰蔻小黑瓶眼霜 眼霜") == ["兰蔻小黑瓶眼霜", "眼霜"]

    def test_empty(self):
        assert split_tags("") == []
        assert split_tags(None) == []


class TestLoadNote:
    def test_chinese_schema(self, zh_dir):
        s = load_note(zh_dir, NID)
        assert s is not None
        assert s.title == "兰蔻小黑瓶眼霜"
        assert s.liked == 126 and s.collected == 43
        assert s.comment_count == 81 and s.share == 36
        assert s.author == "噜啦啦"
        assert s.tags == ("兰蔻小黑瓶眼霜", "眼霜")
        assert s.image_count == 1

    def test_english_schema(self, en_dir):
        s = load_note(en_dir, NID)
        assert s is not None
        assert s.title == "AGE面霜"
        assert s.liked == 1047
        assert s.tags == ("面霜", "抗老")

    def test_two_schemas_produce_comparable_subjects(self, tmp_path):
        """核心保证：两套 schema 读出的 Subject 结构完全一致。"""
        zh = load_note(_mk(tmp_path / "zh", zh_payload()), NID)
        en = load_note(_mk(tmp_path / "en", en_payload()), NID)
        # Subject 用了 slots，没有 __dict__，要比 dataclass 字段集
        zh_fields = {f.name for f in fields(Subject)}
        en_fields = {f.name for f in fields(Subject)}
        assert zh_fields == en_fields
        assert zh.liked == en.liked               # 取值路径一致

    def test_missing_file_returns_none(self, tmp_path):
        assert load_note(tmp_path, "ffffffffffffffffffffffff") is None

    def test_malformed_json_returns_none(self, zh_dir):
        (zh_dir / NID / "content" / "note.json").write_text("{broken",
                                                              encoding="utf-8")
        assert load_note(zh_dir, NID) is None

    def test_text_for_model_includes_title(self, zh_dir):
        """标题必须进模型 —— 夸大标题的风险分显著高于仅看正文。"""
        s = load_note(zh_dir, NID)
        txt = s.text_for_model
        assert "标题：" in txt and "正文：" in txt and "话题：" in txt
        assert "兰蔻小黑瓶眼霜" in txt

    def test_text_for_model_without_tags(self, zh_dir):
        n = json.loads((zh_dir / NID / "content" / "note.json")
                       .read_text(encoding="utf-8"))
        n.pop("作品标签")
        (zh_dir / NID / "content" / "note.json").write_text(
            json.dumps(n, ensure_ascii=False), encoding="utf-8")
        s = load_note(zh_dir, NID)
        assert "话题：" not in s.text_for_model


class TestLoadComments:
    def _write(self, root: Path, rows: list) -> Path:
        d = root / NID / "comments"
        d.mkdir(parents=True, exist_ok=True)
        (d / "comments.json").write_text(
            json.dumps(rows, ensure_ascii=False), encoding="utf-8")
        return root

    def test_reads_rows(self, tmp_path):
        root = self._write(tmp_path, [
            {"id": "c1", "content": "好用", "like_count": "5",
             "user_info": {"nickname": "u1"}, "ip_location": "广东"},
            {"id": "c2", "content": "一般", "like_count": "0",
             "user_info": {"nickname": "u2"}},
        ])
        cs = load_comments(root, NID)
        assert len(cs) == 2
        assert cs[0].author == "u1" and cs[0].liked == 5
        assert cs[0].parent_id == NID

    def test_nick_name_alias(self, tmp_path):
        """新抓的数据用 nick_name，旧数据用 nickname，两个都要认。"""
        root = self._write(tmp_path, [
            {"id": "c1", "content": "x", "user_info": {"nick_name": "新字段"}},
            {"id": "c2", "content": "y", "user_info": {"nickname": "旧字段"}},
        ])
        cs = load_comments(root, NID)
        assert {c.author for c in cs} == {"新字段", "旧字段"}

    def test_skips_empty_text_and_missing_id(self, tmp_path):
        root = self._write(tmp_path, [
            {"id": "c1", "content": "   "},          # 空正文
            {"id": "", "content": "有正文但无 id"},
            {"id": "c3", "content": "正常"},
        ])
        cs = load_comments(root, NID)
        assert len(cs) == 1 and cs[0].subject_id == "c3"

    def test_not_a_list_returns_empty(self, tmp_path):
        root = self._write(tmp_path, {"oops": 1})
        assert load_comments(root, NID) == []


class TestIPStats:
    def test_concentrated_ips_detected(self, tmp_path):
        d = tmp_path / NID / "comments"
        d.mkdir(parents=True)
        rows = [{"id": f"c{i}", "content": "x", "ip_location": "广东"}
                for i in range(20)]
        (d / "comments.json").write_text(json.dumps(rows), encoding="utf-8")
        st = note_ip_stats(tmp_path, NID)
        assert st["ip_n"] == 20
        assert st["ip_top1_ratio"] == 1.0      # 全部集中
        assert st["ip_entropy"] < 0.01         # 熵接近 0

    def test_sparse_ips_high_entropy(self, tmp_path):
        d = tmp_path / NID / "comments"
        d.mkdir(parents=True)
        provinces = ["广东", "四川", "山东", "江苏", "上海", "浙江",
                     "河南", "内蒙古", "福建", "湖北"]
        rows = [{"id": f"c{i}", "content": "x",
                 "ip_location": provinces[i % 10]} for i in range(20)]
        (d / "comments.json").write_text(json.dumps(rows), encoding="utf-8")
        st = note_ip_stats(tmp_path, NID)
        assert st["ip_top1_ratio"] == 0.1
        assert st["ip_entropy"] > 0.9

    def test_too_few_samples_returns_zero(self, tmp_path):
        """样本 <5 时统计量不可靠，必须返回 0 而不是噪声。"""
        d = tmp_path / NID / "comments"
        d.mkdir(parents=True)
        rows = [{"id": "c1", "content": "x", "ip_location": "广东"}]
        (d / "comments.json").write_text(json.dumps(rows), encoding="utf-8")
        assert note_ip_stats(tmp_path, NID)["ip_top1_ratio"] == 0.0

    def test_missing_ip_field(self, tmp_path):
        d = tmp_path / NID / "comments"
        d.mkdir(parents=True)
        (d / "comments.json").write_text(json.dumps([]), encoding="utf-8")
        assert note_ip_stats(tmp_path, NID)["ip_n"] == 0.0


# ---------------------------------------------------------------- helpers

def zh_payload() -> dict:
    return {"作品标题": "T", "作品描述": "D", "作品标签": "a b",
            "点赞数量": "126", "收藏数量": "43",
            "评论数量": "81", "分享数量": "36",
            "下载地址": ["u"], "作者昵称": "u"}

def en_payload() -> dict:
    return {"note_id": NID, "title": "T", "desc": "D", "tags": ["a", "b"],
            "liked": "126", "collected": "43",
            "comment_count": "81", "share_count": "36",
            "images": [{"url": "u"}], "author": "u"}

def _mk(root: Path, payload: dict) -> Path:
    (root / NID / "content").mkdir(parents=True)
    (root / NID / "images").mkdir(parents=True)
    (root / NID / "content" / "note.json").write_text(
        json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return root
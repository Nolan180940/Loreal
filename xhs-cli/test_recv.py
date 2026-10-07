"""本地自测：不经浏览器，直接给 recv_server 的 save_note 喂一条样本数据。

用来在启动浏览器之前先验证落盘逻辑，避免把时间浪费在 CORS / 渲染等待上。

用法:
    python xhs-cli/test_recv.py
"""

from __future__ import annotations

import json
import shutil
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
sys.stdout.reconfigure(encoding="utf-8")

import recv_server  # noqa: E402

SAMPLE = {
    "note_id": "aaaaaaaaaaaaaaaaaaaaaaaa",
    "note": {
        "title": "测试标题",
        "desc": "正文内容，用于验证落盘与字段对齐。",
        "tags": ["tagA", "tagB"],
        "author": "作者昵称",
        "author_id": "5fa01262000000000101cc25",
        "author_link": "https://www.xiaohongshu.com/user/profile/5fa01262000000000101cc25",
        "link": "https://www.xiaohongshu.com/explore/aaaa...?xsec_token=T",
        "type": "图文",
        "time_ms": 1777951411000,
        "ip_location": "上海",
        "liked": "126",
        "collected": "43",
        "comment_count": "3",
        "share_count": "36",
    },
    "images": [
        {"idx": 0, "url": "", "w": 0, "h": 0},
    ],
    "comments": [
        {"id": "c1", "content": "一级评论", "create_time": 1777951411,
         "ip_location": "广东", "like_count": "5",
         "user_info": {"user_id": "u1", "nick_name": "用户1", "image": ""},
         "sub_comment_count": 1, "pictures": [], "_is_reply": False},
        {"id": "c2", "content": "楼中楼回复", "create_time": 1777951412,
         "ip_location": "北京", "like_count": "1",
         "user_info": {"user_id": "u2", "nick_name": "用户2", "image": ""},
         "sub_comment_count": 0, "pictures": [], "_is_reply": True,
         "_parent_id": "c1"},
    ],
    "pages": 1,
    "source": "browser_dom",
}


def main() -> int:
    tmp = Path(tempfile.mkdtemp(prefix="recv_test_"))
    recv_server.OUT_ROOT = tmp
    try:
        r = recv_server.save_note(SAMPLE["note_id"], SAMPLE)
        print(f"save_note -> {r}")

        nid = SAMPLE["note_id"]
        note = json.loads((tmp / nid / "content" / "note.json").read_text(encoding="utf-8"))
        card = json.loads((tmp / nid / "comments" / "card.json").read_text(encoding="utf-8"))
        cmts = json.loads((tmp / nid / "comments" / "comments.json").read_text(encoding="utf-8"))
        urls = json.loads((tmp / nid / "images" / "urls.json").read_text(encoding="utf-8"))
        md = (tmp / nid / "content" / "note.md").read_text(encoding="utf-8")

        # 关键断言：中文 key 必须齐（下游按中文 schema 读）
        need_zh = ["作品标题", "作品描述", "作品标签", "作品ID", "作品链接",
                   "作品类型", "发布时间", "最后更新时间", "时间戳",
                   "作者昵称", "作者ID", "作者链接", "IP属地",
                   "点赞数量", "收藏数量", "评论数量", "分享数量",
                   "下载地址", "动图地址", "封面地址"]
        missing = [k for k in need_zh if k not in note]
        print(f"中文 key 缺失: {missing or '无'}")
        print(f"标签类型: {type(note['作品标签']).__name__} = {note['作品标签']!r}")
        print(f"card: total={card['total']} top={card['top_level']} "
              f"rep={card['replies']} expect={card['note_reported']} "
              f"partial={card['partial']}")
        print(f"comments.json: {len(cmts)} 条, is_reply 分布="
              f"{[c['_is_reply'] for c in cmts]}")
        print(f"urls.json: {len(urls)} 条")
        print(f"note.md 首行: {md.splitlines()[0]}")
        return 1 if missing else 0
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
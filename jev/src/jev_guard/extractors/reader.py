"""采集数据的读取层。

必须处理的一个现实
------------------
``data/`` 目录里是**两套schema 混存**的：

- 早期 Spider_XHS 产物：中文 key（``作品标题``/``点赞数量``…），``作品标签`` 是空格分隔字符串
- 后期 jev-guard 产物：英文 key（``title``/``liked``…），``tags`` 是数组

``xhs-cli`` 写的 ``recv_server.py`` 已经是双写，但历史文件改不了。
所以读取层**必须**同时认两套，否则会把好数据误判成空。

本模块是唯一知道这件事的地方；上游拿到的永远是统一的
:class:`~jev_guard.core.models.Subject` 视图。
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterator

NOTE_ID_LEN = 24

#: 计算评论长度标准差所需的最少评论数。
#:
#: 2 条评论的标准差在数学上必然很小（无论内容是否刷评），
#: 所以样本不足时不报 flag，只把 n 透出去给上层展示。
SPREAD_MIN_COMMENTS = 3

#: 标准差低于此值判为「评论区整齐得不自然」。
#:
#: 依据（tools/validate_signals.py，人工判读 24 条）：
#:   人工 high 的5 篇里 4 篇 SD ≤ 6.1
#:   人工 low  的 14 篇里 13 篇 SD ≥ 8.6
#: 阈值取 7 落在两组之间。唯一被漏掉的是 `6a7ebdfe`(SD=15.6)——
#: 个人号的真实测评帖，评论区在认真讨论，属于可接受的方向性误差。
SPREAD_SD_THRESHOLD = 7.0


def pick(note: dict[str, Any], key: str, default: Any = None) -> Any:
    """按 ``key`` 取值，自动回退到中文别名。

    ``key`` 传英文（``desc``），命中 ``作品描述`` 时也会返回。
    """
    aliases = FIELD_ALIASES.get(key, (key,))
    for k in aliases:
        if k in note and note[k] not in (None, ""):
            return note[k]
    return default


#: 英文 key -> 中文 key 别名表
FIELD_ALIASES: dict[str, tuple[str, ...]] = {
    "title": ("title", "作品标题"),
    "desc": ("desc", "作品描述"),
    "tags": ("tags", "作品标签"),
    "author": ("author", "作者昵称"),
    "author_id": ("author_id", "作者ID"),
    "liked": ("liked", "点赞数量"),
    "collected": ("collected", "收藏数量"),
    "comment_count": ("comment_count", "评论数量"),
    "share": ("share_count", "share", "分享数量"),
    "published": ("published", "发布时间"),
    "ip_location": ("ip_location", "IP属地"),
    "image_urls": ("images", "下载地址"),
}


def to_int(v: Any, default: int = 0) -> int:
    """安全转int。

    小红书的计数有两个坑：
    1. ``-1`` 表示「无/未公开」，不是缺失 —— 按 0 处理。
    2. 搜索快照里是 ``"1.2万"`` 这种字符串，:func:`parse_count` 处理。
    """
    if v is None:
        return default
    if isinstance(v, (int, float)):
        return max(int(v), 0)
    s = str(v).strip().replace(",", "")
    if not s or s in {"-", "-1"}:
        return 0
    mult = 1
    if s.endswith("万"):
        mult, s = 10000, s[:-1]
    elif s.endswith("w") or s.endswith("W"):
        mult, s = 10000, s[:-1]
    elif s.endswith("k") or s.endswith("K"):
        mult, s = 1000, s[:-1]
    try:
        return max(int(float(s) * mult), 0)
    except ValueError:
        return default


def parse_count(v: Any) -> int | None:
    """解析可能带「万」后缀的计数，失败返回 ``None``（区别于 0）。"""
    if v is None:
        return None
    return to_int(v, default=-1) if to_int(v, default=-1) >= 0 else None


def split_tags(v: Any) -> list[str]:
    """``tags`` 可能是数组，也可能是空格分隔字符串。"""
    if isinstance(v, list):
        return [str(t).strip() for t in v if str(t).strip()]
    if isinstance(v, str) and v.strip():
        return [t for t in v.replace("，", " ").split() if t]
    return []


@dataclass(slots=True)
class Subject:
    """统一的内容视图。上游只认这个，不认原始 JSON。"""

    subject_id: str
    kind: str                      # "note" | "comment"
    text: str = ""# 送进模型的正文
    title: str = ""
    tags: tuple[str, ...] = ()
    author: str = ""
    liked: int = 0
    collected: int = 0
    comment_count: int = 0
    share: int = 0
    image_count: int = 0
    parent_id: str = ""            # 评论所属笔记
    raw: dict[str, Any] = field(default_factory=dict)

    @property
    def text_for_model(self) -> str:
        """拼成适合判断的文本：标题 + 正文 + 标签。

        标题必须带上—— 实测夸大标题（「杀伤力为100000%」）的风险分
        显著高于仅看正文时的结果。
        """
        parts = []
        if self.title:
            parts.append(f"标题：{self.title}")
        if self.text:
            parts.append(f"正文：{self.text}")
        if self.tags:
            parts.append(f"话题：{' '.join(self.tags)}")
        return "\n".join(parts)


def _read_json(p: Path) -> Any:
    if not p.is_file():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError, OSError):
        return None


def iter_note_ids(data_root: Path) -> Iterator[str]:
    """列出所有笔记 ID（24 位 hex 目录名）。"""
    if not data_root.is_dir():
        return
    for d in sorted(data_root.iterdir()):
        if d.is_dir() and len(d.name) == NOTE_ID_LEN:
            yield d.name


def load_note(data_root: Path, note_id: str) -> Subject | None:
    """读单篇笔记。缺 ``note.json`` 返回 ``None``。"""
    d = Path(data_root) / note_id
    n = _read_json(d / "content" / "note.json")
    if not isinstance(n, dict):
        return None

    urls = _read_json(d / "images" / "urls.json") or []
    if not urls:
        urls = pick(n, "image_urls", []) or []
    if not isinstance(urls, list):
        urls = [urls]

    files = [f for f in (d / "images").glob("*")
             if f.is_file() and f.suffix.lower() in
             (".jpg", ".jpeg", ".png", ".webp", ".heic", ".avif")
             and f.stat().st_size > 0]

    return Subject(
        subject_id=note_id,
        kind="note",
        text=str(pick(n, "desc", "") or ""),
        title=str(pick(n, "title", "") or ""),
        tags=tuple(split_tags(pick(n, "tags", []))),
        author=str(pick(n, "author", "") or ""),
        liked=to_int(pick(n, "liked", 0)),
        collected=to_int(pick(n, "collected", 0)),
        comment_count=to_int(pick(n, "comment_count", 0)),
        share=to_int(pick(n, "share", 0)),
        image_count=len(urls) or len(files),
        raw=n,
    )


def load_comment(data_root: Path, note_id: str,
                 row: dict[str, Any]) -> Subject | None:
    """从 ``comments.json`` 的一行构造 Subject。"""
    cid = str(row.get("id") or "").strip()
    text = str(row.get("content") or "").strip()
    if not cid or not text:
        return None
    ui = row.get("user_info") or {}
    return Subject(
        subject_id=cid,
        kind="comment",
        text=text,
        author=str(ui.get("nickname") or ui.get("nick_name") or ""),
        liked=to_int(row.get("like_count", 0)),
        parent_id=note_id,
        raw=row,
    )


def load_comments(data_root: Path, note_id: str) -> list[Subject]:
    arr = _read_json(Path(data_root) / note_id / "comments" / "comments.json")
    if not isinstance(arr, list):
        return []
    out = []
    for row in arr:
        if not isinstance(row, dict):
            continue
        s = load_comment(data_root, note_id, row)
        if s:
            out.append(s)
    return out


def iter_notes(data_root: Path) -> Iterator[Subject]:
    """遍历所有笔记。缺 content 的跳过（但计数时要能看到跳过数）。"""
    for nid in iter_note_ids(data_root):
        s = load_note(data_root, nid)
        if s:
            yield s


def iter_all_subjects(data_root: Path,
                      with_comments: bool = True) -> Iterator[Subject]:
    """遍历笔记 + 评论。这是打标的主入口。"""
    for n in iter_notes(data_root):
        yield n
        if with_comments:
            yield from load_comments(data_root, n.subject_id)


def comment_length_spread(data_root: Path, note_id: str) -> dict[str, Any]:
    """评论长度离散度 —— Layer 2「传播质量」信号。

    思路
    ----
    广告/刷评的评论区是**短句打卡区**（"求链接""多少钱""+1"），
    长度高度一致；真实讨论天然有长有短（"我用了三个月…（40字）"
    和 "好用" 混在一起）。所以**标准差比均值更可靠**：

        均值短 ≠ 可疑（活动贴评论区天然短）
        标准差小 = 可疑（要伪造整齐度得故意写长短不一的评论）

    实测（42篇 / 915 条，见 tools/validate_signals.py）
    ----------------------------------------------
    - 对人工判读 high vs 其他：**AUC 0.853**（三个候选信号里最强）
    - 对官方号vs 个人号：AUC 1.000
    - jev 分数 vs 评论均长 r=−0.470，本信号 r=−0.471（同一方向）

    为什么不进 ``total``
    --------------------
    AUC 衡量的是「区分能力」，不是「加权价值」。n=42 时任何新权重都是
    过拟合，而且会把已验证的 83.3% 一致率拖下水。所以它作为**独立的第二层**
    输出，不参与加权 —— 语义也不同：这是「传播质量」，不是「内容真实性」。

    只用评论**正文**，不依赖 ``create_time`` / ``ip_location`` /
    ``like_count`` —— 那三个字段匿名采集拿不到（见 docs/PLAN.md）。

    Returns
    -------
    dict
        ``n`` 评论数· ``mean`` 平均长度 · ``sd`` 标准差 ·
        ``spread_flag`` 是否整齐得不自然
    """
    arr = _read_json(Path(data_root) / note_id / "comments" / "comments.json")
    if not isinstance(arr, list):
        return {"n": 0, "mean": 0.0, "sd": None, "spread_flag": False}

    lens = [len(str(r.get("content") or "").strip())
            for r in arr if isinstance(r, dict)]
    lens = [x for x in lens if x > 0]
    n = len(lens)
    if n < SPREAD_MIN_COMMENTS:
        # 样本太少时标准差不可靠：2 条评论永远「整齐」，
        # 但那是数学必然不是人为整齐。
        return {"n": n, "mean": (sum(lens) / n if n else 0.0),
                "sd": None, "spread_flag": False}

    mean = sum(lens) / n
    var = sum((x - mean) ** 2 for x in lens) / n
    sd = var ** 0.5
    return {
        "n": n,
        "mean": round(mean, 2),
        "sd": round(sd, 2),
        "spread_flag": sd < SPREAD_SD_THRESHOLD,
    }


def note_ip_stats(data_root: Path, note_id: str) -> dict[str, float]:
    """评论地域集中度 —— 刷量信号（非 jev 维度，可选叠加）。

    思路：正常 UGC 的 IP 属地分布分散；集中刷评会出现
    单一省份占比异常高、地域熵异常低。
    """
    arr = _read_json(Path(data_root) / note_id / "comments" / "comments.json")
    if not isinstance(arr, list):
        return {"ip_n": 0.0, "ip_top1_ratio": 0.0, "ip_entropy": 0.0}

    ips = [str(x.get("ip_location") or "") for x in arr
           if isinstance(x, dict) and x.get("ip_location")]
    n = len(ips)
    if n < 5:      # 样本太少，统计量不可靠
        return {"ip_n": float(n), "ip_top1_ratio": 0.0, "ip_entropy": 0.0}

    from collections import Counter
    import math
    c = Counter(ips)
    top1 = c.most_common(1)[0][1] / n
    ent = -sum((v / n) * math.log(v / n + 1e-9) for v in c.values())
    # 熵按 ln(省份数) 归一化到 0..1，便于当特征用
    max_ent = math.log(len(c)) if len(c) > 1 else 1.0
    return {"ip_n": float(n), "ip_top1_ratio": round(top1, 4),
            "ip_entropy": round(ent / max_ent if max_ent else 0.0, 4)}
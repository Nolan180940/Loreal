"""SSR HTML → 结构化字段。

**为什么用正则不用 JSON**
------------------------
``window.__INITIAL_STATE__`` 是 JS 字面量，不是合法 JSON：
含 ``undefined``、``new Map([])``、单引号、尾随逗号。
实测 ``json.loads`` 直接 ``JSONDecodeError``。所以走正则抽字段。

**必须先反转义**
----------------
HTML 里斜杠被转义成 ``\\u002F``、引号成 ``\\"``。
不先反转义，图片 URL 抽出来是一堆乱码、``content`` 里的引号会截断。
这是最容易踩的坑。

评论解析的四次迭代（照抄 v4，别再踩）
------------------------------------
v1  一条正则 ``content ... [^}]{0,800} ... ipLocation/likeCount/time/user``
    → ❌ 中间隔着 atUsers / targetComment / subComments 三层嵌套，
      800 字不够，命中 0 条
v2  按 ``"user":{...}`` 切块，向左右 1200 字就近取
    → ⚠️ 命中 24 条，但 content 取到**上一条**的（错位）
v3  按 ``"user":{...}`` 切块，**只向后** 500 字取
    → ⚠️ 一级对了，楼中楼全错位 —— 因为两种评论的字段顺序不同
v4  **以 ``content`` 为锚点**，向前后就近取其余字段
    → ✅ 一级/楼中楼都正确

v4 可行的根本原因（SSR 实测字段顺序）
----------------------------------
一级评论::

    {"likeViewCount":..,"id":..,"noteId":..,"likeCount":..,"liked":..,
     "time":..,"user":{..},"commentType":..,"ipLocation":"..",
     "content":"..","atUsers":[..],"status":..,
     "subCommentCount":..,"subComments":[..]}

楼中楼::

    {"targetComment":{"id":..},"ipLocation":"..","likeViewCount":..,
     "id":..,"noteId":..,"content":"..","status":..,"time":..,
     "user":{..},"commentType":..,"atUsers":[..],"likeCount":..,
     "liked":..,"subCommentCount":0}

**user 相对于 content 的位置在两种评论里是相反的**，按 user 切必然错一半；
而 content 每条必有，其余字段都在它前后 400 字内，所以按 content 切最稳。

楼中楼主判据：content 之前 400 字内出现 ``"targetComment":{"``
（楼中楼引用父评论，一级评论没有这个字段）。
"""

from __future__ import annotations

import re
from typing import Any

#: content 锚点。每条评论必有该字段，且其余字段都落在它前后 400 字内。
CONTENT_RE = re.compile(r'"content":"((?:[^"\\]|\\.)*)"')

#: user 块整体。锚定 ``"user":{`` 并用 ``[^{}]*`` 抓完整块体，
#: 再在块体内分别取 userId / nickname。
#:
#: 为什么不能只匹配 userId —— SSR 里 ``atUsers:[{userId,nickname}]``
#: 也是同款结构，不锚 ``"user":{`` 会把被 @ 的用户当成评论者。
USER_RE = re.compile(r'"user":\{(?P<body>[^{}]*)\}')

#: 块体内取 userId / nickname（顺序无关）
_UID_RE = re.compile(r'"userId":"([0-9a-f]{24})"')
_NICK_RE = re.compile(r'"nickname":"((?:[^"\\]|\\.)*)"')

#: 向前/向后取字段的窗口
BEFORE_WINDOW = 400
AFTER_WINDOW = 400

#: 附属字段与 content 的最大配对距离（字符数）。
#: 一条评论的字段通常 < 300 字，但 user 块带 image URL 会拉到 250+；
#: 取 600 兼顾两者，又不至于跨到相邻评论。
MAX_PAIR_DIST = 600


def prepare(html: str) -> str:
    """只反转义斜杠，让 URL 与路径类字段可用。

    **故意不转 ``\\"``**：那会破坏 ``"content":"..."`` 的边界，
    让正则把值截断、把后续字段误配成内容（表现为 content 尾部
    带 ``赞0}]``、user 块匹配失败）。
    引号由各字段取出后单独 :func:`unescape` 处理。
    """
    return html.replace("\\u002F", "/").replace("\\/", "/")


def unescape(text: str) -> str:
    """还原单个字段值里的 JS 转义。取到值之后才调用。"""
    return (text.replace('\\"', '"')
                .replace("\\n", "\n")
                .replace("\\t", "\t"))



def _first(pattern: str, text: str, default: str = "") -> str:
    """取第一个匹配组，没有则返回 default。"""
    found = re.findall(pattern, text)
    return found[0] if found else default


def grab(html: str, field: str, default: str = "") -> str:
    """取 ``"field":"value"`` 或 ``"field":value``。"""
    m = re.search(r'"' + re.escape(field) + r'"\s*:\s*"?([^,"}]+)', html)
    return m.group(1).strip() if m else default


def _author_ip(h: str) -> str:
    """作者的 IP 属地。

    不能直接 ``grab(h, "ipLocation")`` —— 那会拿到**第一条评论**的 IP。
    做法：先定位第一个 userId（就是作者），再在其后 600 字内取。
    """
    m = re.search(r'"userId":"([0-9a-f]{24})"', h)
    if not m:
        return ""
    window = h[m.end():m.end() + 600]
    ip = re.search(r'"ipLocation":"([^"]*)"', window)
    return ip.group(1) if ip else ""


def parse_note(html: str) -> dict[str, Any]:
    """note 级字段 + 图片清单。"""
    h = prepare(html)

    # 标题可能为空（视频帖），退回正文前 30 字
    title = grab(h, "title")
    desc_m = re.search(r'"desc":"((?:[^"\\]|\\.)*)"', h)
    desc = unescape(desc_m.group(1)) if desc_m else ""

    # 图片：字段叫 url（PC SSR 里叫 urlDefault，手机 UA 这份只有 url）
    images: list[str] = []
    for u in re.findall(r'"url":"(https?://[^"]*sns-webpic[^"]+)"', h):
        if u not in images:
            images.append(u)

    return {
        "note_id": grab(h, "noteId"),
        "title": title or (desc[:30] + "…" if len(desc) > 30 else desc),
        "desc": desc,
        "author": grab(h, "nickName") or grab(h, "nickname"),
        "author_id": grab(h, "userId"),
        "ip_location": _author_ip(h),
        "liked": grab(h, "likedCount"),
        "collected": grab(h, "collectedCount"),
        "comment_count": grab(h, "commentCount"),
        "comment_count_l1": grab(h, "commentCountL1") or "0",
        "share": grab(h, "shareCount"),
        "time_ms": grab(h, "time", "0"),
        "tags": [t for t in re.findall(r'"name":"([^"]{1,30})"', h)[:20]],
        "images": images,
    }


def parse_comments(html: str) -> list[dict[str, Any]]:
    """评论列表（一级 + 内联楼中楼）。

    实现：**以 content 为锚，附属字段按绝对距离最近配对**。

    为什么不能按固定方向取字段
    --------------------------
    SSR 里一级评论与楼中楼的字段顺序**相反**（实测）：

    * 一级  ：``... user{}, ipLocation, content ...``
    * 楼中楼：``content ... ipLocation, user{} ...``

    固定"只向后取"会让楼中楼取不到自己的字段；
    固定"先后取再后取"会取到相邻评论的（错位）。

    唯一不依赖顺序的做法：把 content / user / ipLocation /
    likeCount / time 全部抽成 ``(位置, 值)``，
    再让每个附属值配给**绝对距离最近**的那个 content。
    """
    # 快路径：括号配对 + json.loads，完全准确定位字段。
    # SSR 里一级评论的 user 与 content 隔着整个 subComments 数组
    # （实测 1000~1500 字），正则的"最近距离配对"在这种跨度下必然错配。
    from .ssr_json import flatten, parse_comments_json
    fast = parse_comments_json(html)
    if fast is not None:
        return flatten(fast)

    # 慢路径：正则 + 最近距离配对（SSR 结构异常时的保底）
    h = prepare(html)
    # 只在 commentData 容器里找，避免把正文等其他 content 当评论
    start = h.find('"commentData"')
    scope = h[start:] if start >= 0 else h

    contents = [(m.start(), m.end(), unescape(m.group(1)))
                for m in CONTENT_RE.finditer(scope)]
    if not contents:
        return []

    # 附属锚点：(位置, 值)
    users = []
    for m in USER_RE.finditer(scope):
        body = m.group("body")
        uid_m = _UID_RE.search(body)
        if not uid_m:
            continue                      # 形态1：块体无 userId，跳过
        nick_m = _NICK_RE.search(body)
        users.append((
            m.start(),
            uid_m.group(1),
            unescape(nick_m.group(1)) if nick_m else "",
        ))
    ips = [(m.start(), m.group(1))
           for m in re.finditer(r'"ipLocation":"([^"]*)"', scope)]
    likes = [(m.start(), m.group(1).strip('"'))
             for m in re.finditer(r'"likeCount":([^,]+)', scope)]
    times = [(m.start(), m.group(1))
             for m in re.finditer(r'"time":(\d+)', scope)]

    def attach(pairs):
        """把若干 (位置, 值) 各配给最近的 content，返回 {content_idx: 值}。"""
        out: dict[int, str] = {}
        for pos, val in pairs:
            best, best_d = None, MAX_PAIR_DIST
            for idx, (cstart, _end, _txt) in enumerate(contents):
                d = abs(pos - cstart)
                if d < best_d:
                    best, best_d = idx, d
            if best is not None and best not in out:
                out[best] = val
        return out

    uid_map = attach([(p, u) for p, u, _n in users])
    nick_map = attach([(p, n) for p, _u, n in users])
    ip_map = attach(ips)
    like_map = attach(likes)
    time_map = attach(times)

    rows: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for idx, (cstart, cend, content) in enumerate(contents):
        if not content.strip():
            continue

        before = scope[max(0, cstart - BEFORE_WINDOW):cstart]
        after = scope[cend:cend + AFTER_WINDOW]
        # 楼中楼主判据：content 之前有 "targetComment":{"（引用父评论）
        is_reply = '"targetComment":{' in before
        is_author = ('"is_author"' in before[-150:]
                     or '"is_author"' in after[:150])

        uid = uid_map.get(idx, "")
        key = (uid, content[:40])
        if key in seen:
            continue
        seen.add(key)

        t = time_map.get(idx, "")
        rows.append({
            "user_id": uid,
            "nickname": nick_map.get(idx, ""),
            "content": content,
            "ip_location": ip_map.get(idx, ""),
            "like_count": like_map.get(idx, "0") or "0",
            "time": int(t) if t.isdigit() else 0,
            "is_author": is_author,
            "_is_reply": is_reply,
        })

    return rows


def parse(html: str) -> dict[str, Any]:
    """完整解析：note + comments + 完整性标记。"""
    note = parse_note(html)
    comments = parse_comments(html)

    got = len(comments)
    declared = 0
    raw_declared = note.get("comment_count") or ""
    if raw_declared.isdigit():
        declared = int(raw_declared)

    return {
        "note": note,
        "comments": comments,
        "declared": declared,
        "got": got,
        # got < declared 说明首屏没给全（翻页未实现）
        "complete": declared == 0 or got >= declared,
    }


class EmptyDataError(RuntimeError):
    """HTML 拿到了，但关键字段全空 —— 通常意味着 token 失效/被降级。"""


def validate(parsed: dict[str, Any]) -> None:
    """确认真的拿到数据，而不是一个空壳页面。"""
    note = parsed.get("note") or {}
    if not note.get("liked") and not note.get("desc"):
        raise EmptyDataError(
            "SSR 未渲染出数据：liked 与 desc 均为空，token 可能失效")
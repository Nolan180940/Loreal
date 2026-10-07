"""实测：匿名（无 cookie）到底能拿到哪些"数据字段"，哪些拿不到。

只探测，不写库。输出 out/anonymous_capability.md。
关键区分：
  A. 笔记层互动指标  liked / collected / comment_count / share_count
  B. 评论层指标      like_count / create_time / ip_location / sub_comment_count
"""

import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from jev_guard.core.config import load_config  # noqa: E402
from jev_guard.extractors.reader import iter_note_ids, load_note  # noqa: E402
from jev_guard.providers.jev import BROWSER_UA  # noqa: E402

cfg = load_config()
L: list[str] = []


def emit(s: str = "") -> None:
    L.append(s)


# ---------------------------------------------------------------- 1. 已有离线数据盘点
emit("## 1. 离线数据盘点：哪些笔记有笔记层互动指标")
emit()
have = {"liked": [], "collected": [], "comment_count": [], "share_count": []}
for nid in iter_note_ids(cfg.data_root):
    p = cfg.data_root / nid / "content" / "note.json"
    if not p.is_file():
        continue
    try:
        n = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        continue
    if not isinstance(n, dict):
        continue
    for k in have:
        for cand in (k, {"share_count": "分享数量", "comment_count": "评论数量",
                         "collected": "收藏数量", "liked": "点赞数量"}[k]):
            v = n.get(cand)
            if v not in (None, "", 0, "0", -1):
                have[k].append(nid)
                break

total = sum(1 for _ in iter_note_ids(cfg.data_root))
emit("| 字段 | 有值笔记数 | 占比 |")
emit("| --- | ---: | ---: |")
for k, v in have.items():
    emit(f"| {k} | {len(v)}/{total} | {len(v) / total * 100:.0f}% |")
emit()

# ---------------------------------------------------------------- 2. 匿名实测
emit("## 2. 匿名实测（不带任何 cookie）")
emit()
emit("用 B 组里点赞最高的一篇做探测 —— 它是纯匿名 SSR 采集的。")
emit()

cands = []
for nid in iter_note_ids(cfg.data_root):
    p = cfg.data_root / nid / "content" / "note.json"
    if not p.is_file():
        continue
    try:
        n = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        continue
    if isinstance(n, dict) and n.get("liked"):
        cands.append((int(n.get("liked") or 0), nid))
cands.sort(reverse=True)

TOKENS = {
    "6ab6a30e": "ABYix_3oM91DsEE9SHDs2AggR5PopmlYicNukXMl6QB3Y=",
    "6abb030f": "ABtpvw0rA6einjRJvJV00VfLIsjWdqT6m11_7FXCJBnVs=",
    "693abce3": "ABcIzAIpURB-vkVd36gxOmzIuvPv7bQrKNjuk244UUUeA=",
}

emit("### 2.1 匿名请求笔记详情页 HTML，看 __INITIAL_STATE__ 是否含互动指标")
emit()
emit("| note | HTTP | 含 noteDetailMap | liked | collected | commentCount | shareCount |")
emit("| --- | --- | --- | ---: | ---: | ---: | ---: |")

probe_ok = 0
for _liked, nid in cands[:3]:
    tok = TOKENS.get(nid[:8])
    if not tok:
        continue
    url = (f"https://www.xiaohongshu.com/explore/{nid}"
           f"?xsec_token={tok}&xsec_source=pc_search")
    req = urllib.request.Request(url, headers={
        "User-Agent": BROWSER_UA,
        "Accept": "text/html,application/xhtml+xml",
        "Accept-Language": "zh-CN,zh;q=0.9",
    })
    try:
        with urllib.request.urlopen(req, timeout=25) as r:
            html = r.read().decode("utf-8", "replace")
            code = r.status
    except urllib.error.HTTPError as e:
        html, code = "", e.code
    except Exception as e:
        emit(f"| `{nid[:8]}` | ERR {type(e).__name__} | - | - | - | - | - |")
        continue

    has_map = "__INITIAL_STATE__" in html and "noteDetailMap" in html
    def grab(key: str) -> str:
        i = html.find(f'"{key}"')
        if i < 0:
            return "-"
        seg = html[i:i + 60]
        import re
        m = re.search(r'"\s*(?:' + key + r'")\s*:\s*"?([0-9]+)', seg)
        return m.group(1) if m else "-"
    emit(f"| `{nid[:8]}` | {code} | {'Y' if has_map else 'N'} | "
         f"{grab('likedCount')} | {grab('collectedCount')} | "
         f"{grab('commentCount')} | {grab('shareCount')} |")
    if code == 200 and has_map:
        probe_ok += 1

emit()
emit(f"**匿名可读详情页：{probe_ok}/3**")
emit()

# ---------------------------------------------------------------- 3. 评论 API 匿名
emit("## 3. 评论 API 匿名实测（comment/page）")
emit()
emit("这是关键一环：匿名能不能拿到带 like_count / create_time / ip_location 的评论。")
emit()
emit("| note | HTTP | 返回条数 | 带create_time | 带like_count | 带ip_location |")
emit("| --- | --- | ---: | ---: | ---: | ---: |")
for _liked, nid in cands[:3]:
    tok = TOKENS.get(nid[:8])
    if not tok:
        continue
    body = json.dumps({
        "note_id": nid, "cursor": "", "top_comment_id": "",
        "image_formats": ["jpg", "webp", "avif"], "xsec_token": tok,
    }).encode()
    url = "https://www.xiaohongshu.com/api/sns/web/v2/comment/page"
    req = urllib.request.Request(url, data=body, method="POST", headers={
        "User-Agent": BROWSER_UA,
        "Content-Type": "application/json;charset=UTF-8",
        "Accept": "application/json",
        "Referer": f"https://www.xiaohongshu.com/explore/{nid}",
    })
    try:
        with urllib.request.urlopen(req, timeout=25) as r:
            j = json.loads(r.read().decode("utf-8"))
            code = r.status
    except urllib.error.HTTPError as e:
        emit(f"| `{nid[:8]}` | **{e.code}** | - | - | - | - |")
        continue
    except Exception as e:
        emit(f"| `{nid[:8]}` | ERR | - | - | - | - |")
        continue
    if not j.get("success"):
        emit(f"| `{nid[:8]}` | {code} fail={j.get('code')} | - | - | - | - |")
        continue
    lst = (j.get("data") or {}).get("comments") or []
    nt = sum(1 for c in lst if c.get("create_time"))
    nl = sum(1 for c in lst if c.get("like_count") not in (None, "", "0"))
    ni = sum(1 for c in lst if c.get("ip_location"))
    emit(f"| `{nid[:8]}` | {code} | {len(lst)} | {nt} | {nl} | {ni} |")

emit()
emit("> 461 = 风控拦截。注释里已记录「匿名状态下第 2 页必 461」。")
emit()

Path("out/anonymous_capability.md").write_text("\n".join(L), encoding="utf-8")
print("written: out/anonymous_capability.md")
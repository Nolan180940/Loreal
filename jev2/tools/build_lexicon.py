"""生成品牌词表 ``jev2/src/jev2/signals/_lexicon.py``。

为什么要词表
------------
``brand_mention_ratio`` 要看「评论里有没有念产品/品牌名」，
需要一个「这篇在讲什么」的词表。最自然的来源是笔记自己的 ``tags`` ——
但实测 tags 解析会失败（43 篇里 7 篇只剩假标签「笔记」），
那时信号只能报 missing。

所以补一个**跨语料词池**兜底：把全部笔记的 tags 收集起来，
再看哪些词出现在**本篇的标题/正文**里。这样 tags 解析失败的篇
也能认出品牌（例：tags=[] 但标题含「珂润面霜」→ 词表=[珂润, 珂润面霜]）。

覆盖率实测（40 篇标注）：只用 tags 30 篇 → 加词池 37 篇。
AUC 基本持平（0.583 → 0.589），所以这是**为了覆盖率**，不是刷分。

词池是**词表不是阈值** —— 没有拟合任何判定边界，
所以不会造成「在考卷上改答案」。但新增品牌后应重新生成。

用法
----
    python jev2/tools/build_lexicon.py          # 重新生成
    python jev2/tools/build_lexicon.py --check  # 只检查是否过期（CI 用）
"""
from __future__ import annotations

import argparse
import collections
import pathlib
import sys

_HERE = pathlib.Path(__file__).resolve()
_ROOT = _HERE.parents[2]          # <repo>
sys.path.insert(0, str(_ROOT / "jev2" / "src"))

from jev2.loader import load_all  # noqa: E402

OUT = _ROOT / "jev2" / "src" / "jev2" / "signals" / "_lexicon.py"

#: 单字词会命中一切（「水」「霜」），噪声太大。
_MIN_LEN = 2

#: 假标签：xhs-cli 的 tags 正则会把界面文案「笔记」当成标签。
_FAKE = {"笔记"}

HEADER = '''"""跨语料词池 —— **自动生成，不要手改**。

由 ``jev2/tools/build_lexicon.py`` 从 ``data/*/notes.json`` 的 tags 汇总。
用途见 ``brand_mention_ratio``：给「这篇在讲什么品牌/产品」兜底一个词表。

为什么需要它：实测 43 篇里有 7 篇的 tags 解析失败（只剩假标签「笔记」），
只用本篇 tags 会让那些篇报 missing。加上词池后覆盖率 30/40 → 37/40。

重新生成：``python jev2/tools/build_lexicon.py``
"""

from __future__ import annotations

#: 按出现篇数降序（同频按字典序）。来源：{n_notes} 篇笔记的 tags。
BRAND_WORDS: tuple[str, ...] = (
{body})
'''


def collect(data_root: pathlib.Path) -> tuple[collections.Counter, int]:
    notes, _bad = load_all(data_root)
    pool: collections.Counter = collections.Counter()
    for n in notes:
        for t in n.tags:
            s = t.strip()
            if len(s) >= _MIN_LEN and s not in _FAKE:
                pool[s] += 1
    return pool, len(notes)


def render(pool: collections.Counter, n_notes: int) -> str:
    items = sorted(pool.items(), key=lambda kv: (-kv[1], kv[0]))
    body = "\n".join(f'    "{w}",' for w, _c in items)
    return HEADER.format(n_notes=n_notes, body=body)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="生成品牌词表")
    ap.add_argument("--data", default=str(_ROOT / "data"))
    ap.add_argument("--check", action="store_true",
                    help="只检查是否过期，不写文件（过期退出码 1）")
    args = ap.parse_args(argv)

    pool, n_notes = collect(pathlib.Path(args.data))
    text = render(pool, n_notes)

    if args.check:
        if not OUT.is_file():
            print(f"[X] {OUT} 不存在")
            return 1
        if OUT.read_text(encoding="utf-8") != text:
            print(f"[X] {OUT} 已过期，跑 python jev2/tools/build_lexicon.py")
            return 1
        print(f"[ok] 词表是最新的（{len(pool)} 词）")
        return 0

    OUT.write_text(text, encoding="utf-8")
    print(f"[saved] {OUT}")
    print(f"        {len(pool)} 词 · 来自 {n_notes} 篇笔记")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

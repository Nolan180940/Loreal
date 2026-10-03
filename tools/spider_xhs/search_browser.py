# -*- coding: utf-8 -*-
"""用 Playwright 采集小红书「美妆避雷/踩雷」类笔记的搜索结果与评论。

复用已登录的浏览器实例，不需要 web_session。
"""

from __future__ import annotations

import json
import re
import time
from pathlib import Path

OUT = Path("D:/LOreal-ai/data/search")
OUT.mkdir(parents=True, exist_ok=True)

KEYWORDS = ["美妆避雷", "护肤品踩雷", "面霜翻车", "美妆智商税"]


def clean(t: str) -> str:
    return re.sub(r"\s+", " ", t or "").strip()


def extract_cards(page) -> list[dict]:
    """从搜索结果页提取笔记卡片。"""
    return page.evaluate("""() => {
      const out = [];
      const secs = document.querySelectorAll('section.note-item, div.note-item');
      for (const s of secs) {
        const a = s.querySelector('a[href*="/search_result/"], a[href*="/explore/"]');
        const title = s.querySelector('.title, .footer .title, span');
        const author = s.querySelector('.author .name, .author');
        const like = s.querySelector('.like-wrapper .count, .count');
        if (!a) continue;
        out.push({
          href: a.getAttribute('href') || '',
          title: (title ? title.innerText : '').trim(),
          author: (author ? author.innerText : '').trim(),
          like: (like ? like.innerText : '').trim(),
        });
      }
      return out;
    }""")


def main() -> int:
    from playwright.sync_api import sync_playwright

    all_rows = []
    with sync_playwright() as p:
        browser = p.chromium.connect_over_cdp("http://127.0.0.1:9222")
        ctx = browser.contexts[0] if browser.contexts else browser.new_context()
        page = ctx.new_page()

        for kw in KEYWORDS:
            url = ("https://www.xiaohongshu.com/search_result"
                   f"/?keyword={kw}&type=51")
            print(f"\n=== {kw} ===")
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=45000)
                page.wait_for_timeout(4000)
                page.mouse.wheel(0, 3000)
                page.wait_for_timeout(2500)
                cards = extract_cards(page)
            except Exception as e:
                print(f"  失败: {type(e).__name__}: {e}")
                continue

            print(f"  抓到 {len(cards)} 条")
            for c in cards[:20]:
                c["keyword"] = kw
                all_rows.append(c)
                print(f"  - [{c['like']:>5}] {c['title'][:30]}  @{c['author'][:12]}")
            time.sleep(2)

        page.close()

    path = OUT / "search_results.json"
    path.write_text(json.dumps(all_rows, ensure_ascii=False, indent=2),
                    encoding="utf-8")
    print(f"\n[OK] 共 {len(all_rows)} 条 -> {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

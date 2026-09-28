# 一键集成命令

`xhs_cli.py` 把「采集笔记 + 下载图片 + 抓全量评论」串成一条命令。

## 用法

**首次使用**（干净克隆后必跑一次，重建 `tools/.venv`）：

```powershell
python tools\setup_env.py
```

它会自动建 venv、装依赖、装 Node.js 检查、并验证签名模块可用。

**日常使用**：

```powershell
cd D:\LOreal-ai\tools\spider_xhs
..\.venv\Scripts\python.exe xhs_cli.py "https://xhslink.cn/o/6wvIYWl9oLU"
```

输出：

```
[1/4] cookie OK（590 字符，web_session=有）
[2/4] 短链解析: note_id = 6wvIYWl9oLU
[3/4] 抓取笔记（正文 / 标签 / 图片）...
    标题: 新版白绷带太猛了...油皮脸也嘭弹到爆
    正文: 735 字 | 标签: 28 字
    互动: 赞766 藏209 评34 转21
    图片: 6 张
[4/4] 抓取评论（全部，含楼中楼）...
    一级 20 + 楼中楼 14 = 34 条
[OK] 全部产物在 D:\LOreal-ai\data\xhs_demo
```

## 参数

| 参数 | 作用 |
|---|---|
| `-o, --out` | 输出目录（默认 `data/xhs`） |
| `--no-images` | 跳过图片下载（快） |
| `--no-comments` | 跳过评论抓取 |
| `--dry-run` | 只解析链接，不发请求 |

## 产物结构

```
<out>/
├─ note/
│   ├─ note.md          标题 + 正文 + 标签 + 互动（人可直接读）
│   ├─ note.json        完整结构化
│   └─ image_urls.json  图片 URL 列表
├─ comments/
│   ├─ comments.json       全部（一级 + 楼中楼，楼中楼带 _is_reply 标记）
│   ├─ comments_top.json   仅一级评论
│   ├─ comments_replies.json 仅楼中楼
│   └─ comments.txt        人可读，楼中楼缩进挂在对应一级下
└─ Download/
    ├─ *.jpeg           图片
    └─ ExploreData.db   作品历史（SQLite）
```

## 实现要点

| 问题 | 处理 |
|---|---|
| 短链 ID ≠ 真实 note_id | 抓完笔记后用 `作品ID` 覆盖 |
| `xsec_token` 不在图片 URL 里 | 从 `作品链接` 字段正则提取 |
| 评论接口 406 | `bootstrap()` 不可省（user_id → `xy-direction` 签名头） |
| 只拿到 20 条而非 34 条 | 笔记页评论数 = 一级 + 楼中楼；需显式展开 `sub_comments` |
| 中文输出乱码 | 全部落盘 UTF-8，控制台只打摘要 |

## 前提

- 用 `tools\.venv` 的解释器（需 `curl_cffi` / `PyExecJS` / `loguru`）
- 系统装 Node.js（`node --version` 有输出）
- 项目根 `.env` 里有 `XHS_COOKIE`（含 `web_session`）

> `xsec_token` 有时效，**用刚从小红书分享出来的链接**成功率最高。

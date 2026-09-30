# Loreal · 小红书笔记内容采集

输入一个小红书链接，一条命令导出**正文 / 标签 / 图片 / 全量评论（含楼中楼）**。

```
python tools\spider_xhs\xhs_cli.py "https://www.xiaohongshu.com/discovery/item/xxxx"
```

---

## 1. 环境准备（首次使用，干净克隆后跑一次）

```powershell
python tools\setup_env.py
```

它会自动完成：

1. 检查 Node.js（缺失会报错并给下载链接；签名算法依赖它）
2. 创建 `tools\.venv`
3. 安装依赖
4. **自检**：真实 import 一次签名模块，确认可跑
5. 检查 cookie 是否已配置

> Windows 上若提示权限不足，用管理员身份运行 PowerShell。

## 2. 配置 Cookie

```powershell
copy .env.example .env
```

编辑 `.env`，填入 `XHS_COOKIE=...`。获取方式：

1. 浏览器**登录**小红书 → 打开 `https://www.xiaohongshu.com/explore`
2. `F12` → **Application** 标签 → Storage → Cookies → `https://www.xiaohongshu.com`
3. 找到 **`web_session`**，双击 Value 复制
4. 把 `web_session=xxx` 追加到 cookie 串末尾

也可用系统环境变量 `XHS_COOKIE` 覆盖（优先级更高）。

> `.env` 已在 `.gitignore` 中，不会进仓库。

## 3. 日常使用

```powershell
cd tools\spider_xhs
..\.venv\Scripts\python.exe xhs_cli.py "小红书链接"
```

**输出示例：**

```
[1/4] cookie OK（590 字符，web_session=有）
[2/4] 短链解析: note_id = 6ab7946f...
[3/4] 抓取笔记（正文 / 标签 / 图片）...
    标题: 如果出道能复刻当年1d的盛况吗
    正文: 19 字 | 标签: 7 字
    互动: 赞1362 藏141 评117 转367
    图片: 3 张
[4/4] 抓取评论（全部，含楼中楼）...
    楼中楼补全 31 条（9 次请求）
    一级 68 + 楼中楼 49 = 117 条（笔记显示 117，已对齐）
[OK] 全部产物在 D:\LOreal-ai\data\xhs
```

### 参数

| 参数 | 作用 |
|---|---|
| `-o, --out` | 输出目录（默认 `data/xhs`） |
| `--no-images` | 跳过图片下载（快很多） |
| `--no-comments` | 跳过评论抓取 |
| `--dry-run` | 只解析链接，不发请求 |

## 4. 产物结构

```
<输出目录>/
├─ note/
│   ├─ note.md          标题 + 正文 + 标签 + 互动数据（人可直接读）
│   ├─ note.json        完整结构化数据
│   └─ image_urls.json  图片 URL 列表
├─ comments/
│   ├─ comments.txt        全部评论，楼中楼缩进挂在对应一级下
│   ├─ comments.json       结构化（楼中楼带 _is_reply / _parent_id）
│   ├─ comments_top.json   仅一级评论
│   ├─ comments_replies.json 仅楼中楼
│   └─ card.json           抓取自检（是否与笔记页数字对齐）
└─ images/  Download/   图片文件 + 作品数据库（SQLite）
```

`comments/card.json` 是**抓取自检报告**，字段：

| 字段 | 含义 |
|---|---|
| `expected` | 笔记页显示的评论数 |
| `top_level` / `replies` | 实际抓到的一级 / 楼中楼数 |
| `complete` | 是否完全对齐 |
| `thread_gaps` | 仍未抓全的楼明细（不静默丢数据） |

## 5. 工作原理

```
链接
 ├─ XHS-Downloader ──→ 抓 HTML 页面 → 正文 / 标签 / 图片
 └─ Spider_XHS ──────→ 签名 API 调用 → 一级评论 + 楼中楼
```

两个上游项目都放在 `tools/` 下（已内置，非 submodule）：

| 目录 | 来源 | 作用 |
|---|---|---|
| `tools/source/`、`tools/main.py` | [JoeanAmier/XHS-Downloader](https://github.com/JoeanAmier/XHS-Downloader) | 笔记正文、标签、图片 |
| `tools/spider_xhs/xhs_utils/`、`apis/` | [cv-cat/Spider_XHS](https://github.com/cv-cat/Spider_XHS) | 小红书 web 签名、评论接口 |

**我们自己的代码只有 4 个文件：**

| 文件 | 作用 |
|---|---|
| `tools/spider_xhs/xhs_cli.py` | 一键命令入口 |
| `tools/spider_xhs/thread_fetcher.py` | 楼中楼完整抓取（翻页 + 去重合并 + 自检） |
| `tools/spider_xhs/fetch_comments.py` | 单独抓评论 |
| `tools/setup_env.py`、`tools/read_my_cookie.py` | 环境与 cookie |

### 关键实现要点

| 问题 | 处理 |
|---|---|
| 短链 ID ≠ 真实 note_id | 抓完笔记后用返回的 `作品ID` 覆盖 |
| `xsec_token` 不在图片 URL 里 | 从 `作品链接` 字段正则提取 |
| 评论接口返回 406 | 必须先 `bootstrap()` 拿 user_id（签名头 `xy-direction` 依赖它） |
| 只抓到一级评论 | 笔记页评论数 = 一级 + 楼中楼；楼中楼需显式翻 `sub/page` 并按 id 去重合并 |
| 中文输出乱码 | 全部落盘 UTF-8，控制台只打摘要 |

## 6. 已知限制

| 限制 | 说明 |
|---|---|
| **拿不到原图** | 下载的是平台转码版（URL 含 `imageView2` 参数），传感器噪声与 EXIF 已被剥离。像素级篡改取证不适用 |
| **楼中楼每页仅 5 条** | 已实现翻页（上限 30 页/楼），实测 117 条笔记可完全对齐 |
| **`xsec_token` 有时效** | 作品链接带日期，**请用刚从小红书分享出来的链接**，旧链接会被拒 |
| **风控** | 已内置 0.8–1.2s 请求延时。官方文档警告高频请求会触发风控甚至封号，请勿批量高频抓取 |
| **楼中楼回复内容** | 只保证抓到 `sub_comment_count` 标注的条数；被删除/折叠的评论无法获取 |

## 7. 合规

仅用于公开可见内容的采集与分析。请遵守平台服务条款与当地法规，不得用于规模化抓取、用户数据画像或商业竞争用途。

## 8. 历史代码归档

本仓库早期做过一套**图像取证流水线**（`forensic/`：像素级篡改检测、证据卡生成、合成数据集），已从 `main` 移除，完整保留在归档分支：

```powershell
git checkout archive/full              # 切到归档分支查看
git checkout archive/full -- forensic/  # 只取回 forensic 目录
```

标签 `archive/pre-reset` 指向重置前的最后一个提交（`0aeb834`）。

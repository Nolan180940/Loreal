# xhs-cli

匿名免登录采集小红书笔记（文案 / 图片 / 首批评论）。

## 安装

```powershell
D:\LOreal-ai\.venv\Scripts\python.exe -m pip install -e .
D:\LOreal-ai\.venv\Scripts\python.exe -m playwright install chromium
```

## 用法

```powershell
# 单个分享链接
xhs "https://www.xiaohongshu.com/explore/<id>?...&xsec_token=..."

# 手机短链（自动展开拿新鲜 token）
xhs "https://xhslink.cn/o/xxxxxxxx"

# 链接清单（每行一个，# 开头为注释）
xhs --input urls.txt

# 用本机 Chrome（TLS 指纹更像真人）
xhs --engine chrome --input urls.txt

# 审计已有数据
xhs --audit-only
```

常用参数：

| 参数 | 说明 |
|---|---|
| `--out DIR` | 输出根目录，默认 `xhs_data/` |
| `--engine chrome` | 用本机 Chrome 代替自带 Chromium |
| `--skip-images` | 不下载图片 |
| `--proxy URL` | 走代理 |
| `--audit-only` | 只做完整性审计 |

## 输出结构

```
xhs_data/<note_id>/
  content/note.json      标题/正文/互动数/作者/标签
  content/note.md        人读版
  images/urls.json       图片 URL 清单
  images/01.jpg ...      下载的图片（序号与 urls.json 对齐）
  comments/comments.json 扁平列表：一级 + 楼中楼（楼中楼带 _is_reply）
  comments/card.json     统计卡片，含 partial 标记
```

## 设计约束

### 匿名硬约束

`anonymity.py` 在每次请求前断言不出现 `cookie` / `web_session` / `id_token`
等登录态字段。工程**不读取**任何 cookie 或 `.env` 文件。

### 不美化数据

抓不到首批评论时，`card.json` 里会标 `"partial": true` 并记录缺口数，
不会伪装成完整数据。审计报告同样如实展示。

## 已验证的平台限制（2026-10-03 实测）

这些是实测结论，不是推测，改动前请先读：

| 能力 | 匿名状态 |
|---|---|
| 文案 / 互动数 / 图片 | ✅ 可得（需有效 `xsec_token`） |
| 首批评论（10 条）+ inline 楼中楼 | ✅ 可得 |
| 评论翻页（第 2 页起） | ❌ 每会话仅 1 次请求，第 2 次必 461 |
| 跨会话翻页 | ❌ cursor 与签发会话绑定，换会话失效 |
| 楼中楼补全（`comment/sub/page`） | ❌ 匿名首请求即 461 |
| 无 token 的裸详情页 | ❌ 302 跳登录，`noteDetailMap` 键被渲染成 `"undefined"` |
| 搜索页 / 搜索 API | ❌ 登录墙 / `-104 无权限` |
| 发现页 API（Python） | ❌ `success:true` 但 `items:[]`（软限流） |
| 手机短链展开 | ⚠️ 偶发成功，但平台对短链解析有独立频控，频繁请求会跳登录 |
| stealth 反检测 | ❌ JS 指纹伪装成功但仍失败（TLS 指纹被识别） |

**结论**：全量评论（含楼中楼）在纯匿名条件下不可实现，这是平台侧策略。
本工具稳定交付的是「文案 + 图片 + 首批评论」。

## 已知失败分类

`comments/card.json` 与 CLI 日志会给出精确原因，便于区分问题：

| kind | 含义 |
|---|---|
| `token_expired` | 被重定向到登录页，token 已失效（有效期约数小时） |
| `token_rejected` | `noteDetailMap` 键为 `undefined`，token 未被接受 |
| `empty_note` | `noteDetailMap` 为空 |
| `not_found` | 404，链接错误或 token 失效 |
| `no_state` | 渲染超时，`__INITIAL_STATE__` 未出现 |
| `network` | 网络故障（已重试） |

## 断点续跑

已有完整数据的笔记会被跳过（`[skip]`），中途失败重跑不会重复劳动。
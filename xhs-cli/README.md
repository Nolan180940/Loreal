# xhs-cli

匿名免登录采集小红书笔记：**文案 / 图片 / 评论**。

核心链路不依赖浏览器 —— 只用 Python 标准库 `urllib`，
不需要 Playwright、不需要 Chromium、不需要 cookie、不需要登录。

---

## 安装

```powershell
cd xhs-cli
D:\LOreal-ai\.venv\Scripts\python.exe -m pip install -e . --no-deps
```

`--no-deps` 是有意的：HTTP 链路只用标准库。
（`pyproject.toml` 里声明的 `playwright` / `curl_cffi` 只服务已废弃的浏览器链路。）

---

## Quick Start

```powershell
# 1. 解析一个链接，人读输出
python -m xhs_cli parse "https://xhslink.cn/o/9yWznlCm2pp"

# 2. 落盘成 JSON（GBK 控制台看中文会乱码，读文件最省事）
python -m xhs_cli parse "https://xhslink.cn/o/9yWznlCm2pp" --save note.json

# 3. 只要 JSON，打到屏幕
python -m xhs_cli parse "https://xhslink.cn/o/9yWznlCm2pp" --json
```

支持四种链接写法：

| 形态 | 例子 |
|---|---|
| 手机短链（推荐） | `https://xhslink.cn/o/9yWznlCm2pp` |
| 长链带 token | `https://www.xiaohongshu.com/explore/<24位id>?xsec_token=...` |
| 长链无 token | `https://www.xiaohongshu.com/explore/<24位id>` |
| 缺协议头 | `www.xiaohongshu.com/explore/<24位id>` |

> Windows 控制台乱码是 PowerShell 按 GBK 解码 UTF-8 导致的，数据本身没问题。
> 加 `--save` 读文件，或先执行 `chcp 65001`。

---

## 架构

```
xhs-cli/src/xhs_cli/
  core/                ★ HTTP 直连链路（在用）
    link.py            链接归一化：短链/长链/缺协议 → LinkRef
    fetch.py           urllib 直连 + 手机 UA
    ssr.py             HTML → 结构化字段
    ssr_json.py        括号配对提取嵌套数组（评论 / tagList）
    service.py         parse_link()：重试 + 换 token
  storage/layout.py    目录化落盘布局
  cli.py               命令行入口
  page.py              浏览器链路（已废弃，见下）
  extractors/          浏览器链路的字段归一化
  share.py             短链展开（浏览器版）
  audit.py             完整性审计
```

### 两条链路

```mermaid
graph TB
    subgraph HTTP["core/ — HTTP 直连 ✅ 在用"]
        A1[链接] --> A2[link.normalize]
        A2 --> A3[fetch.expand<br/>urllib 取新鲜 xsec_token]
        A3 --> A4[fetch.fetch_html<br/>手机 UA 取详情页]
        A4 --> A5[ssr.parse]
        A5 --> A6[note / images / comments]
    end
    subgraph PW["page.py — 浏览器 ❌ 已废弃"]
        B1[链接] --> B2[启动 Chromium]
        B2 --> B3[预热首页]
        B3 --> B4[打开详情页]
        B4 --> B5[读 __INITIAL_STATE__]
        B5 -.->|302 跳登录| BX[失败]
    end
```

| | `core/`（HTTP 直连） | `page.py`（浏览器） |
|---|---|---|
| 依赖 | 仅标准库 | playwright + chromium |
| 状态 | ✅ 在用 | ❌ 已被风控识别 |
| 入口 | `parse` 子命令 | `--url` / `--input` |
| 落盘 | `--save FILE` | `--out DIR` |

2026-10-10 实测：Playwright 的 TLS 指纹被小红书识别，
headless 与有头真 Chrome 全部 302 跳登录页；而 `urllib` + 手机 UA 直连成功。
所以浏览器链路不是「调参能救」，是路线本身不可用。它暂时保留，仅在人工排查时用。

---

## 原理

### 1. 三条铁律

1. **必须手机 UA。** 桌面 UA 会 302 到登录页，而 **HTTP 状态码仍是 200** ——
   只判状态码会静默拿到一个废页面。所以展开后必须校验最终 URL。
2. **必须 `urllib`。** 实测它的 TLS 指纹能过。
   `requests` / `httpx` / `curl_cffi` **未验证，不要替换**。
3. **不复用连接。** 不开 `Session`、不加 keep-alive，每次新建 `Request`。

### 2. 短链优先

短链（`xhslink.cn/o/xxx`）每次展开都由平台**新签发** `xsec_token`；
长链里写死的 token 几小时就失效。所以优先保存短链。

### 3. SSR 是 JS 字面量，不是 JSON

详情页把数据塞在 HTML 的 JS 对象里，含 `undefined`、尾随逗号，不能直接 `json.loads`。

```
HTML
 ├─ prepare()      只反转义 \u002F 与 \/（不碰 \" —— 会切断字段边界）
 ├─ 正则取标量      title / desc / likedCount / shareCount ...
 ├─ 括号配对取数组  "commentData":{"comments":[ → 深度扫描跳过字符串与转义 → json.loads
 └─ 摊平           一级评论在前，其楼中楼紧跟其后
```

**评论为什么必须括号配对**：SSR 里一级评论的 `user` 与 `content` 之间
隔着整个 `subComments` 数组（实测 1000~1500 字），任何「最近距离配对」都会错配；
而且 `user` 相对 `content` 的位置在一级评论与楼中楼里**正好相反**。
按括号配对取整段 JSON 是唯一不依赖字段顺序的做法。

### 4. 降级链

```
HTTP 直连
  ↓ token 类失败（detail_http_* / expand_no_token / expand_login）
重新展开短链换新 token
  ↓ 拿到 HTML 但关键字段全空（EmptyDataError）
重新展开短链换新 token
  ↓ 限流 / 网络类失败
指数退避 1s → 2s → 4s
  ↓ 仍失败
抛 FetchError（带 kind）
```

最长 4 次尝试（`BACKOFF = (1, 2, 4)`）。

---

## 命令与参数

### `parse` —— HTTP 直连（在用）

```powershell
python -m xhs_cli parse "https://xhslink.cn/o/9yWznlCm2pp"
```

| 位置/参数 | 必填 | 默认 | 说明 |
|---|---|---|---|
| `link` | ✅ | — | 小红书短链或长链 |
| `--json` | | 关 | 输出机器可读 JSON |
| `--save FILE` | | 无 | 同时把 JSON 写进文件 |

> ⚠️ `parse` **没有** `--out`，也不下载图片 —— 它只输出图片 URL。
> 想落成目录用主命令（见下）。
>
> ⚠️ 已知问题：`--json` 与 `--save` **同时用时不落盘**
> （`--save` 的判断被写在了 `else` 分支里）。
> 要存文件就别加 `--json`：`parse "<链接>" --save note.json`。

退出码：`0` 成功 · `2` 链接不支持 · `3` 抓取失败。

### 主命令 —— 浏览器链路（引擎已废弃）

```powershell
python -m xhs_cli --url "<链接>"          # 单篇
python -m xhs_cli --input urls.txt        # 链接清单（每行一个，# 开头为注释）
python -m xhs_cli --audit-only            # 只审计已有数据
```

| 参数 | 默认 | 说明 |
|---|---|---|
| `--url URL` | 无 | 单个分享链接 |
| `--input FILE` | 无 | 链接清单文件 |
| `--out DIR` | `xhs-cli/xhs_data` | 输出根目录 |
| `--skip-images` | 关 | 不下载图片 |
| `--audit-only` | 关 | 只审计已有数据，不抓取 |
| `--proxy URL` | 无 | 如 `http://127.0.0.1:7890` |
| `--sleep N` | `2.0` | 篇间间隔（秒） |
| `--engine` | `chromium` | `chrome` = 用本机 Chrome |
| `--no-headless` | 关 | 显示浏览器窗口（调试） |
| `--cookies FILE` | 无 | 注入 cookie（**非匿名模式**） |
| `--version` | | 打印版本 |

---

## 输出

### A. `parse` 的 JSON

一行命令：

```powershell
python -m xhs_cli parse "https://xhslink.cn/o/9yWznlCm2pp" --save note.json
```

`note.json` 结构（值为真实抓取结果，非示例编造）：

```jsonc
{
  "note_id": "6ac3c7f4000000001b02fc03",
  "note": {
    "note_id": "6ac3c7f4000000001b02fc03",
    "title": "学生心理需要重视",
    "desc": "#我在小红书聊心理[话题]# #学生压力大[话题]# …",
    "author": "胦鱼",
    "author_id": "667659460000000007007fc4",
    "ip_location": "",              // ⚠️ 匿名态拿不到，见「字段可用性」
    "liked": "7546",                // 全部为字符串
    "collected": "618",
    "comment_count": "523",         // 页面声明的总数（一级 + 楼中楼）
    "comment_count_l1": "226",      // 其中一级评论数
    "share": "176",                 // ⚠️ 这里叫 share，不是 share_count
    "time_ms": "1791215604000",     // 毫秒时间戳（字符串）
    "tags": ["我在小红书聊心理", "学生压力大", "…", "笔记", "我在小红书聊心理", "…"],
    "images": ["http://sns-webpic-qc.xhscdn.com/…!h5_1080jpg"]
  },
  "images": ["http://sns-webpic-qc.xhscdn.com/…!h5_1080jpg"],  // = note.images
  "comments": [
    {
      "user_id": "61599e8000000000020234ab",
      "nickname": "长夜.",
      "content": "一共才十四亿人，但是精神病人数接近两亿…",
      "ip_location": "山东",         // 评论 IP 可得
      "like_count": "0",            // 字符串
      "time": 1791470300000,        // 整数（毫秒）
      "is_author": false,
      "_is_reply": false
    },
    {
      "user_id": "667659460000000007007fc4",
      "nickname": "胦鱼",
      "content": "骗你的，其实本人也坚持不了也有抑郁[笑哭R]",
      "ip_location": "浙江",
      "like_count": "0",
      "time": 1791470950000,
      "is_author": false,
      "_is_reply": true,            // true = 楼中楼
      "_parent_id": "6ac7aadb…"     // 仅楼中楼有此字段，指向父评论 id
    }
  ],
  "declared": 523,                  // 页面声明的评论总数
  "got": 20,                        // 实际拿到多少条
  "complete": false,                // got >= declared
  "elapsed_ms": 426
}
```

字段要点：

| 字段 | 说明 |
|---|---|
| `note.*` 的计数字段 | 都是**字符串**（`"7546"`），不是数字 |
| `time_ms` | **毫秒**时间戳，字符串 |
| 评论 `time` | **毫秒**时间戳，整数 |
| 评论 `like_count` | 字符串，可能是 `"1千+"` 这类展示值 |
| `_is_reply` | `true` = 楼中楼；一级评论为 `false` |
| `_parent_id` | **只有**楼中楼才有 |
| `comments` 顺序 | 一级评论 + 其楼中楼紧跟其后，非严格时间序 |
| `complete` | `got >= declared`；匿名态几乎总是 `false` |

### B. 主命令的目录结构

```powershell
python -m xhs_cli --url "<链接>" --out my_data
```

```
my_data/<note_id>/
  content/note.json       标题/正文/互动数/作者/标签
  content/note.md         人读版
  images/urls.json        图片 URL 清单（按原顺序）
  images/01.jpg ...       下载的图片，序号与 urls.json 对齐
  comments/comments.json  扁平列表：一级 + 楼中楼（带 _is_reply）
  comments/card.json      统计卡片，含 partial 标记
```

> 这套 `note.json` 用的是**另一套键名**（`share_count` / `published`），
> 与 A 形态的 `share` / `time_ms` 不一致。
> 下游读数据时要同时兼容两套。参考 `jev/src/jev_guard/extractors/reader.py`
> 的 `FIELD_ALIASES`。

---

## 字段可用性（2026-10-10 实测）

| 数据 | 状态 | 说明 |
|---|---|---|
| 标题 / 正文 | ✅ | 需有效 token |
| 话题标签 | ⚠️ | **有重复**（见「已知问题」） |
| 图片 URL | ✅ | 同一张图在 SSR 里有多个 CDN 变体，已去重 |
| 帖子点赞 / 收藏 / 评论数 / 分享数 | ✅ | 部分笔记不公开该数字，此时返回空串 |
| 发布时间 | ✅ | `time_ms` |
| 作者昵称 / ID | ✅ | |
| **作者 IP 属地** | ❌ | note 区**没有任何** IP 字段 |
| 一级评论 | ⚠️ **只有 5 条** | 不论该帖实际有多少 |
| 该 5 条一级评论下的楼中楼 | ✅ | 全部带出 |
| 评论者昵称 / 正文 | ✅ | |
| **评论 IP 属地** | ✅ | |
| 评论点赞 | ⚠️ | 绝大多数是真实的 0 |
| 评论翻页（第 6 条一级起） | ❌ | 分页接口返回 461 |
| 搜索页 / 用户主页 | ❌ | 登录墙 |

两个最容易误解的点：

**「前十条」是错的，实际是「5 条一级评论 + 其下全部楼中楼」。**

| 帖 | 平台标称一级评论 | 实际内联 |
|---|---:|---:|
| `6a5c65d3` | 106 | **5** |
| `6ab6a30e` | 1874 | **5** |

所以总条数可以远超 5（楼中楼能带出几十上百条），但**楼层数被锁在 5**。

**作者 IP 匿名态拿不到。** note 区的 `user` 对象只有
`userId` / `nickName` / `avatar` / `redOfficialVerifyType`；
试过 `ipLocation` / `ipProvince` / `ipCity` / `locatedCity` / `publishLocation`
等 13 个候选键名，note 区全部 0 命中。全文的 `ipLocation` 都在 `commentData` 区内，
那些是**评论者**的 IP。

---

## 已知问题

| # | 问题 | 影响 |
|---|---|---|
| 1 | `tags` 有重复项，且混入假标签「笔记」 | 该字段不能直接用 |
| 2 | `--json --save FILE` 不落盘 | 存文件时别加 `--json` |
| 3 | `--out` 只在主命令有，`parse` 没有 | 想落目录得用主命令（但引擎已废弃） |

**问题 1 的成因**：`ssr.parse_note` 用全局正则 `"name":"…"` 取标签，两个后果 ——

- 页面里有 `"tabs":[{"id":"note","name":"笔记"}]`，「笔记」被当成标签；
- `tagList` 在 SSR 内联与水合数据里各存一份，于是每项重复两遍。

实测一帖 4 个真标签会输出 9 项：
`['我在小红书聊心理', '学生压力大', '教育理念的重要性', '以学生为中心', '笔记', '我在小红书聊心理', '学生压力大', '教育理念的重要性', '以学生为中心']`

**临时处理**：读之前先清洗 ——

```python
def clean_tags(tags):
    out = []
    for t in tags:
        t = t.strip()
        if t and t != "笔记" and t not in out:
            out.append(t)
    return out
```

---

## 失败分类

`FetchError.kind`：

| kind | 含义 |
|---|---|
| `expand_no_token` | 展开结果没有 `xsec_token` |
| `expand_login` / `expand_login_body` | 短链被跳到登录页 |
| `expand_http_{code}` | 展开时 HTTP 错误 |
| `expand_network` | 展开时网络故障 |
| `detail_http_{code}` | 详情页 HTTP 错误（401 / 461 等） |
| `detail_network` | 详情页网络故障 |
| `exhausted` | 重试 4 次后仍失败 |
| `UnsupportedLink` | 链接形态不支持（**不是** FetchError，不重试） |

拿到 HTML 但关键字段全空会抛 `EmptyDataError`，同样触发换 token 重试。

---

## 开发

```powershell
# 测试（30 个用例）
D:\LOreal-ai\.venv\Scripts\python.exe -m pytest xhs-cli/tests -q
```

改动前请先读 `core/fetch.py` 开头的三条铁律、
以及 `core/ssr_json.py` 的注释（记录了 7 轮正则迭代的失败原因）。

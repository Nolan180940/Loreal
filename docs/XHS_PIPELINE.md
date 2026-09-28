# 小红书链接 → 图片 / 文案 / 评论 全量导出

本文档说明如何**从一个小红书链接导出全部素材**，供赛道2「信任守护师」的内容核验流水线使用。

---

## 一、能力边界（先看这个，避免误解）

| 能拿到 | 拿不到 / 有损 |
|---|---|
| ✅ 笔记正文（`desc`） | ❌ **原图**（见下方说明） |
| ✅ 标签（`tag_list`） | ❌ 评论的**楼中楼正文**（仅拿到 `sub_comment_count`） |
| ✅ 一级评论（正文 / 昵称 / 点赞 / IP 属地 / 时间） | ⚠️ 评论**翻页上限 20 页**（安全阀） |
| ✅ 互动数据（点赞/收藏/评论/分享数） | |
| ✅ 图片文件（下载到本地） | |

### ⚠️ 关于「原图」

下载得到的图片**不是原始上传文件**，而是平台转码版。URL 形如：

```
https://ci.xiaohongshu.com/.../xxx?imageView2/format/jpeg
                                                    ↑ CDN 转码参数
```

实测 6 张图的噪声 σ = 0、EXIF 全空 → 传感器噪声与拍摄元数据已被剥离。

**影响**：像素级篡改取证（复制粘贴、拼接检测）在这批图上**不适用**。
**处置**：`forensic` 侧用 σ 检测做自动分流（见第五节）。

---

## 二、环境准备

### 2.1 目录结构

```
D:\LOreal-ai\
├─ .env                     # 存放 cookie（已被 .gitignore 排除）
├─ tools\
│  ├─ .venv\                # 采集工具虚拟环境
│  ├─ spider_xhs\           # Spider_XHS（签名实现）
│  └─ read_my_cookie.py     # cookie 读取辅助（可选）
└─ data\xhs\                # 输出目录
```

### 2.2 依赖

```powershell
cd D:\LOreal-ai\tools
.\.venv\Scripts\python.exe -m pip install curl-cffi PyExecJS loguru
```

**系统要求**：Node.js（`node --version` 有输出即可），`PyExecJS` 依赖它。

### 2.3 Cookie

小红书接口需要登录态。`web_session` 是 **HttpOnly**，Console 脚本读不到，必须手动取：

**方法 A（推荐）**：F12 → Application → Storage → Cookies → `https://www.xiaohongshu.com` → 找 `web_session` → 复制 Value

**方法 B**：`F12 → Network → 勾选「保留日志」→ 滚动评论区 → 点任意 `api/sns` 请求 → Headers → Request Headers → 复制 `cookie:` 整行

拿到后写入 `.env`：

```
XHS_COOKIE=a1=xxx; webId=xxx; web_session=xxx; gid=xxx; ...
```

> `.env` 已在 `.gitignore` 中，**绝不会进仓库**。也可用系统环境变量 `XHS_COOKIE` 覆盖（优先级更高）。

---

## 三、导出流程

### 3.1 第一步：解析链接拿 note_id 与 xsec_token

```python
from forensic.xhs_comments import parse_note_ref

ref = parse_note_ref("https://xhslink.cn/o/6wvIYWl9oLU")
print(ref["note_id"])      # 6a4cc2cd000000001101daf1
print(ref["xsec_token"])   # CBzj7RPSlGq4mj5dZr...
```

短链（`xhslink.cn`）必须先展开，`tools` 内的 `XHS.extract()` 会自动处理。

### 3.2 第二步：导出正文 + 标签 + 图片

```python
import asyncio
from source import XHS          # tools 已在 sys.path

async def main():
    async with XHS(
        cookie="",                       # 留空则读 .env / 浏览器
        work_path="D:/LOreal-ai/data/xhs",
        image_format="JPEG",            # 取证用途别选 WEBP（有损）
        record_data=True,               # 写入 ExploreData.db
        note_format="all",              # 保存 txt + md
        download_record=False,          # 允许重复下载
        write_mtime=True,               # 文件 mtime = 发布时间（时间线取证有用）
    ) as xhs:
        return await xhs.extract(url, download=True)

note = asyncio.run(main())[0]
print(note["作品标题"])
print(note["作品描述"])   # 正文
print(note["作品标签"])   # #标签
print(note["评论数量"])
print(note["下载地址"])   # 图片 URL 列表
```

**输出**：图片落在 `data\xhs\Download\`，作品数据落在 `data\xhs\Download\ExploreData.db`。

### 3.3 第三步：导出评论

用 Spider_XHS 的签名实现（`xhshow` 的签名不被小红书网关承认，见第六节）：

```python
from forensic.xhs_comments import get_cookie
from xhs_utils.xhs_pc import XHSPcAuth
from apis.xhs_pc_apis import XHS_Apis

auth = XHSPcAuth.from_cookie(get_cookie())
apis = XHS_Apis(auth)
apis.bootstrap()                                   # 必须：拿 user_id 算 xy-direction
ok, msg, comments = apis.get_note_all_out_comment(note_id, xsec_token)
```

**`bootstrap()` 不可省略** —— 它调 `user/me` 拿到 `user_id`，签名头 `xy-direction` 依赖它。缺这步会返回 **HTTP 406**。

现成脚本：`tools\spider_xhs\fetch_comments.py`

```powershell
cd D:\LOreal-ai\tools\spider_xhs
..\.venv\Scripts\python.exe fetch_comments.py
# 输出：fetched=20 saved=D:\LOreal-ai\data\xhs\comments_raw.json
```

### 3.4 一键跑通（推荐）

`fetch_comments.py` 已串好完整链路：读 cookie → bootstrap → 抓评论 → 落盘 JSON + 预览 TXT。

---

## 四、评论数据结构

```json
{
  "id": "65f...",
  "note_id": "6a4cc2cd000000001101daf1",
  "content": "这个真的是没有平替啊啊啊啊",
  "like_count": "0",
  "create_time": 1752...,
  "ip_location": "江苏",
  "sub_comment_count": "1",
  "user_info": {
    "user_id": "68...",
    "nickname": "小星星",
    "image": "https://..."
  }
}
```

**可用于分析的水军信号字段**：

| 字段 | 信号 |
|---|---|
| `create_time` | 批量同时间发布 |
| `ip_location` | 同省聚集 |
| `nickname` | 模板化/默认昵称/数字串 |
| `content` | 高度重复、模板话术 |
| `like_count` | 异常点赞曲线 |
| `user_id` | 跨帖复用检测（需多篇语料） |

---

## 五、与取证流水线的衔接

```
输入链接
   ↓
[采集] 正文 / 标签 / 评论 / 图片
   ↓
[分流] σ 噪声检测  ← forensic/features.extract_x1 的 sigma
   ├─ σ ∈ [2,8]  真原图 → 跑 x1–x6 像素取证
   └─ σ ≈ 0      转码版 → 只跑修饰强度 / 版式 / 图文一致性
   ↓
[分析] 文本侧：种草判定（队友）
        评论侧：水军 / 质疑信号
        图片侧：修饰强度（face_Y、pore_kurt）
   ↓
[融合] logit 加权 + 三档判定 + 证据卡
```

**σ 检测实现**（在纹理最强的 30% 像素上估计，避免整屏纯色把 σ 拉成 0）：

```python
import numpy as np
from scipy import ndimage
from PIL import Image

def noise_sigma(path):
    g = np.asarray(Image.open(path).convert("L")).astype(np.float32)
    r = g - ndimage.median_filter(g, size=3)
    m1 = ndimage.uniform_filter(g, 8); m2 = ndimage.uniform_filter(g * g, 8)
    lstd = np.sqrt(np.maximum(m2 - m1 * m1, 0))
    mask = lstd >= max(np.percentile(lstd, 70), 1.0)
    return float(1.4826 * np.median(np.abs(r[mask]))) if mask.sum() > 100 else 0.0
```

**实测参考**：真实相机照 σ ≈ 2–8；小红书转码版 σ = 0；截图 σ = 0。

---

## 六、踩坑记录（避免重复试错）

| 现象 | 根因 | 处置 |
|---|---|---|
| 笔记接口 406 | `edith` 网关拒绝非官方客户端签名 | 改用 HTML 抓取（XHS-Downloader） |
| 评论接口 406 | `xhshow` 签名不被承认 | 换 Spider_XHS；**且必须先 `bootstrap()`** |
| 换 host 报 500 | `edith` → `www` 路由不同 | 别换 |
| `ModuleNotFoundError: xhshow` | 官方 `pyproject.toml` 未声明该包 | 手动 `pip install xhshow` |
| `rookiepy` 装不上 | 需 Rust 编译 | 放弃自动读浏览器 cookie，手动取 |
| `document.cookie` 拿不到 `web_session` | HttpOnly，浏览器设计如此 | 必须用 Application/Network 面板 |
| 重复下载被跳过 | 作品 ID 存在 `ExploreID.db` | 删库或 `download_record=False` |
| PowerShell `-c` 传多行代码转义失败 | `exec('...\n...')` 引号被吃 | 写成 `.py` 文件运行 |

---

## 七、风控与合规

| 事项 | 说明 |
|---|---|
| **请求频率** | 官方文档警告高频请求会触发风控甚至封号。本实现内置 1.2s 延时 + 20 页安全阀 |
| **旧链接失效** | 作品链接带日期，**必须用最新获取的链接** |
| **自动化滚动** | 默认关闭；开启可能被判定为自动化导致封号 |
| **使用范围** | 仅用于公开可见内容的采集与分析。请遵守平台 ToS 与当地法规，不要用于规模化抓取、用户数据画像或商业竞争用途 |

---

## 八、快速命令速查

```powershell
$PY = "D:\LOreal-ai\tools\.venv\Scripts\python.exe"

# 抓评论（现成脚本）
cd D:\LOreal-ai\tools\spider_xhs
& $PY fetch_comments.py

# 导出笔记（正文+标签+图片）
cd D:\LOreal-ai\tools
& $PY main.py            # TUI 交互模式，粘贴链接即可

# 启动 API 服务（供网页后端调用）
& $PY main.py api        # http://127.0.0.1:5556/xhs/detail

# 评估图片是否真原图
cd D:\LOreal-ai
d:\LOreal-ai\.venv\Scripts\python.exe -c "from forensic.xhs_comments import *; ..."
```

**API 调用示例**（网页后端）：

```python
from curl_cffi.requests import post

resp = post("http://127.0.0.1:5556/xhs/detail", json={
    "url": "https://xhslink.cn/o/6wvIYWl9oLU",
    "download": True,
    "index": None,          # None = 全部图片
}, timeout=30)
note = resp.json()
```

---

## 九、相关文件

| 路径 | 作用 |
|---|---|
| `forensic/xhs_comments.py` | cookie 读取、链接解析、评论抓取（`xhshow` 路线，备用） |
| `tools/spider_xhs/fetch_comments.py` | **推荐**：Spider_XHS 签名路线评论抓取 |
| `tools/read_my_cookie.py` | 浏览器 cookie 读取辅助（需管理员权限） |
| `data/xhs/comments_raw.json` | 评论原始数据 |
| `data/xhs/ExploreData.db` | 笔记数据（SQLite） |
| `docs/PROGRESS.md` | 项目进展与决策记录 |

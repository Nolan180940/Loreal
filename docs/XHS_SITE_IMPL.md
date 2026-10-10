# XHS 解析服务 · 实现说明（HTTP 路线）

> 状态：**S1–S3 + CLI 已完成并用真实短链验证通过**（2026-10-10）。
> 网站层（S6/S7）未开始。

---

## 1. 验证结论

用 4 条真实链接（3 短链 + 1 长链）端到端验收：

| 用例 | 形态 | 结果 | 耗时 |
|---|---|---|---|
| 面试贴 | 短链 | ✅ 11 条评论全字段正确 | 672ms |
| 养白tips | 短链 | ✅ 15 条评论全字段正确 | 665ms |
| 沐言冰岛 | 短链 | ✅ 20 条评论全字段正确 | 442ms |
| 同帖长链 | 长链+token | ✅ 与短链一致 | — |

字段质量：**空 content 0 / 空昵称 0 / 空 IP 1**（该条评论 SSR 本身无 IP）。

**全程零浏览器、零 Playwright、零登录态。**

---

## 2. 架构

```
xhs_cli/core/            ← 新增，HTTP 直连路线
  link.py      链接归一化（短链/长链 -> LinkRef）
  fetch.py     urllib + 手机 UA（唯一实测可用的指纹）
  ssr.py       HTML -> 结构化字段
  ssr_json.py  括号配对提取 comments 数组（精确路径）
  service.py   parse_link()：重试 + 换 token + 降级链

xhs_cli/page.py          ← Playwright 路线，保留为人工兜底，**不进主链路**
xhs_cli/extractors/*     ← 零改动
xhs_cli/storage/*        ← 零改动
```

CLI 用法：

```bash
xhs-cli parse <链接>              # 人类可读
xhs-cli parse <链接> --json        # 机器可读（喂网站后端）
xhs-cli parse <链接> --save out.json
```

---

## 3. 三条铁律（改动前必读）

| # | 铁律 | 违反后果 |
|---|---|---|
| 1 | **必须手机 UA** | 桌面 UA 会 302 到登录页，且 HTTP 状态仍是 200 —— 不校验最终 URL 发现不了 |
| 2 | **必须 urllib** | 实测它的 TLS 指纹能过。`requests`/`httpx`/`curl_cffi` 未验证，Playwright 的 Chromium 指纹**已确认被拒** |
| 3 | **不许复用连接** | 不开 Session、不加 keep-alive。每次新建 Request 最像新用户首访 |

---

## 4. 评论解析的演进（7 轮，教训都在代码注释里）

正则方案全部失败，最终改用**括号配对 + `json.loads`**：

```
v1  单正则 content...[^}]{0,800}...user        → 0 命中（隔 3 层嵌套）
v2  按 user 切块，左右就近取                   → 24 命中，content 错位到上一条
v3  按 user 切块，只向后取                     → 一级对，楼中楼全错（字段顺序相反）
v4  以 content 为锚，before/after 分方向取     → IP 配到上一条的
v5  以 content 为锚，附属字段按绝对距离最近     → 一级对，楼中楼错（隔着 subComments）
v6  标题距离阈值                               → 仍有跨条错配
v7  括号配对 + json.loads                      → ✅ 全部正确
```

**v7 可行的根本原因**：一级评论的 `user` 与 `content` 之间**隔着整个
`subComments` 数组**（实测 1000~1500 字）。任何"就近匹配"在这种跨度下
都会错配，只有真正解析 JSON 结构才对。

代码位置：`ssr_json.py::parse_comments_json`，慢路径（正则）保留作保底。

---

## 5. 踩过的坑

### 5.1 `prepare()` 不能转 `\"`

```python
# ❌ 会截断 content，并把后续字段咬进来（表现为尾部带 「赞0}」）
raw.replace('\\"', '"')

# ✅ 只转斜杠；引号由各字段取出后单独 unescape()
prepare() -> html.replace("\\u002F", "/")
```

### 5.2 `likeCount` 的正则别用 `[^,]+`

`"likeCount":0}` 后面是 `}` 不是 `,`，`[^,]+` 会吃到 `}`。
用 `(\d+)` 或字符串形式（值可能是 `"1千+"`）。

### 5.3 note 的 `ipLocation` 不能直接 grab

`grab(h, "ipLocation")` 取到的是**第一条评论的 IP**。
改为先定位作者 userId，再在其后 600 字内取（`ssr.py::_author_ip`）。
**注意**：实测该字段 SSR 经常不提供，返回空是正常行为。

### 5.4 user 块有 4 种形态，`atUsers` 是陷阱

```
A. {"image":..,"aiAgent":false,"userId":"..","nickname":".."}
B. {"userId":"..","nickname":"..","image":..}
C. {"image":..,"aiAgent":false,"userId":".."}            ← 无 nickname
D. atUsers: [{"userId":"..","nickname":".."}]            ← 不是评论者！
```
正则必须锚定 `"user":{`，否则把被 @ 的用户当成评论者。

### 5.5 `nickName` vs `nickname`

作者用 `nickName`（大写 N），评论用 `nickname`。两个都要试。

### 5.6 Windows 控制台必须 reconfigure UTF-8

昵称/内容高频 emoji，GBK 直接 `UnicodeEncodeError`。

---

## 6. 已知限制（诚实清单）

| 限制 | 说明 |
|---|---|
| **评论拿不全** | SSR 首屏只给 10 条一级 + 内联楼中楼。实测 11/16、15/65、20/4351。API 已返回 `declared` 与 `got`，前端据此提示 |
| **不做翻页** | `comment/page` 需签名且实测 461 限流（详见 `tools/spider_xhs/PROBE_NOTES.md`） |
| **作者 IP 常缺失** | SSR 不提供，返回 `""` |
| **只验证过一个手机 UA** | UA 可配置（`fetch.MOBILE_UAS`），未验证的不默认启用 |
| **urllib TLS 指纹是隐性依赖** | 锁 Python 版本；部署时锁基础镜像 digest |

---

## 7. 下一步（未开始）

- **S6 网站层**：FastAPI + 单页 HTML。`POST /api/parse` 直接调 `parse_link()`
- **S7 部署**：Dockerfile（无需 Chromium，镜像约 150MB）
- 图片：默认只返 URL（CDN 公网可达，已实测下载成功），不代理下载

---

## 8. 测试

```
xhs-cli/tests/test_core_http.py    22 passed
jev/tests/                         90 passed
```

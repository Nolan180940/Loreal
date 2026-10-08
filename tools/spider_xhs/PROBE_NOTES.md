# 461 / 全量评论排查记录（2026-10-08）

一次性探测脚本已删除，结论保留。需要复现时按下面的方法重写。

## 已验证的死路（别再试）

| 尝试 | 结果 |
|---|---|
| 浏览器直发 comment/page（v1/v2、GET/POST、去参、加参、改头） | 全部 500 `jarvis-gateway` |
| Python 签名 + 同会话翻页 | 第1页✅ 第2页 `data={}` |
| Python 签名 + 新会话 + 首页 cursor | 同样空 |
| AnonPool 每请求换会话 | 第2页 461 |
| SSR cursor / 伪造 cursor | 461（服务端校验 cursor 真实性） |
| sub/page 楼中楼 | 匿名返回空 |
| top_comment_id | 首请求 10 条但与内联 0 重叠（另一窗口），第2页 461 |
| num=20/30/50 | 全部返回 10 条（服务端写死） |
| 90 秒间隔 | 无效（限流是次数维度） |
| 短链之外的取 token 路 | 搜索页无权限、推荐流 token 在 DOM 被清理 |

## 已确认的技术事实

1. **API 真实域名是 `edith.xiaohongshu.com`，不是 `www`。**
   签名绑定 URL —— 打 `www` 必 500，打 `edith` 才 461（签名通过）。
   **500→461 是判断签名是否正确的唯一可靠信号。**

2. **headless chromium 被指纹识别**：`feed._rawValue` 长度 = 0。
   `channel="chrome" + headless=False` 才有 feed（28-31条）。

3. **前端 RAP 签名白名单**（`window.anti_hp_sign_config.signIncludesUrl`）：
   ```
   ✅ homefeed / search/notes / feed / comment/post
   ❌ comment/page / comment/sub/page
   ```
   所以浏览器直发必缺签名。手动注入白名单无效（RAP 读安装时快照）。
   必须走 Python `_request_params()` 生成完整头（含 `x-xray-traceid`）。

4. **cursor 就是上一页最后一条的 id**（实测 `cursor==第10条`）。
   伪造 cursor 直接 461。

5. **top_comment_id 是排序锚点不是窗口**：3 个不同取值 8/10 重叠。

6. **新 token 也翻不了页**：CBSb 前缀（App 分享）首页 200，第2页 461。
   461 与 token 无关，是 IP + 接口维度的滑动窗口配额。

7. **SSR 的 cursor 与 API 返回的一致**（`6abc9a22...`）。

## 匿名天花板（实测）

```
每篇 = SSR 首页 10 条一级 + 内联楼中楼
     + 字段 10/10 完整（createTime/ipLocation/likeCount/userInfo）
```

## 待验证（配额恢复后测一次）

**真 Chrome 指纹 + 正确签名下，第 2 页能否过？**
之前的"第2页必死"全是在 headless 指纹下测的。`collect_full.py`
就是为这个写的（真 Chrome 常驻 + 等配额恢复 + 自动翻页）。

## 有价值的工具脚本（已保留）

- `collect_full.py` —— 真 Chrome + 精确签名 + 等配额 + 自动翻页 + 断点续跑
- `collect_union.py` —— 多会话 + 锚点轮换拼并集（5 会话 = 12 条）
- `sign_for_browser.py` —— 为浏览器会话生成签名（a1 替换法）
- `watch_quota.py` —— 配额恢复探测器（每 N 分钟一次）
- `test_fresh_paging.py` —— 新 token 首页 + 翻页最小验证
- `hybrid_reverse.py` —— 反向混合（浏览器建会话 → Python 签名）
- `chrome_probe3.py` —— 真 Chrome + 原样复用 `_request_params` 头

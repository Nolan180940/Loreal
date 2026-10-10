# 匿名态决定性测试

目标笔记：`6a97b778000000002b012493`

## 1. 访客会话

- 首页 HTTP 200
- 最终 URL 域名路径：`https://www.xiaohongshu.com/login`
- 是否登录页：**是**
- feed 条数：**0**
- noteDetailMap：`undefined`

- cookie 名单：`a1, abRequestId, acw_tc, acw_tc, ets, gid, loadts, sec_poison_id, webBuild, webId, web_session, websectiga, xsecappid`

> 判据：`feedLen > 0` 或 `noteId` 存在才算匿名会话真的可用。

## 2. 笔记详情页 —— 各种 URL 形态

每种都显式检查 noteDetailMap，而不是只看 HTTP 200。

| URL 形态 | HTTP | 落登录页 | noteDetailMap | 点赞 | 评论数 | 首批评论 |
| --- | ---: | :-: | --- | ---: | ---: | ---: |
| 无 token 无 source | 200 | 否 | `undefine` | None | None | 0 |
| 无 token + pc_feed | 200 | 否 | `undefine` | None | None | 0 |
| discovery/item 无 token | 200 | 否 | `undefine` | None | None | 0 |
| 老 token（9-30 签发） | 200 | **是** | `undefine` | None | None | 0 |

## 3. 能否解析出新鲜 (note_id, xsec_token)

- DOM 里 `/explore/` 链接：**0** 条
- 其中带 xsec_token：**0** 条


## 4. 搜索页（匿名是否有权限）

- HTTP 200 ·落登录页：**否**
- 页面标题含「登录后」：**是**

## 5. 结论

✅ **无 token 无 source** 可用：拿到 `undefine` 赞None 藏None 评None 首批评论0
✅ **无 token + pc_feed** 可用：拿到 `undefine` 赞None 藏None 评None 首批评论0
✅ **discovery/item 无 token** 可用：拿到 `undefine` 赞None 藏None 评None 首批评论0
✅ **老 token（9-30 签发）** 可用：拿到 `undefine` 赞None 藏None 评None 首批评论0

### token 是否必需

如果「无 token」也能拿到 noteDetailMap，
说明 token 只是入口凭证而非数据凭证，匿名完全可行。
如果只有带 token 的能拿到 —— 而老 token 又已过期 ——
那匿名路径必须先解决「怎么拿新 token」。

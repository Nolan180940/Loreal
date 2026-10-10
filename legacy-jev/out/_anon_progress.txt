# 匿名实测：xhs-cli 能力边界

## 1. 预热（访客会话）

- warmup(): **True**
- cookie 数量：12
- cookie 名单：`a1, abRequestId, acw_tc, ets, gid, loadts, sec_poison_id, webBuild, webId, web_session, websectiga, xsecappid`

## 2. 取token

- 搜索 `雅诗兰黛 小棕瓶` 拿到 0 条

搜索页被拦（匿名访客无搜索权限）。

改用已知 note_id 走详情页 —— 验证 token 是否还有效。

改用 2 个存量 token 继续探测。

去重后：**2** 篇可用

## 3. 详情页字段（noteDetailMap）

- `6a97b778` **被重定向到登录页**
- `693abce3` **被重定向到登录页**
## 4. 汇总：匿名拿到的字段全集

### 笔记层

```
(未取到)
```

### 笔记互动指标

```
(未取到)
```

### 评论容器

```
(未取到)
```
# 两篇失败帖诊断

## `6a17c863` 珂润面霜买错了

清单里的 URL（`xsec_source=pc_search`）：

```
https://www.xiaohongshu.com/explore/6a17c863000000000702e8ef?xsec_token=ABWTuMmCSoT2Rv-nOSy3zu-zeYzkLPnurIGHQiz_UyMiU=&xsec_source=pc_search
```

- HTTP 200
- 最终 URL：`https://www.xiaohongshu.com/website-login/captcha?redirectPath=http%3A%2F%2Fwww.xiaohongshu.com%2Fexplore%2F6a17c863000000000702e8ef%3Fxsec_token%3DAB`
- 落点判定：验证码页
- body 大小：**10358** 字节（正常详情页约 22000+）
  - 含 `noteDetailMap`：False
  - 含 `commentData`：False
  - 含 `likedCount`：False
  - 含 `登录`：False
  - 含 `验证`：False

## `6abc5bb8` (无标题)

清单里的 URL（`xsec_source=pc_search`）：

```
https://www.xiaohongshu.com/explore/6abc5bb8000000000202bdc0?xsec_token=ABdUWRv6N5fFtsvtxXlyW0dDWyeVmO5soSDblVd2pPq6U=&xsec_source=pc_search
```

- HTTP 200
- 最终 URL：`https://www.xiaohongshu.com/website-login/captcha?redirectPath=http%3A%2F%2Fwww.xiaohongshu.com%2Fexplore%2F6abc5bb8000000000202bdc0%3Fxsec_token%3DAB`
- 落点判定：验证码页
- body 大小：**10358** 字节（正常详情页约 22000+）
  - 含 `noteDetailMap`：False
  - 含 `commentData`：False
  - 含 `likedCount`：False
  - 含 `登录`：False
  - 含 `验证`：False


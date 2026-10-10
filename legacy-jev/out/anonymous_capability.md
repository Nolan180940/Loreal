## 1. 离线数据盘点：哪些笔记有笔记层互动指标

| 字段 | 有值笔记数 | 占比 |
| --- | ---: | ---: |
| liked | 42/42 | 100% |
| collected | 41/42 | 98% |
| comment_count | 40/42 | 95% |
| share_count | 41/42 | 98% |

## 2. 匿名实测（不带任何 cookie）

用 B 组里点赞最高的一篇做探测 —— 它是纯匿名 SSR 采集的。

### 2.1 匿名请求笔记详情页 HTML，看 __INITIAL_STATE__ 是否含互动指标

| note | HTTP | 含 noteDetailMap | liked | collected | commentCount | shareCount |
| --- | --- | --- | ---: | ---: | ---: | ---: |
| `6ab6a30e` | 200 | N | - | - | - | - |
| `6abb030f` | 200 | N | - | - | - | - |

**匿名可读详情页：0/3**

## 3. 评论 API 匿名实测（comment/page）

这是关键一环：匿名能不能拿到带 like_count / create_time / ip_location 的评论。

| note | HTTP | 返回条数 | 带create_time | 带like_count | 带ip_location |
| --- | --- | ---: | ---: | ---: | ---: |
| `6ab6a30e` | **500** | - | - | - | - |
| `6abb030f` | **500** | - | - | - | - |

> 461 = 风控拦截。注释里已记录「匿名状态下第 2 页必 461」。

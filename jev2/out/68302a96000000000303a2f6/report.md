# jev2 单篇判定：`68302a96000000000303a2f6`

> 这就是贵货的威力吗。。。

## 结论

| 项 | 值 |
|---|---|
| 总分 | **0.7960** |
| 档位 | **高风险** |
| run_id | `20261011-145742-0b53f7` |
| config_hash | `efe851c89c90` |
| 模型 | `jev-1.13` |
| 规则集 | `default` |
| 判定时间 | 2026-10-11T14:57:43 |
| 耗时 | 920 ms |

## 笔记

| 项 | 值 |
|---|---|
| 标题 | 这就是贵货的威力吗。。。 |
| 作者 | 是你拐 |
| 点赞 | 2986 |
| 评论声明 | 246 |
| 评论实得 | 19 |
| 图片 | 3 张 |

## 语义维度（jev-1.13）

| 维度 | 风险值 | 置信度 | 题型 |
|---|---:|---:|---|
| `exaggeration` | 0.987 | 0.96 | score |
| `has_risk` | 0.890 | — | noul |
| `is_ad` | 0.730 | — | noul |
| `is_cta` | 0.060 | — | noul |

## 统计信号

| 信号 | 风险值 | n | 详情 |
|---|---:|---:|---|
| `comment_len_mean` | 0.417 | 19 | mean=17.7 |
| `like_comment_ratio` | 0.327 | 1 | ratio=12.14 · liked=2986 · comment_count=246 |
| `low_effort_ratio` | 0.269 | 19 | low_effort=8 · ratio=0.421 |
| `comment_len_iqr` | 0.188 | 19 | iqr=17.0 |
| `text_exclaim_density` | 0.168 | 498 | exclaims=7 · density_per_100=1.41 |
| `tag_count` | 0.143 | 6 | tag_count=6 · tags=('眼霜', '眼霜推荐', '兰蔻菁纯眼霜', '眼纹', '抗老眼霜', '全新兰蔻菁纯眼霜')  |
| `author_reply_ratio` | 0.000 | 19 | author_comments=0 · ratio=0.0 |
| `comment_len_sd` | 0.000 | 19 | sd=16.47 · mean=17.7 · min_len=2 · max_len=57 |
| `comment_time_span` | 0.000 | 19 | span_minutes=587492.1 · first_ms=1748500888000 · last_ms=1783750411000 |
| `cta_lexicon` | 0.000 | 0 | density_per_100=0.0 · strong=[] · weak=[] |
| `ip_entropy` | 0.000 | 19 | entropy=0.9497 · distinct=9 |
| `ip_top1_ratio` | 0.000 | 19 | top1=0.211 · top1_ip=四川 · distinct=9 |
| `structure_markers` | 0.000 | 0 | marker_count=0 · markers=[] |
| `sub_reply_ratio` | 0.000 | 19 | replies=15 · ratio=0.789 |
| `text_length` | 0.000 | 485 | desc_len=485 · title_len=12 |

**缺失 1 个**（样本不足或数据源限制，未参与打分）：

- `comment_like_rate` —— 19 条评论点赞全为 0 —— 疑似匿名态未填充该字段，不作为刷评证据

## 判定过程（规则逐条求值）

| 规则 | 动作 | 值 | 权重 | 贡献 | 说明 |
|---|---|---:|---:|---:|---|
| `ad_gate` | veto | 0.000 | 0.00 | 0.0000 | is_ad=0.000 < 0.85 |
| `risk` | contribute | 0.890 | 0.35 | 0.3115 |  |
| `exaggeration` | contribute | 0.987 | 0.30 | 0.2960 |  |
| `is_ad` | contribute | 0.730 | 0.25 | 0.1825 |  |
| `is_cta` | contribute | 0.060 | 0.10 | 0.0060 |  |
| `l2_stats` | flag | 0.101 | 0.00 | 0.0000 | l2_mean=0.101（仅记录，不计分） |

> 命中 veto 的规则会直接把总分拉满，后续规则不再计入；
> `flag` 动作只记录不计分（如 L2 统计信号）。


# jev2 单篇判定：`6a463cfb000000001700ba21`

> 25岁抗初老，兰蔻小黑瓶值得买吗？

## 结论

| 项 | 值 |
|---|---|
| 总分 | **0.1485** |
| 档位 | **低风险** |
| run_id | `20261011-141239-304fd6` |
| config_hash | `efe851c89c90` |
| 模型 | `jev-1.13` |
| 规则集 | `default` |
| 判定时间 | 2026-10-11T14:12:53 |
| 耗时 | 711 ms |

## 笔记

| 项 | 值 |
|---|---|
| 标题 | 25岁抗初老，兰蔻小黑瓶值得买吗？ |
| 作者 | 存到10w就去西藏 |
| 点赞 | 61 |
| 评论声明 | 79 |
| 评论实得 | 17 |
| 图片 | 1 张 |

## 语义维度（jev-1.13）

| 维度 | 风险值 | 置信度 | 题型 |
|---|---:|---:|---|
| `is_cta` | 0.350 | — | noul |
| `exaggeration` | 0.217 | 0.59 | score |
| `is_ad` | 0.110 | — | noul |
| `has_risk` | 0.060 | — | noul |

## 统计信号

| 信号 | 风险值 | n | 详情 |
|---|---:|---:|---|
| `comment_len_iqr` | 0.250 | 17 | iqr=16.0 |
| `comment_len_mean` | 0.055 | 17 | mean=23.2 |
| `like_comment_ratio` | 0.030 | 1 | ratio=0.77 · liked=61 · comment_count=79 |
| `author_reply_ratio` | 0.000 | 17 | author_comments=3 · ratio=0.176 |
| `comment_len_sd` | 0.000 | 17 | sd=13.69 · mean=23.2 · min_len=5 · max_len=51 |
| `comment_time_span` | 0.000 | 17 | span_minutes=100406.2 · first_ms=1782988286000 · last_ms=1789012659000 |
| `cta_lexicon` | 0.000 | 0 | density_per_100=0.0 · strong=[] · weak=[] |
| `ip_entropy` | 0.000 | 17 | entropy=0.9338 · distinct=10 |
| `ip_top1_ratio` | 0.000 | 17 | top1=0.235 · top1_ip=广东 · distinct=10 |
| `low_effort_ratio` | 0.000 | 17 | low_effort=4 · ratio=0.235 |
| `structure_markers` | 0.000 | 0 | marker_count=0 · markers=[] |
| `sub_reply_ratio` | 0.000 | 17 | replies=12 · ratio=0.706 |
| `tag_count` | 0.000 | 5 | tag_count=5 · tags=('求助', '兰蔻超修小黑瓶', '精华推荐', '抗初老', '精华') · desc_len=1 |
| `text_exclaim_density` | 0.000 | 165 | exclaims=0 · density_per_100=0.0 |
| `text_length` | 0.000 | 147 | desc_len=147 · title_len=17 |

**缺失 1 个**（样本不足或数据源限制，未参与打分）：

- `comment_like_rate` —— 17 条评论点赞全为 0 —— 疑似匿名态未填充该字段，不作为刷评证据

## 判定过程（规则逐条求值）

| 规则 | 动作 | 值 | 权重 | 贡献 | 说明 |
|---|---|---:|---:|---:|---|
| `ad_gate` | veto | 0.000 | 0.00 | 0.0000 | is_ad=0.000 < 0.85 |
| `risk` | contribute | 0.060 | 0.35 | 0.0210 |  |
| `exaggeration` | contribute | 0.217 | 0.30 | 0.0650 |  |
| `is_ad` | contribute | 0.110 | 0.25 | 0.0275 |  |
| `is_cta` | contribute | 0.350 | 0.10 | 0.0350 |  |
| `l2_stats` | flag | 0.022 | 0.00 | 0.0000 | l2_mean=0.022（仅记录，不计分） |

> 命中 veto 的规则会直接把总分拉满，后续规则不再计入；
> `flag` 动作只记录不计分（如 L2 统计信号）。


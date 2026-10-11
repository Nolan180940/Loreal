# jev2 单篇判定：`6931e77a000000001e033f7b`

> 珂润面霜今年入的很对很适合油皮冬季用

## 结论

| 项 | 值 |
|---|---|
| 总分 | **0.1140** |
| 档位 | **低风险** |
| run_id | `20261011-141239-304fd6` |
| config_hash | `efe851c89c90` |
| 模型 | `jev-1.13` |
| 规则集 | `default` |
| 判定时间 | 2026-10-11T14:12:40 |
| 耗时 | 790 ms |

## 笔记

| 项 | 值 |
|---|---|
| 标题 | 珂润面霜今年入的很对很适合油皮冬季用 |
| 作者 | 瑶妹妹 |
| 点赞 | 54 |
| 评论声明 | 8 |
| 评论实得 | 7 |
| 图片 | 3 张 |

## 语义维度（jev-1.13）

| 维度 | 风险值 | 置信度 | 题型 |
|---|---:|---:|---|
| `exaggeration` | 0.207 | 0.62 | score |
| `is_ad` | 0.110 | — | noul |
| `is_cta` | 0.070 | — | noul |
| `has_risk` | 0.050 | — | noul |

## 统计信号

| 信号 | 风险值 | n | 详情 |
|---|---:|---:|---|
| `comment_len_iqr` | 0.969 | 7 | iqr=4.5 |
| `comment_len_mean` | 0.838 | 7 | mean=11.4 |
| `low_effort_ratio` | 0.286 | 7 | low_effort=3 · ratio=0.429 |
| `like_comment_ratio` | 0.213 | 1 | ratio=6.75 · liked=54 · comment_count=8 |
| `author_reply_ratio` | 0.000 | 7 | author_comments=0 · ratio=0.0 |
| `comment_len_sd` | 0.000 | 7 | sd=7.37 · mean=11.4 · min_len=3 · max_len=28 |
| `comment_time_span` | 0.000 | 7 | span_minutes=138381.3 · first_ms=1764920552000 · last_ms=1773223429000 |
| `cta_lexicon` | 0.000 | 0 | density_per_100=0.0 · strong=[] · weak=[] |
| `ip_entropy` | 0.000 | 7 | entropy=0.963 · distinct=5 |
| `ip_top1_ratio` | 0.000 | 7 | top1=0.286 · top1_ip=江苏 · distinct=5 |
| `structure_markers` | 0.000 | 0 | marker_count=0 · markers=[] |
| `sub_reply_ratio` | 0.000 | 7 | replies=3 · ratio=0.429 |
| `tag_count` | 0.000 | 0 | tag_count=0 · tags=[] · desc_len=128 |
| `text_exclaim_density` | 0.000 | 147 | exclaims=0 · density_per_100=0.0 |
| `text_length` | 0.000 | 128 | desc_len=128 · title_len=18 |

**缺失 1 个**（样本不足或数据源限制，未参与打分）：

- `comment_like_rate` —— 7 条评论点赞全为 0 —— 疑似匿名态未填充该字段，不作为刷评证据

## 判定过程（规则逐条求值）

| 规则 | 动作 | 值 | 权重 | 贡献 | 说明 |
|---|---|---:|---:|---:|---|
| `ad_gate` | veto | 0.000 | 0.00 | 0.0000 | is_ad=0.000 < 0.85 |
| `risk` | contribute | 0.050 | 0.35 | 0.0175 |  |
| `exaggeration` | contribute | 0.207 | 0.30 | 0.0620 |  |
| `is_ad` | contribute | 0.110 | 0.25 | 0.0275 |  |
| `is_cta` | contribute | 0.070 | 0.10 | 0.0070 |  |
| `l2_stats` | flag | 0.154 | 0.00 | 0.0000 | l2_mean=0.154（仅记录，不计分） |

> 命中 veto 的规则会直接把总分拉满，后续规则不再计入；
> `flag` 动作只记录不计分（如 L2 统计信号）。


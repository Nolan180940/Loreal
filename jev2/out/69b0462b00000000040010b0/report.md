# jev2 单篇判定：`69b0462b00000000040010b0`

> 敏感肌不能用

## 结论

| 项 | 值 |
|---|---|
| 总分 | **0.2630** |
| 档位 | **低风险** |
| run_id | `20261011-141239-304fd6` |
| config_hash | `efe851c89c90` |
| 模型 | `jev-1.13` |
| 规则集 | `default` |
| 判定时间 | 2026-10-11T14:12:43 |
| 耗时 | 837 ms |

## 笔记

| 项 | 值 |
|---|---|
| 标题 | 敏感肌不能用 |
| 作者 | JoJo |
| 点赞 | 411 |
| 评论声明 | 332 |
| 评论实得 | 20 |
| 图片 | 1 张 |

## 语义维度（jev-1.13）

| 维度 | 风险值 | 置信度 | 题型 |
|---|---:|---:|---|
| `exaggeration` | 0.767 | 0.30 | score |
| `is_cta` | 0.140 | — | noul |
| `has_risk` | 0.040 | — | noul |
| `is_ad` | 0.020 | — | noul |

## 统计信号

| 信号 | 风险值 | n | 详情 |
|---|---:|---:|---|
| `like_comment_ratio` | 0.047 | 1 | ratio=1.24 · liked=411 · comment_count=332 |
| `text_exclaim_density` | 0.020 | 144 | exclaims=1 · density_per_100=0.69 |
| `author_reply_ratio` | 0.000 | 20 | author_comments=4 · ratio=0.2 |
| `comment_len_iqr` | 0.000 | 20 | iqr=27.5 |
| `comment_len_mean` | 0.000 | 20 | mean=38.5 |
| `comment_len_sd` | 0.000 | 20 | sd=62.24 · mean=38.5 · min_len=3 · max_len=296 |
| `comment_time_span` | 0.000 | 20 | span_minutes=35899.4 · first_ms=1773162461000 · last_ms=1775316425000 |
| `cta_lexicon` | 0.000 | 0 | density_per_100=0.0 · strong=[] · weak=[] |
| `ip_entropy` | 0.000 | 20 | entropy=0.9585 · distinct=10 |
| `ip_top1_ratio` | 0.000 | 20 | top1=0.2 · top1_ip=云南 · distinct=10 |
| `low_effort_ratio` | 0.000 | 20 | low_effort=3 · ratio=0.15 |
| `structure_markers` | 0.000 | 0 | marker_count=0 · markers=[] |
| `sub_reply_ratio` | 0.000 | 20 | replies=15 · ratio=0.75 |
| `tag_count` | 0.000 | 1 | tag_count=1 · tags=('薇诺娜特护霜',) · desc_len=137 |
| `text_length` | 0.000 | 137 | desc_len=137 · title_len=6 |

**缺失 1 个**（样本不足或数据源限制，未参与打分）：

- `comment_like_rate` —— 20 条评论点赞全为 0 —— 疑似匿名态未填充该字段，不作为刷评证据

## 判定过程（规则逐条求值）

| 规则 | 动作 | 值 | 权重 | 贡献 | 说明 |
|---|---|---:|---:|---:|---|
| `ad_gate` | veto | 0.000 | 0.00 | 0.0000 | is_ad=0.000 < 0.85 |
| `risk` | contribute | 0.040 | 0.35 | 0.0140 |  |
| `exaggeration` | contribute | 0.767 | 0.30 | 0.2300 |  |
| `is_ad` | contribute | 0.020 | 0.25 | 0.0050 |  |
| `is_cta` | contribute | 0.140 | 0.10 | 0.0140 |  |
| `l2_stats` | flag | 0.004 | 0.00 | 0.0000 | l2_mean=0.004（仅记录，不计分） |

> 命中 veto 的规则会直接把总分拉满，后续规则不再计入；
> `flag` 动作只记录不计分（如 L2 统计信号）。


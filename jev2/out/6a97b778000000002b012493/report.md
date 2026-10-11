# jev2 单篇判定：`6a97b778000000002b012493`

> 业内人锐评薇诺娜特护霜（无废话）

## 结论

| 项 | 值 |
|---|---|
| 总分 | **0.2860** |
| 档位 | **低风险** |
| run_id | `20261011-141239-304fd6` |
| config_hash | `efe851c89c90` |
| 模型 | `jev-1.13` |
| 规则集 | `default` |
| 判定时间 | 2026-10-11T14:13:01 |
| 耗时 | 1099 ms |

## 笔记

| 项 | 值 |
|---|---|
| 标题 | 业内人锐评薇诺娜特护霜（无废话） |
| 作者 | 迷人的金子 |
| 点赞 | 1249 |
| 评论声明 | 102 |
| 评论实得 | 13 |
| 图片 | 7 张 |

## 语义维度（jev-1.13）

| 维度 | 风险值 | 置信度 | 题型 |
|---|---:|---:|---|
| `has_risk` | 0.420 | — | noul |
| `is_ad` | 0.300 | — | noul |
| `exaggeration` | 0.167 | 0.50 | score |
| `is_cta` | 0.140 | — | noul |

## 统计信号

| 信号 | 风险值 | n | 详情 |
|---|---:|---:|---|
| `ip_entropy` | 1.000 | 13 | entropy=0.7193 · distinct=3 |
| `ip_top1_ratio` | 0.974 | 13 | top1=0.692 · top1_ip=北京 · distinct=3 |
| `author_reply_ratio` | 0.846 | 13 | author_comments=6 · ratio=0.462 |
| `like_comment_ratio` | 0.329 | 1 | ratio=12.25 · liked=1249 · comment_count=102 |
| `tag_count` | 0.286 | 7 | tag_count=7 · tags=('薇诺娜特护霜', '修护面霜', '敏感肌面霜', '敏感肌', '面霜', '薇诺娜') · d |
| `comment_len_iqr` | 0.000 | 13 | iqr=31.0 |
| `comment_len_mean` | 0.000 | 13 | mean=41.1 |
| `comment_len_sd` | 0.000 | 13 | sd=33.11 · mean=41.1 · min_len=4 · max_len=121 |
| `comment_time_span` | 0.000 | 13 | span_minutes=47360.0 · first_ms=1788345963000 · last_ms=1791187564000 |
| `cta_lexicon` | 0.000 | 0 | density_per_100=0.0 · strong=[] · weak=[] |
| `low_effort_ratio` | 0.000 | 13 | low_effort=1 · ratio=0.077 |
| `structure_markers` | 0.000 | 0 | marker_count=0 · markers=[] |
| `sub_reply_ratio` | 0.000 | 13 | replies=8 · ratio=0.615 |
| `text_exclaim_density` | 0.000 | 206 | exclaims=0 · density_per_100=0.0 |
| `text_length` | 0.000 | 189 | desc_len=189 · title_len=16 |

**缺失 1 个**（样本不足或数据源限制，未参与打分）：

- `comment_like_rate` —— 13 条评论点赞全为 0 —— 疑似匿名态未填充该字段，不作为刷评证据

## 判定过程（规则逐条求值）

| 规则 | 动作 | 值 | 权重 | 贡献 | 说明 |
|---|---|---:|---:|---:|---|
| `ad_gate` | veto | 0.000 | 0.00 | 0.0000 | is_ad=0.000 < 0.85 |
| `risk` | contribute | 0.420 | 0.35 | 0.1470 |  |
| `exaggeration` | contribute | 0.167 | 0.30 | 0.0500 |  |
| `is_ad` | contribute | 0.300 | 0.25 | 0.0750 |  |
| `is_cta` | contribute | 0.140 | 0.10 | 0.0140 |  |
| `l2_stats` | flag | 0.229 | 0.00 | 0.0000 | l2_mean=0.229（仅记录，不计分） |

> 命中 veto 的规则会直接把总分拉满，后续规则不再计入；
> `flag` 动作只记录不计分（如 L2 统计信号）。


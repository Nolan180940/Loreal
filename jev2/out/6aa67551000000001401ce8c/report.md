# jev2 单篇判定：`6aa67551000000001401ce8c`

> 目前没发现任何更好的面霜

## 结论

| 项 | 值 |
|---|---|
| 总分 | **0.3065** |
| 档位 | **中风险** |
| run_id | `20261011-141239-304fd6` |
| config_hash | `efe851c89c90` |
| 模型 | `jev-1.13` |
| 规则集 | `default` |
| 判定时间 | 2026-10-11T14:13:04 |
| 耗时 | 773 ms |

## 笔记

| 项 | 值 |
|---|---|
| 标题 | 目前没发现任何更好的面霜 |
| 作者 | 阿仍的（不）健康生活记录 |
| 点赞 | 759 |
| 评论声明 | 342 |
| 评论实得 | 20 |
| 图片 | 1 张 |

## 语义维度（jev-1.13）

| 维度 | 风险值 | 置信度 | 题型 |
|---|---:|---:|---|
| `exaggeration` | 0.480 | 0.54 | score |
| `has_risk` | 0.400 | — | noul |
| `is_ad` | 0.070 | — | noul |
| `is_cta` | 0.050 | — | noul |

## 统计信号

| 信号 | 风险值 | n | 详情 |
|---|---:|---:|---|
| `low_effort_ratio` | 0.111 | 20 | low_effort=7 · ratio=0.35 |
| `like_comment_ratio` | 0.082 | 1 | ratio=2.22 · liked=759 · comment_count=342 |
| `comment_time_span` | 0.048 | 20 | span_minutes=15722.9 · first_ms=1789460880000 · last_ms=1790404251000 |
| `author_reply_ratio` | 0.000 | 20 | author_comments=2 · ratio=0.1 |
| `comment_len_iqr` | 0.000 | 20 | iqr=24.75 |
| `comment_len_mean` | 0.000 | 20 | mean=24.1 |
| `comment_len_sd` | 0.000 | 20 | sd=17.36 · mean=24.1 · min_len=5 · max_len=62 |
| `cta_lexicon` | 0.000 | 0 | density_per_100=0.0 · strong=[] · weak=[] |
| `ip_entropy` | 0.000 | 20 | entropy=0.9595 · distinct=9 |
| `ip_top1_ratio` | 0.000 | 20 | top1=0.25 · top1_ip=河南 · distinct=9 |
| `structure_markers` | 0.000 | 0 | marker_count=0 · markers=[] |
| `sub_reply_ratio` | 0.000 | 20 | replies=15 · ratio=0.75 |
| `tag_count` | 0.000 | 0 | tag_count=0 · tags=() · desc_len=163 |
| `text_exclaim_density` | 0.000 | 176 | exclaims=0 · density_per_100=0.0 |
| `text_length` | 0.000 | 163 | desc_len=163 · title_len=12 |

**缺失 1 个**（样本不足或数据源限制，未参与打分）：

- `comment_like_rate` —— 20 条评论点赞全为 0 —— 疑似匿名态未填充该字段，不作为刷评证据

## 判定过程（规则逐条求值）

| 规则 | 动作 | 值 | 权重 | 贡献 | 说明 |
|---|---|---:|---:|---:|---|
| `ad_gate` | veto | 0.000 | 0.00 | 0.0000 | is_ad=0.000 < 0.85 |
| `risk` | contribute | 0.400 | 0.35 | 0.1400 |  |
| `exaggeration` | contribute | 0.480 | 0.30 | 0.1440 |  |
| `is_ad` | contribute | 0.070 | 0.25 | 0.0175 |  |
| `is_cta` | contribute | 0.050 | 0.10 | 0.0050 |  |
| `l2_stats` | flag | 0.016 | 0.00 | 0.0000 | l2_mean=0.016（仅记录，不计分） |

> 命中 veto 的规则会直接把总分拉满，后续规则不再计入；
> `flag` 动作只记录不计分（如 L2 统计信号）。


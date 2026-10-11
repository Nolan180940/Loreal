# jev2 单篇判定：`6a35d622000000001003c523`

> 空瓶︳兰蔻超修小黑瓶115ml

## 结论

| 项 | 值 |
|---|---|
| 总分 | **0.1170** |
| 档位 | **低风险** |
| run_id | `20261011-141239-304fd6` |
| config_hash | `efe851c89c90` |
| 模型 | `jev-1.13` |
| 规则集 | `default` |
| 判定时间 | 2026-10-11T14:12:52 |
| 耗时 | 986 ms |

## 笔记

| 项 | 值 |
|---|---|
| 标题 | 空瓶︳兰蔻超修小黑瓶115ml |
| 作者 | 小小梨🍐 |
| 点赞 | 56 |
| 评论声明 | 43 |
| 评论实得 | 16 |
| 图片 | 1 张 |

## 语义维度（jev-1.13）

| 维度 | 风险值 | 置信度 | 题型 |
|---|---:|---:|---|
| `exaggeration` | 0.317 | 0.59 | score |
| `is_cta` | 0.040 | — | noul |
| `is_ad` | 0.030 | — | noul |
| `has_risk` | 0.030 | — | noul |

## 统计信号

| 信号 | 风险值 | n | 详情 |
|---|---:|---:|---|
| `comment_len_iqr` | 0.594 | 16 | iqr=10.5 |
| `comment_len_mean` | 0.250 | 16 | mean=20.2 |
| `like_comment_ratio` | 0.050 | 1 | ratio=1.3 · liked=56 · comment_count=43 |
| `author_reply_ratio` | 0.000 | 16 | author_comments=3 · ratio=0.188 |
| `comment_len_sd` | 0.000 | 16 | sd=16.01 · mean=20.2 · min_len=4 · max_len=66 |
| `comment_time_span` | 0.000 | 16 | span_minutes=158869.4 · first_ms=1781915616000 · last_ms=1791447777000 |
| `cta_lexicon` | 0.000 | 0 | density_per_100=0.0 · strong=[] · weak=[] |
| `ip_entropy` | 0.000 | 16 | entropy=0.9641 · distinct=10 |
| `ip_top1_ratio` | 0.000 | 16 | top1=0.188 · top1_ip=四川 · distinct=10 |
| `low_effort_ratio` | 0.000 | 16 | low_effort=3 · ratio=0.188 |
| `structure_markers` | 0.000 | 0 | marker_count=0 · markers=[] |
| `sub_reply_ratio` | 0.000 | 16 | replies=11 · ratio=0.688 |
| `tag_count` | 0.000 | 0 | tag_count=0 · tags=() · desc_len=72 |
| `text_exclaim_density` | 0.000 | 88 | exclaims=0 · density_per_100=0.0 |
| `text_length` | 0.000 | 72 | desc_len=72 · title_len=15 |

**缺失 1 个**（样本不足或数据源限制，未参与打分）：

- `comment_like_rate` —— 16 条评论点赞全为 0 —— 疑似匿名态未填充该字段，不作为刷评证据

## 判定过程（规则逐条求值）

| 规则 | 动作 | 值 | 权重 | 贡献 | 说明 |
|---|---|---:|---:|---:|---|
| `ad_gate` | veto | 0.000 | 0.00 | 0.0000 | is_ad=0.000 < 0.85 |
| `risk` | contribute | 0.030 | 0.35 | 0.0105 |  |
| `exaggeration` | contribute | 0.317 | 0.30 | 0.0950 |  |
| `is_ad` | contribute | 0.030 | 0.25 | 0.0075 |  |
| `is_cta` | contribute | 0.040 | 0.10 | 0.0040 |  |
| `l2_stats` | flag | 0.060 | 0.00 | 0.0000 | l2_mean=0.060（仅记录，不计分） |

> 命中 veto 的规则会直接把总分拉满，后续规则不再计入；
> `flag` 动作只记录不计分（如 L2 统计信号）。


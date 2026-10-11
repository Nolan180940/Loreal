# jev2 单篇判定：`6a12d06d000000000702b6ec`

> 兰蔻小黑瓶精华价格

## 结论

| 项 | 值 |
|---|---|
| 总分 | **0.1235** |
| 档位 | **低风险** |
| run_id | `20261011-141239-304fd6` |
| config_hash | `efe851c89c90` |
| 模型 | `jev-1.13` |
| 规则集 | `default` |
| 判定时间 | 2026-10-11T14:12:49 |
| 耗时 | 931 ms |

## 笔记

| 项 | 值 |
|---|---|
| 标题 | 兰蔻小黑瓶精华价格 |
| 作者 | Lydia |
| 点赞 | 43 |
| 评论声明 | 37 |
| 评论实得 | 14 |
| 图片 | 2 张 |

## 语义维度（jev-1.13）

| 维度 | 风险值 | 置信度 | 题型 |
|---|---:|---:|---|
| `is_cta` | 0.930 | — | noul |
| `is_ad` | 0.080 | — | noul |
| `has_risk` | 0.030 | — | noul |
| `exaggeration` | 0.000 | 1.00 | score |

## 统计信号

| 信号 | 风险值 | n | 详情 |
|---|---:|---:|---|
| `comment_len_mean` | 0.538 | 14 | mean=15.9 |
| `comment_len_iqr` | 0.328 | 14 | iqr=14.75 |
| `low_effort_ratio` | 0.286 | 14 | low_effort=6 · ratio=0.429 |
| `like_comment_ratio` | 0.044 | 1 | ratio=1.16 · liked=43 · comment_count=37 |
| `author_reply_ratio` | 0.000 | 14 | author_comments=2 · ratio=0.143 |
| `comment_len_sd` | 0.000 | 14 | sd=15.14 · mean=15.9 · min_len=2 · max_len=51 |
| `comment_time_span` | 0.000 | 14 | span_minutes=191429.2 · first_ms=1779619071000 · last_ms=1791104822000 |
| `cta_lexicon` | 0.000 | 0 | density_per_100=0.0 · strong=[] · weak=[] |
| `ip_entropy` | 0.000 | 14 | entropy=0.9417 · distinct=9 |
| `ip_top1_ratio` | 0.000 | 14 | top1=0.214 · top1_ip=上海 · distinct=9 |
| `structure_markers` | 0.000 | 0 | marker_count=0 · markers=[] |
| `sub_reply_ratio` | 0.000 | 14 | replies=9 · ratio=0.643 |
| `tag_count` | 0.000 | 0 | tag_count=0 · tags=() · desc_len=50 |
| `text_exclaim_density` | 0.000 | 60 | exclaims=0 · density_per_100=0.0 |
| `text_length` | 0.000 | 50 | desc_len=50 · title_len=9 |

**缺失 1 个**（样本不足或数据源限制，未参与打分）：

- `comment_like_rate` —— 14 条评论点赞全为 0 —— 疑似匿名态未填充该字段，不作为刷评证据

## 判定过程（规则逐条求值）

| 规则 | 动作 | 值 | 权重 | 贡献 | 说明 |
|---|---|---:|---:|---:|---|
| `ad_gate` | veto | 0.000 | 0.00 | 0.0000 | is_ad=0.000 < 0.85 |
| `risk` | contribute | 0.030 | 0.35 | 0.0105 |  |
| `exaggeration` | contribute | 0.000 | 0.30 | 0.0000 |  |
| `is_ad` | contribute | 0.080 | 0.25 | 0.0200 |  |
| `is_cta` | contribute | 0.930 | 0.10 | 0.0930 |  |
| `l2_stats` | flag | 0.080 | 0.00 | 0.0000 | l2_mean=0.080（仅记录，不计分） |

> 命中 veto 的规则会直接把总分拉满，后续规则不再计入；
> `flag` 动作只记录不计分（如 L2 统计信号）。


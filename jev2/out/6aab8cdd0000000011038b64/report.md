# jev2 单篇判定：`6aab8cdd0000000011038b64`

> 对黑白绷带彻底祛魅

## 结论

| 项 | 值 |
|---|---|
| 总分 | **0.0380** |
| 档位 | **低风险** |
| run_id | `20261011-141239-304fd6` |
| config_hash | `efe851c89c90` |
| 模型 | `jev-1.13` |
| 规则集 | `default` |
| 判定时间 | 2026-10-11T14:13:05 |
| 耗时 | 847 ms |

## 笔记

| 项 | 值 |
|---|---|
| 标题 | 对黑白绷带彻底祛魅 |
| 作者 | 法律学姐Rebecca |
| 点赞 | 8 |
| 评论声明 | 3 |
| 评论实得 | 3 |
| 图片 | 1 张 |

## 语义维度（jev-1.13）

| 维度 | 风险值 | 置信度 | 题型 |
|---|---:|---:|---|
| `exaggeration` | 0.050 | 0.85 | score |
| `has_risk` | 0.040 | — | noul |
| `is_cta` | 0.040 | — | noul |
| `is_ad` | 0.020 | — | noul |

## 统计信号

| 信号 | 风险值 | n | 详情 |
|---|---:|---:|---|
| `low_effort_ratio` | 0.815 | 3 | low_effort=2 · ratio=0.667 |
| `comment_len_mean` | 0.778 | 3 | mean=12.3 |
| `comment_time_span` | 0.308 | 3 | span_minutes=4301.5 · first_ms=1791198681000 · last_ms=1791456769000 |
| `like_comment_ratio` | 0.096 | 1 | ratio=2.67 · liked=8 · comment_count=3 |
| `author_reply_ratio` | 0.000 | 3 | author_comments=0 · ratio=0.0 |
| `comment_len_sd` | 0.000 | 3 | sd=7.59 · mean=12.3 · min_len=6 · max_len=23 |
| `cta_lexicon` | 0.000 | 0 | density_per_100=0.0 · strong=[] · weak=[] |
| `ip_entropy` | 0.000 | 3 | entropy=1.0 · distinct=3 |
| `ip_top1_ratio` | 0.000 | 3 | top1=0.333 · top1_ip=广东 · distinct=3 |
| `structure_markers` | 0.000 | 0 | marker_count=0 · markers=[] |
| `tag_count` | 0.000 | 0 | tag_count=0 · tags=() · desc_len=210 |
| `text_exclaim_density` | 0.000 | 220 | exclaims=0 · density_per_100=0.0 |
| `text_length` | 0.000 | 210 | desc_len=210 · title_len=9 |

**缺失 3 个**（样本不足或数据源限制，未参与打分）：

- `comment_len_iqr` —— 评论 3 条 < 4，IQR 无意义
- `comment_like_rate` —— 评论 3 条 < 5
- `sub_reply_ratio` —— 评论 3 条 < 5，比值不稳

## 判定过程（规则逐条求值）

| 规则 | 动作 | 值 | 权重 | 贡献 | 说明 |
|---|---|---:|---:|---:|---|
| `ad_gate` | veto | 0.000 | 0.00 | 0.0000 | is_ad=0.000 < 0.85 |
| `risk` | contribute | 0.040 | 0.35 | 0.0140 |  |
| `exaggeration` | contribute | 0.050 | 0.30 | 0.0150 |  |
| `is_ad` | contribute | 0.020 | 0.25 | 0.0050 |  |
| `is_cta` | contribute | 0.040 | 0.10 | 0.0040 |  |
| `l2_stats` | flag | 0.154 | 0.00 | 0.0000 | l2_mean=0.154（仅记录，不计分） |

> 命中 veto 的规则会直接把总分拉满，后续规则不再计入；
> `flag` 动作只记录不计分（如 L2 统计信号）。


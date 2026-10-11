# jev2 单篇判定：`693abce3000000001e03b9bd`

> AGE面霜快空瓶了，聊下使用感受

## 结论

| 项 | 值 |
|---|---|
| 总分 | **0.0945** |
| 档位 | **低风险** |
| run_id | `20261011-141239-304fd6` |
| config_hash | `efe851c89c90` |
| 模型 | `jev-1.13` |
| 规则集 | `default` |
| 判定时间 | 2026-10-11T14:12:41 |
| 耗时 | 799 ms |

## 笔记

| 项 | 值 |
|---|---|
| 标题 | AGE面霜快空瓶了，聊下使用感受 |
| 作者 | 飘来飘去hba |
| 点赞 | 1050 |
| 评论声明 | 272 |
| 评论实得 | 20 |
| 图片 | 1 张 |

## 语义维度（jev-1.13）

| 维度 | 风险值 | 置信度 | 题型 |
|---|---:|---:|---|
| `has_risk` | 0.180 | — | noul |
| `is_ad` | 0.050 | — | noul |
| `exaggeration` | 0.050 | 0.85 | score |
| `is_cta` | 0.040 | — | noul |

## 统计信号

| 信号 | 风险值 | n | 详情 |
|---|---:|---:|---|
| `like_comment_ratio` | 0.134 | 1 | ratio=3.86 · liked=1050 · comment_count=272 |
| `author_reply_ratio` | 0.000 | 20 | author_comments=4 · ratio=0.2 |
| `comment_len_iqr` | 0.000 | 20 | iqr=22.0 |
| `comment_len_mean` | 0.000 | 20 | mean=26.0 |
| `comment_len_sd` | 0.000 | 20 | sd=22.02 · mean=26.0 · min_len=6 · max_len=85 |
| `comment_time_span` | 0.000 | 20 | span_minutes=156816.4 · first_ms=1765683634000 · last_ms=1775092616000 |
| `cta_lexicon` | 0.000 | 0 | density_per_100=0.0 · strong=[] · weak=[] |
| `ip_entropy` | 0.000 | 20 | entropy=0.9343 · distinct=10 |
| `ip_top1_ratio` | 0.000 | 20 | top1=0.25 · top1_ip=上海 · distinct=10 |
| `low_effort_ratio` | 0.000 | 20 | low_effort=5 · ratio=0.25 |
| `structure_markers` | 0.000 | 0 | marker_count=0 · markers=[] |
| `sub_reply_ratio` | 0.000 | 20 | replies=15 · ratio=0.75 |
| `tag_count` | 0.000 | 5 | tag_count=5 · tags=('干皮面霜', '面霜推荐', '空瓶记', '面霜分享', '使用感受') · desc_len= |
| `text_exclaim_density` | 0.000 | 396 | exclaims=0 · density_per_100=0.0 |
| `text_length` | 0.000 | 379 | desc_len=379 · title_len=16 |

**缺失 1 个**（样本不足或数据源限制，未参与打分）：

- `comment_like_rate` —— 20 条评论点赞全为 0 —— 疑似匿名态未填充该字段，不作为刷评证据

## 判定过程（规则逐条求值）

| 规则 | 动作 | 值 | 权重 | 贡献 | 说明 |
|---|---|---:|---:|---:|---|
| `ad_gate` | veto | 0.000 | 0.00 | 0.0000 | is_ad=0.000 < 0.85 |
| `risk` | contribute | 0.180 | 0.35 | 0.0630 |  |
| `exaggeration` | contribute | 0.050 | 0.30 | 0.0150 |  |
| `is_ad` | contribute | 0.050 | 0.25 | 0.0125 |  |
| `is_cta` | contribute | 0.040 | 0.10 | 0.0040 |  |
| `l2_stats` | flag | 0.009 | 0.00 | 0.0000 | l2_mean=0.009（仅记录，不计分） |

> 命中 veto 的规则会直接把总分拉满，后续规则不再计入；
> `flag` 动作只记录不计分（如 L2 统计信号）。


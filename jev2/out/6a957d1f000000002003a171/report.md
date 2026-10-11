# jev2 单篇判定：`6a957d1f000000002003a171`

> 此物对烂脸的杀伤力为100000%！！

## 结论

| 项 | 值 |
|---|---|
| 总分 | **0.8610** |
| 档位 | **高风险** |
| run_id | `20261011-141239-304fd6` |
| config_hash | `efe851c89c90` |
| 模型 | `jev-1.13` |
| 规则集 | `default` |
| 判定时间 | 2026-10-11T14:13:00 |
| 耗时 | 750 ms |

## 笔记

| 项 | 值 |
|---|---|
| 标题 | 此物对烂脸的杀伤力为100000%！！ |
| 作者 | 挖宝小孟 |
| 点赞 | 1099 |
| 评论声明 | 115 |
| 评论实得 | 9 |
| 图片 | 4 张 |

## 语义维度（jev-1.13）

| 维度 | 风险值 | 置信度 | 题型 |
|---|---:|---:|---|
| `exaggeration` | 0.987 | 0.96 | score |
| `has_risk` | 0.860 | — | noul |
| `is_cta` | 0.790 | — | noul |
| `is_ad` | 0.740 | — | noul |

## 统计信号

| 信号 | 风险值 | n | 详情 |
|---|---:|---:|---|
| `ip_entropy` | 1.000 | 9 | entropy=0.7233 · distinct=4 |
| `comment_len_mean` | 0.985 | 9 | mean=9.2 |
| `ip_top1_ratio` | 0.889 | 9 | top1=0.667 · top1_ip=浙江 · distinct=4 |
| `comment_len_iqr` | 0.625 | 9 | iqr=10.0 |
| `author_reply_ratio` | 0.333 | 9 | author_comments=3 · ratio=0.333 |
| `tag_count` | 0.286 | 7 | tag_count=7 · tags=('薇诺娜特护霜', '修护面霜', '敏感肌面霜', '敏感肌', '面霜', '薇诺娜') · d |
| `like_comment_ratio` | 0.277 | 1 | ratio=9.56 · liked=1099 · comment_count=115 |
| `comment_len_sd` | 0.227 | 9 | sd=5.86 · mean=9.2 · min_len=2 · max_len=19 |
| `text_exclaim_density` | 0.195 | 391 | exclaims=6 · density_per_100=1.53 |
| `low_effort_ratio` | 0.074 | 9 | low_effort=3 · ratio=0.333 |
| `comment_time_span` | 0.000 | 9 | span_minutes=55344.4 · first_ms=1788238728000 · last_ms=1791559390000 |
| `cta_lexicon` | 0.000 | 0 | density_per_100=0.0 · strong=[] · weak=[] |
| `structure_markers` | 0.000 | 0 | marker_count=0 · markers=[] |
| `sub_reply_ratio` | 0.000 | 9 | replies=4 · ratio=0.444 |
| `text_length` | 0.000 | 371 | desc_len=371 · title_len=19 |

**缺失 1 个**（样本不足或数据源限制，未参与打分）：

- `comment_like_rate` —— 9 条评论点赞全为 0 —— 疑似匿名态未填充该字段，不作为刷评证据

## 判定过程（规则逐条求值）

| 规则 | 动作 | 值 | 权重 | 贡献 | 说明 |
|---|---|---:|---:|---:|---|
| `ad_gate` | veto | 0.000 | 0.00 | 0.0000 | is_ad=0.000 < 0.85 |
| `risk` | contribute | 0.860 | 0.35 | 0.3010 |  |
| `exaggeration` | contribute | 0.987 | 0.30 | 0.2960 |  |
| `is_ad` | contribute | 0.740 | 0.25 | 0.1850 |  |
| `is_cta` | contribute | 0.790 | 0.10 | 0.0790 |  |
| `l2_stats` | flag | 0.326 | 0.00 | 0.0000 | l2_mean=0.326（仅记录，不计分） |

> 命中 veto 的规则会直接把总分拉满，后续规则不再计入；
> `flag` 动作只记录不计分（如 L2 统计信号）。


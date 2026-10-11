# jev2 单篇判定：`6abc7ee900000000180116a8`

> 锐评雅诗兰黛全修小棕瓶修护抗老逻辑

## 结论

| 项 | 值 |
|---|---|
| 总分 | **0.5559** |
| 档位 | **中风险** |
| run_id | `20261011-141239-304fd6` |
| config_hash | `efe851c89c90` |
| 模型 | `jev-1.13` |
| 规则集 | `default` |
| 判定时间 | 2026-10-11T14:13:10 |
| 耗时 | 782 ms |

## 笔记

| 项 | 值 |
|---|---|
| 标题 | 锐评雅诗兰黛全修小棕瓶修护抗老逻辑 |
| 作者 | 懂成分的甄嬛（活人版） |
| 点赞 | 629 |
| 评论声明 | 19 |
| 评论实得 | 10 |
| 图片 | 6 张 |

## 语义维度（jev-1.13）

| 维度 | 风险值 | 置信度 | 题型 |
|---|---:|---:|---|
| `is_ad` | 0.720 | — | noul |
| `exaggeration` | 0.633 | 0.82 | score |
| `has_risk` | 0.520 | — | noul |
| `is_cta` | 0.040 | — | noul |

## 统计信号

| 信号 | 风险值 | n | 详情 |
|---|---:|---:|---|
| `author_reply_ratio` | 1.000 | 10 | author_comments=5 · ratio=0.5 |
| `ip_entropy` | 0.961 | 10 | entropy=0.7855 · distinct=4 |
| `comment_len_iqr` | 0.891 | 10 | iqr=5.75 |
| `comment_len_mean` | 0.760 | 10 | mean=12.6 |
| `tag_count` | 0.714 | 10 | tag_count=10 · tags=('雅诗兰黛全修小棕瓶', '雅诗兰黛小棕瓶', '雅诗兰黛精华', '修护精华', '秋冬护肤', |
| `ip_top1_ratio` | 0.667 | 10 | top1=0.6 · top1_ip=湖北 · distinct=4 |
| `comment_len_sd` | 0.589 | 10 | sd=4.05 · mean=12.6 · min_len=5 · max_len=18 |
| `like_comment_ratio` | 0.570 | 1 | ratio=33.11 · liked=629 · comment_count=19 |
| `comment_time_span` | 0.154 | 10 | span_minutes=9251.4 · first_ms=1790750389000 · last_ms=1791305471000 |
| `cta_lexicon` | 0.000 | 0 | density_per_100=0.0 · strong=[] · weak=[] |
| `low_effort_ratio` | 0.000 | 10 | low_effort=1 · ratio=0.1 |
| `structure_markers` | 0.000 | 0 | marker_count=0 · markers=[] |
| `sub_reply_ratio` | 0.000 | 10 | replies=5 · ratio=0.5 |
| `text_exclaim_density` | 0.000 | 352 | exclaims=1 · density_per_100=0.28 |
| `text_length` | 0.000 | 334 | desc_len=334 · title_len=17 |

**缺失 1 个**（样本不足或数据源限制，未参与打分）：

- `comment_like_rate` —— 10 条评论点赞全为 0 —— 疑似匿名态未填充该字段，不作为刷评证据

## 判定过程（规则逐条求值）

| 规则 | 动作 | 值 | 权重 | 贡献 | 说明 |
|---|---|---:|---:|---:|---|
| `ad_gate` | veto | 0.000 | 0.00 | 0.0000 | is_ad=0.000 < 0.85 |
| `risk` | contribute | 0.520 | 0.35 | 0.1820 |  |
| `exaggeration` | contribute | 0.633 | 0.30 | 0.1899 |  |
| `is_ad` | contribute | 0.720 | 0.25 | 0.1800 |  |
| `is_cta` | contribute | 0.040 | 0.10 | 0.0040 |  |
| `l2_stats` | flag | 0.420 | 0.00 | 0.0000 | l2_mean=0.420（仅记录，不计分） |

> 命中 veto 的规则会直接把总分拉满，后续规则不再计入；
> `flag` 动作只记录不计分（如 L2 统计信号）。


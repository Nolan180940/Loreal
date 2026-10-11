# jev2 单篇判定：`6a942f820000000003029674`

> 免洗面膜真的敢天天糊脸上吗？

## 结论

| 项 | 值 |
|---|---|
| 总分 | **0.4605** |
| 档位 | **中风险** |
| run_id | `20261011-145225-bab771` |
| config_hash | `efe851c89c90` |
| 模型 | `jev-1.13` |
| 规则集 | `default` |
| 判定时间 | 2026-10-11T14:52:26 |
| 耗时 | 747 ms |

## 笔记

| 项 | 值 |
|---|---|
| 标题 | 免洗面膜真的敢天天糊脸上吗？ |
| 作者 | 挖宝小孟 |
| 点赞 | 1135 |
| 评论声明 | 119 |
| 评论实得 | 12 |
| 图片 | 3 张 |

## 语义维度（jev-1.13）

| 维度 | 风险值 | 置信度 | 题型 |
|---|---:|---:|---|
| `exaggeration` | 0.680 | 0.84 | score |
| `is_ad` | 0.510 | — | noul |
| `is_cta` | 0.310 | — | noul |
| `has_risk` | 0.280 | — | noul |

## 统计信号

| 信号 | 风险值 | n | 详情 |
|---|---:|---:|---|
| `comment_len_mean` | 0.806 | 12 | mean=11.9 |
| `comment_len_iqr` | 0.766 | 12 | iqr=7.75 |
| `tag_count` | 0.429 | 8 | tag_count=8 · tags=('佰草集仙草泥', '涂抹面膜', '熬夜', '抗老', '睡眠面膜', '面膜') · desc |
| `ip_entropy` | 0.336 | 12 | entropy=0.873 · distinct=7 |
| `author_reply_ratio` | 0.333 | 12 | author_comments=4 · ratio=0.333 |
| `text_exclaim_density` | 0.279 | 619 | exclaims=12 · density_per_100=1.94 |
| `like_comment_ratio` | 0.276 | 1 | ratio=9.54 · liked=1135 · comment_count=119 |
| `low_effort_ratio` | 0.259 | 12 | low_effort=5 · ratio=0.417 |
| `ip_top1_ratio` | 0.056 | 12 | top1=0.417 · top1_ip=浙江 · distinct=7 |
| `comment_len_sd` | 0.000 | 12 | sd=13.29 · mean=11.9 · min_len=2 · max_len=53 |
| `comment_time_span` | 0.000 | 12 | span_minutes=54694.3 · first_ms=1788167083000 · last_ms=1791448741000 |
| `cta_lexicon` | 0.000 | 0 | density_per_100=0.0 · strong=[] · weak=[] |
| `structure_markers` | 0.000 | 0 | marker_count=0 · markers=[] |
| `sub_reply_ratio` | 0.000 | 12 | replies=7 · ratio=0.583 |
| `text_length` | 0.000 | 604 | desc_len=604 · title_len=14 |

**缺失 1 个**（样本不足或数据源限制，未参与打分）：

- `comment_like_rate` —— 12 条评论点赞全为 0 —— 疑似匿名态未填充该字段，不作为刷评证据

## 判定过程（规则逐条求值）

| 规则 | 动作 | 值 | 权重 | 贡献 | 说明 |
|---|---|---:|---:|---:|---|
| `ad_gate` | veto | 0.000 | 0.00 | 0.0000 | is_ad=0.000 < 0.85 |
| `risk` | contribute | 0.280 | 0.35 | 0.0980 |  |
| `exaggeration` | contribute | 0.680 | 0.30 | 0.2040 |  |
| `is_ad` | contribute | 0.510 | 0.25 | 0.1275 |  |
| `is_cta` | contribute | 0.310 | 0.10 | 0.0310 |  |
| `l2_stats` | flag | 0.236 | 0.00 | 0.0000 | l2_mean=0.236（仅记录，不计分） |

> 命中 veto 的规则会直接把总分拉满，后续规则不再计入；
> `flag` 动作只记录不计分（如 L2 统计信号）。


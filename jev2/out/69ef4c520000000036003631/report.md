# jev2 单篇判定：`69ef4c520000000036003631`

> 薇诺娜特护霜你竟然背刺我

## 结论

| 项 | 值 |
|---|---|
| 总分 | **0.1325** |
| 档位 | **低风险** |
| run_id | `20261011-141239-304fd6` |
| config_hash | `efe851c89c90` |
| 模型 | `jev-1.13` |
| 规则集 | `default` |
| 判定时间 | 2026-10-11T14:12:45 |
| 耗时 | 887 ms |

## 笔记

| 项 | 值 |
|---|---|
| 标题 | 薇诺娜特护霜你竟然背刺我 |
| 作者 | 上班即退休 |
| 点赞 | 106 |
| 评论声明 | 24 |
| 评论实得 | 14 |
| 图片 | 3 张 |

## 语义维度（jev-1.13）

| 维度 | 风险值 | 置信度 | 题型 |
|---|---:|---:|---|
| `exaggeration` | 0.363 | 0.31 | score |
| `has_risk` | 0.040 | — | noul |
| `is_ad` | 0.030 | — | noul |
| `is_cta` | 0.020 | — | noul |

## 统计信号

| 信号 | 风险值 | n | 详情 |
|---|---:|---:|---|
| `text_exclaim_density` | 0.500 | 199 | exclaims=7 · density_per_100=3.52 |
| `comment_len_mean` | 0.452 | 14 | mean=17.2 |
| `comment_len_iqr` | 0.156 | 14 | iqr=17.5 |
| `like_comment_ratio` | 0.150 | 1 | ratio=4.42 · liked=106 · comment_count=24 |
| `author_reply_ratio` | 0.000 | 14 | author_comments=3 · ratio=0.214 |
| `comment_len_sd` | 0.000 | 14 | sd=12.18 · mean=17.2 · min_len=3 · max_len=43 |
| `comment_time_span` | 0.000 | 14 | span_minutes=234763.6 · first_ms=1777449114000 · last_ms=1791534933000 |
| `cta_lexicon` | 0.000 | 0 | density_per_100=0.0 · strong=[] · weak=[] |
| `ip_entropy` | 0.000 | 14 | entropy=0.9299 · distinct=7 |
| `ip_top1_ratio` | 0.000 | 14 | top1=0.286 · top1_ip=山东 · distinct=7 |
| `low_effort_ratio` | 0.000 | 14 | low_effort=4 · ratio=0.286 |
| `structure_markers` | 0.000 | 0 | marker_count=0 · markers=[] |
| `sub_reply_ratio` | 0.000 | 14 | replies=9 · ratio=0.643 |
| `tag_count` | 0.000 | 0 | tag_count=0 · tags=() · desc_len=186 |
| `text_length` | 0.000 | 186 | desc_len=186 · title_len=12 |

**缺失 1 个**（样本不足或数据源限制，未参与打分）：

- `comment_like_rate` —— 14 条评论点赞全为 0 —— 疑似匿名态未填充该字段，不作为刷评证据

## 判定过程（规则逐条求值）

| 规则 | 动作 | 值 | 权重 | 贡献 | 说明 |
|---|---|---:|---:|---:|---|
| `ad_gate` | veto | 0.000 | 0.00 | 0.0000 | is_ad=0.000 < 0.85 |
| `risk` | contribute | 0.040 | 0.35 | 0.0140 |  |
| `exaggeration` | contribute | 0.363 | 0.30 | 0.1090 |  |
| `is_ad` | contribute | 0.030 | 0.25 | 0.0075 |  |
| `is_cta` | contribute | 0.020 | 0.10 | 0.0020 |  |
| `l2_stats` | flag | 0.084 | 0.00 | 0.0000 | l2_mean=0.084（仅记录，不计分） |

> 命中 veto 的规则会直接把总分拉满，后续规则不再计入；
> `flag` 动作只记录不计分（如 L2 统计信号）。


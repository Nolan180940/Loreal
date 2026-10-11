# jev2 单篇判定：`69f962b3000000002301eb64`

> 兰蔻小黑瓶眼霜、不吹不黑说真话

## 结论

| 项 | 值 |
|---|---|
| 总分 | **0.0975** |
| 档位 | **低风险** |
| run_id | `20261011-141239-304fd6` |
| config_hash | `efe851c89c90` |
| 模型 | `jev-1.13` |
| 规则集 | `default` |
| 判定时间 | 2026-10-11T14:12:47 |
| 耗时 | 780 ms |

## 笔记

| 项 | 值 |
|---|---|
| 标题 | 兰蔻小黑瓶眼霜、不吹不黑说真话 |
| 作者 | 噜啦啦（恶语反弹） |
| 点赞 | 150 |
| 评论声明 | 93 |
| 评论实得 | 17 |
| 图片 | 2 张 |

## 语义维度（jev-1.13）

| 维度 | 风险值 | 置信度 | 题型 |
|---|---:|---:|---|
| `is_cta` | 0.450 | — | noul |
| `is_ad` | 0.090 | — | noul |
| `has_risk` | 0.060 | — | noul |
| `exaggeration` | 0.030 | 0.91 | score |

## 统计信号

| 信号 | 风险值 | n | 详情 |
|---|---:|---:|---|
| `author_reply_ratio` | 0.647 | 17 | author_comments=7 · ratio=0.412 |
| `ip_entropy` | 0.310 | 17 | entropy=0.8766 · distinct=7 |
| `like_comment_ratio` | 0.061 | 1 | ratio=1.61 · liked=150 · comment_count=93 |
| `ip_top1_ratio` | 0.039 | 17 | top1=0.412 · top1_ip=内蒙古 · distinct=7 |
| `comment_len_iqr` | 0.000 | 17 | iqr=45.0 |
| `comment_len_mean` | 0.000 | 17 | mean=42.4 |
| `comment_len_sd` | 0.000 | 17 | sd=39.3 · mean=42.4 · min_len=7 · max_len=149 |
| `comment_time_span` | 0.000 | 17 | span_minutes=202353.8 · first_ms=1779190531000 · last_ms=1791331761000 |
| `cta_lexicon` | 0.000 | 0 | density_per_100=0.0 · strong=[] · weak=[] |
| `low_effort_ratio` | 0.000 | 17 | low_effort=2 · ratio=0.118 |
| `structure_markers` | 0.000 | 2 | marker_count=2 · markers=['✅', '❌'] |
| `sub_reply_ratio` | 0.000 | 17 | replies=12 · ratio=0.706 |
| `tag_count` | 0.000 | 1 | tag_count=1 · tags=('兰蔻小黑瓶眼霜',) · desc_len=325 |
| `text_exclaim_density` | 0.000 | 341 | exclaims=1 · density_per_100=0.29 |
| `text_length` | 0.000 | 325 | desc_len=325 · title_len=15 |

**缺失 1 个**（样本不足或数据源限制，未参与打分）：

- `comment_like_rate` —— 17 条评论点赞全为 0 —— 疑似匿名态未填充该字段，不作为刷评证据

## 判定过程（规则逐条求值）

| 规则 | 动作 | 值 | 权重 | 贡献 | 说明 |
|---|---|---:|---:|---:|---|
| `ad_gate` | veto | 0.000 | 0.00 | 0.0000 | is_ad=0.000 < 0.85 |
| `risk` | contribute | 0.060 | 0.35 | 0.0210 |  |
| `exaggeration` | contribute | 0.030 | 0.30 | 0.0090 |  |
| `is_ad` | contribute | 0.090 | 0.25 | 0.0225 |  |
| `is_cta` | contribute | 0.450 | 0.10 | 0.0450 |  |
| `l2_stats` | flag | 0.070 | 0.00 | 0.0000 | l2_mean=0.070（仅记录，不计分） |

> 命中 veto 的规则会直接把总分拉满，后续规则不再计入；
> `flag` 动作只记录不计分（如 L2 统计信号）。


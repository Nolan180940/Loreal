# jev2 单篇判定：`69bd5426000000001f006b23`

> 修丽可的age面霜里面加了啥，涂起来一层白白的，跟素颜霜一样…

## 结论

| 项 | 值 |
|---|---|
| 总分 | **0.1300** |
| 档位 | **低风险** |
| run_id | `20261011-141239-304fd6` |
| config_hash | `efe851c89c90` |
| 模型 | `jev-1.13` |
| 规则集 | `default` |
| 判定时间 | 2026-10-11T14:12:43 |
| 耗时 | 768 ms |

## 笔记

| 项 | 值 |
|---|---|
| 标题 | 修丽可的age面霜里面加了啥，涂起来一层白白的，跟素颜霜一样… |
| 作者 | 🐯🐯 |
| 点赞 | 278 |
| 评论声明 | 278 |
| 评论实得 | 20 |
| 图片 | 1 张 |

## 语义维度（jev-1.13）

| 维度 | 风险值 | 置信度 | 题型 |
|---|---:|---:|---|
| `exaggeration` | 0.330 | 0.51 | score |
| `is_ad` | 0.060 | — | noul |
| `has_risk` | 0.040 | — | noul |
| `is_cta` | 0.020 | — | noul |

## 统计信号

| 信号 | 风险值 | n | 详情 |
|---|---:|---:|---|
| `comment_time_span` | 0.079 | 20 | span_minutes=13480.7 · first_ms=1774161904000 · last_ms=1774970745000 |
| `like_comment_ratio` | 0.038 | 1 | ratio=1.0 · liked=278 · comment_count=278 |
| `author_reply_ratio` | 0.000 | 20 | author_comments=3 · ratio=0.15 |
| `comment_len_iqr` | 0.000 | 20 | iqr=22.5 |
| `comment_len_mean` | 0.000 | 20 | mean=28.9 |
| `comment_len_sd` | 0.000 | 20 | sd=29.36 · mean=28.9 · min_len=6 · max_len=127 |
| `cta_lexicon` | 0.000 | 0 | density_per_100=0.0 · strong=[] · weak=[] |
| `ip_entropy` | 0.000 | 20 | entropy=0.9284 · distinct=10 |
| `ip_top1_ratio` | 0.000 | 20 | top1=0.2 · top1_ip=江苏 · distinct=10 |
| `low_effort_ratio` | 0.000 | 20 | low_effort=3 · ratio=0.15 |
| `structure_markers` | 0.000 | 0 | marker_count=0 · markers=[] |
| `sub_reply_ratio` | 0.000 | 20 | replies=15 · ratio=0.75 |
| `tag_count` | 0.000 | 1 | tag_count=1 · tags=('修丽可',) · desc_len=60 |
| `text_exclaim_density` | 0.000 | 92 | exclaims=0 · density_per_100=0.0 |
| `text_length` | 0.000 | 60 | desc_len=60 · title_len=31 |

**缺失 1 个**（样本不足或数据源限制，未参与打分）：

- `comment_like_rate` —— 20 条评论点赞全为 0 —— 疑似匿名态未填充该字段，不作为刷评证据

## 判定过程（规则逐条求值）

| 规则 | 动作 | 值 | 权重 | 贡献 | 说明 |
|---|---|---:|---:|---:|---|
| `ad_gate` | veto | 0.000 | 0.00 | 0.0000 | is_ad=0.000 < 0.85 |
| `risk` | contribute | 0.040 | 0.35 | 0.0140 |  |
| `exaggeration` | contribute | 0.330 | 0.30 | 0.0990 |  |
| `is_ad` | contribute | 0.060 | 0.25 | 0.0150 |  |
| `is_cta` | contribute | 0.020 | 0.10 | 0.0020 |  |
| `l2_stats` | flag | 0.008 | 0.00 | 0.0000 | l2_mean=0.008（仅记录，不计分） |

> 命中 veto 的规则会直接把总分拉满，后续规则不再计入；
> `flag` 动作只记录不计分（如 L2 统计信号）。


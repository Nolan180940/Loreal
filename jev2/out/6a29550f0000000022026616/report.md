# jev2 单篇判定：`6a29550f0000000022026616`

> 没人比它争议大｜自用repo

## 结论

| 项 | 值 |
|---|---|
| 总分 | **0.1380** |
| 档位 | **低风险** |
| run_id | `20261011-141239-304fd6` |
| config_hash | `efe851c89c90` |
| 模型 | `jev-1.13` |
| 规则集 | `default` |
| 判定时间 | 2026-10-11T14:12:51 |
| 耗时 | 736 ms |

## 笔记

| 项 | 值 |
|---|---|
| 标题 | 没人比它争议大｜自用repo |
| 作者 | 日常薯 |
| 点赞 | 999 |
| 评论声明 | 91 |
| 评论实得 | 19 |
| 图片 | 3 张 |

## 语义维度（jev-1.13）

| 维度 | 风险值 | 置信度 | 题型 |
|---|---:|---:|---|
| `exaggeration` | 0.187 | 0.56 | score |
| `is_ad` | 0.120 | — | noul |
| `has_risk` | 0.120 | — | noul |
| `is_cta` | 0.100 | — | noul |

## 统计信号

| 信号 | 风险值 | n | 详情 |
|---|---:|---:|---|
| `comment_len_mean` | 0.667 | 19 | mean=14.0 |
| `comment_len_iqr` | 0.500 | 19 | iqr=12.0 |
| `like_comment_ratio` | 0.305 | 1 | ratio=10.98 · liked=999 · comment_count=91 |
| `author_reply_ratio` | 0.000 | 19 | author_comments=0 · ratio=0.0 |
| `comment_len_sd` | 0.000 | 19 | sd=7.99 · mean=14.0 · min_len=2 · max_len=28 |
| `comment_time_span` | 0.000 | 19 | span_minutes=141193.3 · first_ms=1782042137000 · last_ms=1790513734000 |
| `cta_lexicon` | 0.000 | 0 | density_per_100=0.0 · strong=[] · weak=[] |
| `ip_entropy` | 0.000 | 19 | entropy=0.9748 · distinct=9 |
| `ip_top1_ratio` | 0.000 | 19 | top1=0.211 · top1_ip=上海 · distinct=9 |
| `low_effort_ratio` | 0.000 | 19 | low_effort=5 · ratio=0.263 |
| `structure_markers` | 0.000 | 0 | marker_count=0 · markers=[] |
| `sub_reply_ratio` | 0.000 | 19 | replies=14 · ratio=0.737 |
| `tag_count` | 0.000 | 5 | tag_count=5 · tags=('干皮护肤碎碎念', '好物推荐', '年度爱用', '薇诺娜', '以上仅代表个人使用感受') · |
| `text_exclaim_density` | 0.000 | 371 | exclaims=0 · density_per_100=0.0 |
| `text_length` | 0.000 | 356 | desc_len=356 · title_len=14 |

**缺失 1 个**（样本不足或数据源限制，未参与打分）：

- `comment_like_rate` —— 19 条评论点赞全为 0 —— 疑似匿名态未填充该字段，不作为刷评证据

## 判定过程（规则逐条求值）

| 规则 | 动作 | 值 | 权重 | 贡献 | 说明 |
|---|---|---:|---:|---:|---|
| `ad_gate` | veto | 0.000 | 0.00 | 0.0000 | is_ad=0.000 < 0.85 |
| `risk` | contribute | 0.120 | 0.35 | 0.0420 |  |
| `exaggeration` | contribute | 0.187 | 0.30 | 0.0560 |  |
| `is_ad` | contribute | 0.120 | 0.25 | 0.0300 |  |
| `is_cta` | contribute | 0.100 | 0.10 | 0.0100 |  |
| `l2_stats` | flag | 0.098 | 0.00 | 0.0000 | l2_mean=0.098（仅记录，不计分） |

> 命中 veto 的规则会直接把总分拉满，后续规则不再计入；
> `flag` 动作只记录不计分（如 L2 统计信号）。


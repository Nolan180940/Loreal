# jev2 单篇判定：`6abb030f000000001803b3e0`

> 今日快乐是雅诗兰黛小棕瓶给的❤️

## 结论

| 项 | 值 |
|---|---|
| 总分 | **0.3055** |
| 档位 | **中风险** |
| run_id | `20261011-141239-304fd6` |
| config_hash | `efe851c89c90` |
| 模型 | `jev-1.13` |
| 规则集 | `default` |
| 判定时间 | 2026-10-11T14:13:10 |
| 耗时 | 830 ms |

## 笔记

| 项 | 值 |
|---|---|
| 标题 | 今日快乐是雅诗兰黛小棕瓶给的❤️ |
| 作者 | 小胖杜 |
| 点赞 | 1276 |
| 评论声明 | 467 |
| 评论实得 | 10 |
| 图片 | 2 张 |

## 语义维度（jev-1.13）

| 维度 | 风险值 | 置信度 | 题型 |
|---|---:|---:|---|
| `is_ad` | 0.820 | — | noul |
| `is_cta` | 0.450 | — | noul |
| `has_risk` | 0.090 | — | noul |
| `exaggeration` | 0.080 | 0.76 | score |

## 统计信号

| 信号 | 风险值 | n | 详情 |
|---|---:|---:|---|
| `comment_len_iqr` | 0.969 | 10 | iqr=4.5 |
| `comment_len_mean` | 0.960 | 10 | mean=9.6 |
| `comment_len_sd` | 0.523 | 10 | sd=4.39 · mean=9.6 · min_len=4 · max_len=19 |
| `low_effort_ratio` | 0.444 | 10 | low_effort=5 · ratio=0.5 |
| `comment_time_span` | 0.345 | 10 | span_minutes=3577.9 · first_ms=1790650006000 · last_ms=1790864680000 |
| `cta_lexicon` | 0.332 | 4 | density_per_100=2.05 · strong=['领取', '掉落'] · weak=[] |
| `like_comment_ratio` | 0.099 | 1 | ratio=2.73 · liked=1276 · comment_count=467 |
| `author_reply_ratio` | 0.000 | 10 | author_comments=1 · ratio=0.1 |
| `ip_entropy` | 0.000 | 10 | entropy=0.9427 · distinct=7 |
| `ip_top1_ratio` | 0.000 | 10 | top1=0.3 · top1_ip=河南 · distinct=7 |
| `structure_markers` | 0.000 | 0 | marker_count=0 · markers=[] |
| `sub_reply_ratio` | 0.000 | 10 | replies=5 · ratio=0.5 |
| `tag_count` | 0.000 | 3 | tag_count=3 · tags=('惊喜盒子', '雅诗兰黛', '小棕瓶') · desc_len=164 |
| `text_exclaim_density` | 0.000 | 181 | exclaims=1 · density_per_100=0.55 |
| `text_length` | 0.000 | 164 | desc_len=164 · title_len=16 |

**缺失 1 个**（样本不足或数据源限制，未参与打分）：

- `comment_like_rate` —— 10 条评论点赞全为 0 —— 疑似匿名态未填充该字段，不作为刷评证据

## 判定过程（规则逐条求值）

| 规则 | 动作 | 值 | 权重 | 贡献 | 说明 |
|---|---|---:|---:|---:|---|
| `ad_gate` | veto | 0.000 | 0.00 | 0.0000 | is_ad=0.000 < 0.85 |
| `risk` | contribute | 0.090 | 0.35 | 0.0315 |  |
| `exaggeration` | contribute | 0.080 | 0.30 | 0.0240 |  |
| `is_ad` | contribute | 0.820 | 0.25 | 0.2050 |  |
| `is_cta` | contribute | 0.450 | 0.10 | 0.0450 |  |
| `l2_stats` | flag | 0.245 | 0.00 | 0.0000 | l2_mean=0.245（仅记录，不计分） |

> 命中 veto 的规则会直接把总分拉满，后续规则不再计入；
> `flag` 动作只记录不计分（如 L2 统计信号）。


# jev2 单篇判定：`6a72e8f500000000050288b1`

> 珂润面霜的贵替有啥啊

## 结论

| 项 | 值 |
|---|---|
| 总分 | **0.0700** |
| 档位 | **低风险** |
| run_id | `20261011-141239-304fd6` |
| config_hash | `efe851c89c90` |
| 模型 | `jev-1.13` |
| 规则集 | `default` |
| 判定时间 | 2026-10-11T14:12:58 |
| 耗时 | 874 ms |

## 笔记

| 项 | 值 |
|---|---|
| 标题 | 珂润面霜的贵替有啥啊 |
| 作者 | 虫子 |
| 点赞 | 11 |
| 评论声明 | 21 |
| 评论实得 | 9 |
| 图片 | 1 张 |

## 语义维度（jev-1.13）

| 维度 | 风险值 | 置信度 | 题型 |
|---|---:|---:|---|
| `exaggeration` | 0.120 | 0.64 | score |
| `is_ad` | 0.060 | — | noul |
| `is_cta` | 0.050 | — | noul |
| `has_risk` | 0.040 | — | noul |

## 统计信号

| 信号 | 风险值 | n | 详情 |
|---|---:|---:|---|
| `comment_len_mean` | 0.993 | 9 | mean=9.1 |
| `comment_len_iqr` | 0.688 | 9 | iqr=9.0 |
| `low_effort_ratio` | 0.568 | 9 | low_effort=5 · ratio=0.556 |
| `text_length` | 0.158 | 21 | desc_len=21 · title_len=10 |
| `comment_len_sd` | 0.026 | 9 | sd=6.87 · mean=9.1 · min_len=2 · max_len=24 |
| `like_comment_ratio` | 0.021 | 1 | ratio=0.52 · liked=11 · comment_count=21 |
| `author_reply_ratio` | 0.000 | 9 | author_comments=0 · ratio=0.0 |
| `comment_time_span` | 0.000 | 9 | span_minutes=58836.8 · first_ms=1785915816000 · last_ms=1789446025000 |
| `cta_lexicon` | 0.000 | 0 | density_per_100=0.0 · strong=[] · weak=[] |
| `ip_entropy` | 0.000 | 9 | entropy=0.9359 · distinct=6 |
| `ip_top1_ratio` | 0.000 | 9 | top1=0.333 · top1_ip=陕西 · distinct=6 |
| `structure_markers` | 0.000 | 0 | marker_count=0 · markers=[] |
| `sub_reply_ratio` | 0.000 | 9 | replies=4 · ratio=0.444 |
| `tag_count` | 0.000 | 2 | tag_count=2 · tags=('修护面霜', '保湿面霜') · desc_len=21 |
| `text_exclaim_density` | 0.000 | 32 | exclaims=0 · density_per_100=0.0 |

**缺失 1 个**（样本不足或数据源限制，未参与打分）：

- `comment_like_rate` —— 9 条评论点赞全为 0 —— 疑似匿名态未填充该字段，不作为刷评证据

## 判定过程（规则逐条求值）

| 规则 | 动作 | 值 | 权重 | 贡献 | 说明 |
|---|---|---:|---:|---:|---|
| `ad_gate` | veto | 0.000 | 0.00 | 0.0000 | is_ad=0.000 < 0.85 |
| `risk` | contribute | 0.040 | 0.35 | 0.0140 |  |
| `exaggeration` | contribute | 0.120 | 0.30 | 0.0360 |  |
| `is_ad` | contribute | 0.060 | 0.25 | 0.0150 |  |
| `is_cta` | contribute | 0.050 | 0.10 | 0.0050 |  |
| `l2_stats` | flag | 0.164 | 0.00 | 0.0000 | l2_mean=0.164（仅记录，不计分） |

> 命中 veto 的规则会直接把总分拉满，后续规则不再计入；
> `flag` 动作只记录不计分（如 L2 统计信号）。


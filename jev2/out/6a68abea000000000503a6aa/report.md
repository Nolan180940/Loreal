# jev2 单篇判定：`6a68abea000000000503a6aa`

> 面霜，你自由了

## 结论

| 项 | 值 |
|---|---|
| 总分 | **0.3165** |
| 档位 | **中风险** |
| run_id | `20261011-141239-304fd6` |
| config_hash | `efe851c89c90` |
| 模型 | `jev-1.13` |
| 规则集 | `default` |
| 判定时间 | 2026-10-11T14:12:56 |
| 耗时 | 733 ms |

## 笔记

| 项 | 值 |
|---|---|
| 标题 | 面霜，你自由了 |
| 作者 | 烟波致爽 |
| 点赞 | 157 |
| 评论声明 | 69 |
| 评论实得 | 19 |
| 图片 | 1 张 |

## 语义维度（jev-1.13）

| 维度 | 风险值 | 置信度 | 题型 |
|---|---:|---:|---|
| `exaggeration` | 0.577 | 0.69 | score |
| `has_risk` | 0.310 | — | noul |
| `is_ad` | 0.120 | — | noul |
| `is_cta` | 0.050 | — | noul |

## 统计信号

| 信号 | 风险值 | n | 详情 |
|---|---:|---:|---|
| `comment_len_iqr` | 0.531 | 19 | iqr=11.5 |
| `author_reply_ratio` | 0.474 | 19 | author_comments=7 · ratio=0.368 |
| `comment_len_mean` | 0.463 | 19 | mean=17.1 |
| `ip_entropy` | 0.198 | 19 | entropy=0.8922 · distinct=7 |
| `like_comment_ratio` | 0.083 | 1 | ratio=2.28 · liked=157 · comment_count=69 |
| `comment_len_sd` | 0.000 | 19 | sd=11.43 · mean=17.1 · min_len=2 · max_len=53 |
| `comment_time_span` | 0.000 | 19 | span_minutes=51820.6 · first_ms=1785244806000 · last_ms=1788354040000 |
| `cta_lexicon` | 0.000 | 0 | density_per_100=0.0 · strong=[] · weak=[] |
| `ip_top1_ratio` | 0.000 | 19 | top1=0.316 · top1_ip=江苏 · distinct=7 |
| `low_effort_ratio` | 0.000 | 19 | low_effort=3 · ratio=0.158 |
| `structure_markers` | 0.000 | 0 | marker_count=0 · markers=[] |
| `sub_reply_ratio` | 0.000 | 19 | replies=14 · ratio=0.737 |
| `tag_count` | 0.000 | 5 | tag_count=5 · tags=('遗憾', '后悔', '护肤', '珂润', '珂润面霜') · desc_len=257 |
| `text_exclaim_density` | 0.000 | 265 | exclaims=0 · density_per_100=0.0 |
| `text_length` | 0.000 | 257 | desc_len=257 · title_len=7 |

**缺失 1 个**（样本不足或数据源限制，未参与打分）：

- `comment_like_rate` —— 19 条评论点赞全为 0 —— 疑似匿名态未填充该字段，不作为刷评证据

## 判定过程（规则逐条求值）

| 规则 | 动作 | 值 | 权重 | 贡献 | 说明 |
|---|---|---:|---:|---:|---|
| `ad_gate` | veto | 0.000 | 0.00 | 0.0000 | is_ad=0.000 < 0.85 |
| `risk` | contribute | 0.310 | 0.35 | 0.1085 |  |
| `exaggeration` | contribute | 0.577 | 0.30 | 0.1730 |  |
| `is_ad` | contribute | 0.120 | 0.25 | 0.0300 |  |
| `is_cta` | contribute | 0.050 | 0.10 | 0.0050 |  |
| `l2_stats` | flag | 0.117 | 0.00 | 0.0000 | l2_mean=0.117（仅记录，不计分） |

> 命中 veto 的规则会直接把总分拉满，后续规则不再计入；
> `flag` 动作只记录不计分（如 L2 统计信号）。


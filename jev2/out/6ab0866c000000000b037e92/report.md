# jev2 单篇判定：`6ab0866c000000000b037e92`

> 珂润面霜踩雷

## 结论

| 项 | 值 |
|---|---|
| 总分 | **0.1405** |
| 档位 | **低风险** |
| run_id | `20261011-141239-304fd6` |
| config_hash | `efe851c89c90` |
| 模型 | `jev-1.13` |
| 规则集 | `default` |
| 判定时间 | 2026-10-11T14:13:06 |
| 耗时 | 725 ms |

## 笔记

| 项 | 值 |
|---|---|
| 标题 | 珂润面霜踩雷 |
| 作者 | 是我啊 |
| 点赞 | 17 |
| 评论声明 | 58 |
| 评论实得 | 17 |
| 图片 | 1 张 |

## 语义维度（jev-1.13）

| 维度 | 风险值 | 置信度 | 题型 |
|---|---:|---:|---|
| `exaggeration` | 0.403 | 0.39 | score |
| `is_cta` | 0.040 | — | noul |
| `has_risk` | 0.030 | — | noul |
| `is_ad` | 0.020 | — | noul |

## 统计信号

| 信号 | 风险值 | n | 详情 |
|---|---:|---:|---|
| `comment_len_iqr` | 0.812 | 17 | iqr=7.0 |
| `comment_len_mean` | 0.537 | 17 | mean=15.9 |
| `author_reply_ratio` | 0.412 | 17 | author_comments=6 · ratio=0.353 |
| `ip_entropy` | 0.312 | 17 | entropy=0.8763 · distinct=9 |
| `like_comment_ratio` | 0.012 | 1 | ratio=0.29 · liked=17 · comment_count=58 |
| `comment_len_sd` | 0.000 | 17 | sd=10.26 · mean=15.9 · min_len=2 · max_len=48 |
| `comment_time_span` | 0.000 | 17 | span_minutes=27369.4 · first_ms=1789960767000 · last_ms=1791602932000 |
| `cta_lexicon` | 0.000 | 0 | density_per_100=0.0 · strong=[] · weak=[] |
| `ip_top1_ratio` | 0.000 | 17 | top1=0.353 · top1_ip=日本 · distinct=9 |
| `low_effort_ratio` | 0.000 | 17 | low_effort=3 · ratio=0.176 |
| `structure_markers` | 0.000 | 0 | marker_count=0 · markers=[] |
| `sub_reply_ratio` | 0.000 | 17 | replies=12 · ratio=0.706 |
| `tag_count` | 0.000 | 4 | tag_count=4 · tags=('保湿面霜', '珂润', '雅漾', '护肤') · desc_len=249 |
| `text_exclaim_density` | 0.000 | 256 | exclaims=0 · density_per_100=0.0 |
| `text_length` | 0.000 | 249 | desc_len=249 · title_len=6 |

**缺失 1 个**（样本不足或数据源限制，未参与打分）：

- `comment_like_rate` —— 17 条评论点赞全为 0 —— 疑似匿名态未填充该字段，不作为刷评证据

## 判定过程（规则逐条求值）

| 规则 | 动作 | 值 | 权重 | 贡献 | 说明 |
|---|---|---:|---:|---:|---|
| `ad_gate` | veto | 0.000 | 0.00 | 0.0000 | is_ad=0.000 < 0.85 |
| `risk` | contribute | 0.030 | 0.35 | 0.0105 |  |
| `exaggeration` | contribute | 0.403 | 0.30 | 0.1210 |  |
| `is_ad` | contribute | 0.020 | 0.25 | 0.0050 |  |
| `is_cta` | contribute | 0.040 | 0.10 | 0.0040 |  |
| `l2_stats` | flag | 0.139 | 0.00 | 0.0000 | l2_mean=0.139（仅记录，不计分） |

> 命中 veto 的规则会直接把总分拉满，后续规则不再计入；
> `flag` 动作只记录不计分（如 L2 统计信号）。


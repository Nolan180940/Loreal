# jev2 单篇判定：`6a90329a000000001f00560b`

> 薅羊毛这几个值得入手吗。

## 结论

| 项 | 值 |
|---|---|
| 总分 | **0.1905** |
| 档位 | **低风险** |
| run_id | `20261011-141239-304fd6` |
| config_hash | `efe851c89c90` |
| 模型 | `jev-1.13` |
| 规则集 | `default` |
| 判定时间 | 2026-10-11T14:12:59 |
| 耗时 | 863 ms |

## 笔记

| 项 | 值 |
|---|---|
| 标题 | 薅羊毛这几个值得入手吗。 |
| 作者 | 家电家居情报站-毛小鱼 |
| 点赞 | 3 |
| 评论声明 | 6 |
| 评论实得 | 6 |
| 图片 | 2 张 |

## 语义维度（jev-1.13）

| 维度 | 风险值 | 置信度 | 题型 |
|---|---:|---:|---|
| `is_cta` | 0.570 | — | noul |
| `is_ad` | 0.470 | — | noul |
| `has_risk` | 0.040 | — | noul |
| `exaggeration` | 0.007 | 0.98 | score |

## 统计信号

| 信号 | 风险值 | n | 详情 |
|---|---:|---:|---|
| `comment_len_iqr` | 0.938 | 6 | iqr=5.0 |
| `tag_count` | 0.571 | 9 | tag_count=9 · tags=('赫莲娜面霜', '黑绷带', '白绷带面霜', '高端护肤', 'HR', '赫莲娜') · de |
| `sub_reply_ratio` | 0.056 | 6 | replies=2 · ratio=0.333 |
| `comment_time_span` | 0.045 | 6 | span_minutes=15936.5 · first_ms=1787842110000 · last_ms=1788798297000 |
| `like_comment_ratio` | 0.020 | 1 | ratio=0.5 · liked=3 · comment_count=6 |
| `author_reply_ratio` | 0.000 | 6 | author_comments=0 · ratio=0.0 |
| `comment_len_mean` | 0.000 | 6 | mean=41.8 |
| `comment_len_sd` | 0.000 | 6 | sd=58.79 · mean=41.8 · min_len=8 · max_len=173 |
| `cta_lexicon` | 0.000 | 0 | density_per_100=0.0 · strong=[] · weak=[] |
| `ip_entropy` | 0.000 | 6 | entropy=0.9591 · distinct=4 |
| `ip_top1_ratio` | 0.000 | 6 | top1=0.333 · top1_ip=北京 · distinct=4 |
| `low_effort_ratio` | 0.000 | 6 | low_effort=1 · ratio=0.167 |
| `structure_markers` | 0.000 | 0 | marker_count=0 · markers=[] |
| `text_exclaim_density` | 0.000 | 146 | exclaims=0 · density_per_100=0.0 |
| `text_length` | 0.000 | 133 | desc_len=133 · title_len=12 |

**缺失 1 个**（样本不足或数据源限制，未参与打分）：

- `comment_like_rate` —— 6 条评论点赞全为 0 —— 疑似匿名态未填充该字段，不作为刷评证据

## 判定过程（规则逐条求值）

| 规则 | 动作 | 值 | 权重 | 贡献 | 说明 |
|---|---|---:|---:|---:|---|
| `ad_gate` | veto | 0.000 | 0.00 | 0.0000 | is_ad=0.000 < 0.85 |
| `risk` | contribute | 0.040 | 0.35 | 0.0140 |  |
| `exaggeration` | contribute | 0.007 | 0.30 | 0.0020 |  |
| `is_ad` | contribute | 0.470 | 0.25 | 0.1175 |  |
| `is_cta` | contribute | 0.570 | 0.10 | 0.0570 |  |
| `l2_stats` | flag | 0.109 | 0.00 | 0.0000 | l2_mean=0.109（仅记录，不计分） |

> 命中 veto 的规则会直接把总分拉满，后续规则不再计入；
> `flag` 动作只记录不计分（如 L2 统计信号）。


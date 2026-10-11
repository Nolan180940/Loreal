# jev2 单篇判定：`6a703362000000002701ec7e`

> 有谁和我一样更爱白绷带吗

## 结论

| 项 | 值 |
|---|---|
| 总分 | **0.3515** |
| 档位 | **中风险** |
| run_id | `20261011-141239-304fd6` |
| config_hash | `efe851c89c90` |
| 模型 | `jev-1.13` |
| 规则集 | `default` |
| 判定时间 | 2026-10-11T14:12:57 |
| 耗时 | 753 ms |

## 笔记

| 项 | 值 |
|---|---|
| 标题 | 有谁和我一样更爱白绷带吗 |
| 作者 | 钱是怎么花掉的 |
| 点赞 | 19 |
| 评论声明 | 28 |
| 评论实得 | 14 |
| 图片 | 1 张 |

## 语义维度（jev-1.13）

| 维度 | 风险值 | 置信度 | 题型 |
|---|---:|---:|---|
| `exaggeration` | 0.597 | 0.71 | score |
| `has_risk` | 0.400 | — | noul |
| `is_cta` | 0.100 | — | noul |
| `is_ad` | 0.090 | — | noul |

## 统计信号

| 信号 | 风险值 | n | 详情 |
|---|---:|---:|---|
| `tag_count` | 1.000 | 12 | tag_count=12 · tags=('赫莲娜', '黑绷带', '白绷带', 'HR赫莲娜', '贵妇面霜', '痘肌护肤') · d |
| `author_reply_ratio` | 0.714 | 14 | author_comments=6 · ratio=0.429 |
| `comment_len_iqr` | 0.344 | 14 | iqr=14.5 |
| `ip_entropy` | 0.296 | 14 | entropy=0.8785 · distinct=6 |
| `comment_len_mean` | 0.214 | 14 | mean=20.8 |
| `ip_top1_ratio` | 0.095 | 14 | top1=0.429 · top1_ip=四川 · distinct=6 |
| `like_comment_ratio` | 0.026 | 1 | ratio=0.68 · liked=19 · comment_count=28 |
| `comment_len_sd` | 0.000 | 14 | sd=16.67 · mean=20.8 · min_len=3 · max_len=66 |
| `comment_time_span` | 0.000 | 14 | span_minutes=67418.4 · first_ms=1785744867000 · last_ms=1789789974000 |
| `cta_lexicon` | 0.000 | 0 | density_per_100=0.0 · strong=[] · weak=[] |
| `low_effort_ratio` | 0.000 | 14 | low_effort=3 · ratio=0.214 |
| `structure_markers` | 0.000 | 0 | marker_count=0 · markers=[] |
| `sub_reply_ratio` | 0.000 | 14 | replies=10 · ratio=0.714 |
| `text_exclaim_density` | 0.000 | 524 | exclaims=0 · density_per_100=0.0 |
| `text_length` | 0.000 | 511 | desc_len=511 · title_len=12 |

**缺失 1 个**（样本不足或数据源限制，未参与打分）：

- `comment_like_rate` —— 14 条评论点赞全为 0 —— 疑似匿名态未填充该字段，不作为刷评证据

## 判定过程（规则逐条求值）

| 规则 | 动作 | 值 | 权重 | 贡献 | 说明 |
|---|---|---:|---:|---:|---|
| `ad_gate` | veto | 0.000 | 0.00 | 0.0000 | is_ad=0.000 < 0.85 |
| `risk` | contribute | 0.400 | 0.35 | 0.1400 |  |
| `exaggeration` | contribute | 0.597 | 0.30 | 0.1790 |  |
| `is_ad` | contribute | 0.090 | 0.25 | 0.0225 |  |
| `is_cta` | contribute | 0.100 | 0.10 | 0.0100 |  |
| `l2_stats` | flag | 0.179 | 0.00 | 0.0000 | l2_mean=0.179（仅记录，不计分） |

> 命中 veto 的规则会直接把总分拉满，后续规则不再计入；
> `flag` 动作只记录不计分（如 L2 统计信号）。


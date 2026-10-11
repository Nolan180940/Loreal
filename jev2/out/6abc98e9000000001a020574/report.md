# jev2 单篇判定：`6abc98e9000000001a020574`

> 空瓶一排，才是真测评。。

## 结论

| 项 | 值 |
|---|---|
| 总分 | **0.3835** |
| 档位 | **中风险** |
| run_id | `20261011-141239-304fd6` |
| config_hash | `efe851c89c90` |
| 模型 | `jev-1.13` |
| 规则集 | `default` |
| 判定时间 | 2026-10-11T14:13:11 |
| 耗时 | 718 ms |

## 笔记

| 项 | 值 |
|---|---|
| 标题 | 空瓶一排，才是真测评。。 |
| 作者 | 去朵朵码头 |
| 点赞 | 914 |
| 评论声明 | 35 |
| 评论实得 | 6 |
| 图片 | 3 张 |

## 语义维度（jev-1.13）

| 维度 | 风险值 | 置信度 | 题型 |
|---|---:|---:|---|
| `exaggeration` | 0.567 | 0.68 | score |
| `is_ad` | 0.500 | — | noul |
| `has_risk` | 0.230 | — | noul |
| `is_cta` | 0.080 | — | noul |

## 统计信号

| 信号 | 风险值 | n | 详情 |
|---|---:|---:|---|
| `tag_count` | 0.714 | 10 | tag_count=10 · tags=('修丽可', '修丽可AGE面霜', '修丽可AGE', 'AGE面霜', '空瓶记', '抗老面 |
| `sub_reply_ratio` | 0.611 | 6 | replies=1 · ratio=0.167 |
| `like_comment_ratio` | 0.511 | 1 | ratio=26.11 · liked=914 · comment_count=35 |
| `comment_len_iqr` | 0.453 | 6 | iqr=12.75 |
| `comment_len_mean` | 0.389 | 6 | mean=18.2 |
| `comment_time_span` | 0.197 | 6 | span_minutes=7467.6 · first_ms=1790756512000 · last_ms=1791204565000 |
| `author_reply_ratio` | 0.000 | 6 | author_comments=0 · ratio=0.0 |
| `comment_len_sd` | 0.000 | 6 | sd=11.29 · mean=18.2 · min_len=10 · max_len=40 |
| `cta_lexicon` | 0.000 | 0 | density_per_100=0.0 · strong=[] · weak=[] |
| `ip_entropy` | 0.000 | 6 | entropy=1.0 · distinct=6 |
| `ip_top1_ratio` | 0.000 | 6 | top1=0.167 · top1_ip=河南 · distinct=6 |
| `low_effort_ratio` | 0.000 | 6 | low_effort=0 · ratio=0.0 |
| `structure_markers` | 0.000 | 0 | marker_count=0 · markers=[] |
| `text_exclaim_density` | 0.000 | 584 | exclaims=0 · density_per_100=0.0 |
| `text_length` | 0.000 | 571 | desc_len=571 · title_len=12 |

**缺失 1 个**（样本不足或数据源限制，未参与打分）：

- `comment_like_rate` —— 6 条评论点赞全为 0 —— 疑似匿名态未填充该字段，不作为刷评证据

## 判定过程（规则逐条求值）

| 规则 | 动作 | 值 | 权重 | 贡献 | 说明 |
|---|---|---:|---:|---:|---|
| `ad_gate` | veto | 0.000 | 0.00 | 0.0000 | is_ad=0.000 < 0.85 |
| `risk` | contribute | 0.230 | 0.35 | 0.0805 |  |
| `exaggeration` | contribute | 0.567 | 0.30 | 0.1700 |  |
| `is_ad` | contribute | 0.500 | 0.25 | 0.1250 |  |
| `is_cta` | contribute | 0.080 | 0.10 | 0.0080 |  |
| `l2_stats` | flag | 0.192 | 0.00 | 0.0000 | l2_mean=0.192（仅记录，不计分） |

> 命中 veto 的规则会直接把总分拉满，后续规则不再计入；
> `flag` 动作只记录不计分（如 L2 统计信号）。


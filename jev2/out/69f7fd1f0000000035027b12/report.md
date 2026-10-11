# jev2 单篇判定：`69f7fd1f0000000035027b12`

> 修丽可AGE面霜，你真的是黑绷带平替吗？

## 结论

| 项 | 值 |
|---|---|
| 总分 | **0.2210** |
| 档位 | **低风险** |
| run_id | `20261011-141239-304fd6` |
| config_hash | `efe851c89c90` |
| 模型 | `jev-1.13` |
| 规则集 | `default` |
| 判定时间 | 2026-10-11T14:12:46 |
| 耗时 | 953 ms |

## 笔记

| 项 | 值 |
|---|---|
| 标题 | 修丽可AGE面霜，你真的是黑绷带平替吗？ |
| 作者 | 琪琪子 |
| 点赞 | 247 |
| 评论声明 | 245 |
| 评论实得 | 20 |
| 图片 | 2 张 |

## 语义维度（jev-1.13）

| 维度 | 风险值 | 置信度 | 题型 |
|---|---:|---:|---|
| `exaggeration` | 0.570 | 0.45 | score |
| `has_risk` | 0.100 | — | noul |
| `is_cta` | 0.050 | — | noul |
| `is_ad` | 0.040 | — | noul |

## 统计信号

| 信号 | 风险值 | n | 详情 |
|---|---:|---:|---|
| `ip_entropy` | 0.210 | 20 | entropy=0.8906 · distinct=9 |
| `like_comment_ratio` | 0.039 | 1 | ratio=1.01 · liked=247 · comment_count=245 |
| `text_exclaim_density` | 0.031 | 400 | exclaims=3 · density_per_100=0.75 |
| `author_reply_ratio` | 0.000 | 20 | author_comments=3 · ratio=0.15 |
| `comment_len_iqr` | 0.000 | 20 | iqr=23.25 |
| `comment_len_mean` | 0.000 | 20 | mean=24.6 |
| `comment_len_sd` | 0.000 | 20 | sd=15.37 · mean=24.6 · min_len=3 · max_len=53 |
| `comment_time_span` | 0.000 | 20 | span_minutes=149673.8 · first_ms=1777867900000 · last_ms=1786848326000 |
| `cta_lexicon` | 0.000 | 0 | density_per_100=0.0 · strong=[] · weak=[] |
| `ip_top1_ratio` | 0.000 | 20 | top1=0.25 · top1_ip=河南 · distinct=9 |
| `low_effort_ratio` | 0.000 | 20 | low_effort=3 · ratio=0.15 |
| `structure_markers` | 0.000 | 0 | marker_count=0 · markers=[] |
| `sub_reply_ratio` | 0.000 | 20 | replies=15 · ratio=0.75 |
| `tag_count` | 0.000 | 3 | tag_count=3 · tags=('修丽可AGE面霜', '赫莲娜黑绷带', '敏感皮') · desc_len=379 |
| `text_length` | 0.000 | 379 | desc_len=379 · title_len=20 |

**缺失 1 个**（样本不足或数据源限制，未参与打分）：

- `comment_like_rate` —— 20 条评论点赞全为 0 —— 疑似匿名态未填充该字段，不作为刷评证据

## 判定过程（规则逐条求值）

| 规则 | 动作 | 值 | 权重 | 贡献 | 说明 |
|---|---|---:|---:|---:|---|
| `ad_gate` | veto | 0.000 | 0.00 | 0.0000 | is_ad=0.000 < 0.85 |
| `risk` | contribute | 0.100 | 0.35 | 0.0350 |  |
| `exaggeration` | contribute | 0.570 | 0.30 | 0.1710 |  |
| `is_ad` | contribute | 0.040 | 0.25 | 0.0100 |  |
| `is_cta` | contribute | 0.050 | 0.10 | 0.0050 |  |
| `l2_stats` | flag | 0.019 | 0.00 | 0.0000 | l2_mean=0.019（仅记录，不计分） |

> 命中 veto 的规则会直接把总分拉满，后续规则不再计入；
> `flag` 动作只记录不计分（如 L2 统计信号）。


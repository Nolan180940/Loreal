# jev2 单篇判定：`6ab8e804000000000200d3cd`

> 贵妇面霜好在哪？ 从研发视角看新一代白绷带

## 结论

| 项 | 值 |
|---|---|
| 总分 | **0.4735** |
| 档位 | **中风险** |
| run_id | `20261011-141239-304fd6` |
| config_hash | `efe851c89c90` |
| 模型 | `jev-1.13` |
| 规则集 | `default` |
| 判定时间 | 2026-10-11T14:13:09 |
| 耗时 | 870 ms |

## 笔记

| 项 | 值 |
|---|---|
| 标题 | 贵妇面霜好在哪？ 从研发视角看新一代白绷带 |
| 作者 | 知学长（成分版） |
| 点赞 | 567 |
| 评论声明 | 29 |
| 评论实得 | 8 |
| 图片 | 7 张 |

## 语义维度（jev-1.13）

| 维度 | 风险值 | 置信度 | 题型 |
|---|---:|---:|---|
| `is_ad` | 0.680 | — | noul |
| `exaggeration` | 0.470 | 0.57 | score |
| `has_risk` | 0.450 | — | noul |
| `is_cta` | 0.050 | — | noul |

## 统计信号

| 信号 | 风险值 | n | 详情 |
|---|---:|---:|---|
| `comment_len_iqr` | 0.828 | 8 | iqr=6.75 |
| `structure_markers` | 0.525 | 5 | marker_count=5 · markers=['✅', '1️⃣', '2️⃣', '3️⃣', '👉'] |
| `author_reply_ratio` | 0.500 | 8 | author_comments=3 · ratio=0.375 |
| `like_comment_ratio` | 0.439 | 1 | ratio=19.55 · liked=567 · comment_count=29 |
| `comment_len_mean` | 0.392 | 8 | mean=18.1 |
| `ip_top1_ratio` | 0.333 | 8 | top1=0.5 · top1_ip=广东 · distinct=4 |
| `ip_entropy` | 0.321 | 8 | entropy=0.875 · distinct=4 |
| `text_length` | 0.267 | 932 | desc_len=932 · title_len=21 |
| `comment_time_span` | 0.156 | 8 | span_minutes=9175.6 · first_ms=1790745155000 · last_ms=1791295689000 |
| `comment_len_sd` | 0.000 | 8 | sd=8.89 · mean=18.1 · min_len=11 · max_len=38 |
| `cta_lexicon` | 0.000 | 0 | density_per_100=0.0 · strong=[] · weak=[] |
| `low_effort_ratio` | 0.000 | 8 | low_effort=0 · ratio=0.0 |
| `sub_reply_ratio` | 0.000 | 8 | replies=3 · ratio=0.375 |
| `tag_count` | 0.000 | 3 | tag_count=3 · tags=('新一代白绷带', '赫莲娜白绷带', '贵妇面霜测评') · desc_len=932 |
| `text_exclaim_density` | 0.000 | 954 | exclaims=0 · density_per_100=0.0 |

**缺失 1 个**（样本不足或数据源限制，未参与打分）：

- `comment_like_rate` —— 8 条评论点赞全为 0 —— 疑似匿名态未填充该字段，不作为刷评证据

## 判定过程（规则逐条求值）

| 规则 | 动作 | 值 | 权重 | 贡献 | 说明 |
|---|---|---:|---:|---:|---|
| `ad_gate` | veto | 0.000 | 0.00 | 0.0000 | is_ad=0.000 < 0.85 |
| `risk` | contribute | 0.450 | 0.35 | 0.1575 |  |
| `exaggeration` | contribute | 0.470 | 0.30 | 0.1410 |  |
| `is_ad` | contribute | 0.680 | 0.25 | 0.1700 |  |
| `is_cta` | contribute | 0.050 | 0.10 | 0.0050 |  |
| `l2_stats` | flag | 0.251 | 0.00 | 0.0000 | l2_mean=0.251（仅记录，不计分） |

> 命中 veto 的规则会直接把总分拉满，后续规则不再计入；
> `flag` 动作只记录不计分（如 L2 统计信号）。


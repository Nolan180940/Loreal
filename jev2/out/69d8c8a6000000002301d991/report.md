# jev2 单篇判定：`69d8c8a6000000002301d991`

> 上海微调升级美貌，这就是原生高智脸的魅力~

## 结论

| 项 | 值 |
|---|---|
| 总分 | **1.0000** |
| 档位 | **高风险** |
| 一票否决 | **ad_gate** |
| run_id | `20261011-210820-162af8` |
| config_hash | `efe851c89c90` |
| 模型 | `jev-1.13` |
| 规则集 | `default` |
| 判定时间 | 2026-10-11T21:08:21 |
| 耗时 | 892 ms |

> 一票否决命中：ad_gate（is_ad ≥ 0.85 一票否决。legacy-jev 实测：加权平均会把纯广告稀释（官方活动贴 is_ad=0.96 被拉到加权 0.642 → 误判中风险），加这道门后高风险召回 40% → 100%。）

## 笔记

| 项 | 值 |
|---|---|
| 标题 | 上海微调升级美貌，这就是原生高智脸的魅力~ |
| 作者 | 张玲｜Yestar |
| 作者认证 | 无 |
| 点赞 | 1001 |
| 评论声明 | 100 |
| 评论实得 | 13 |
| 图片 | 5 张 |

## 语义维度（jev-1.13）

| 维度 | 风险值 | 置信度 | 题型 |
|---|---:|---:|---|
| `is_ad` | 0.970 | — | noul |
| `is_cta` | 0.680 | — | noul |
| `exaggeration` | 0.637 | 0.77 | score |
| `has_risk` | 0.330 | — | noul |

## 统计信号

| 信号 | 风险值 | n | 详情 |
|---|---:|---:|---|
| `comment_len_iqr` | 1.000 | 13 | iqr=4.0 |
| `ip_entropy` | 1.000 | 13 | entropy=0.7323 · distinct=5 |
| `low_effort_ratio` | 1.000 | 13 | low_effort=10 · ratio=0.769 |
| `author_reply_ratio` | 0.846 | 13 | author_comments=6 · ratio=0.462 |
| `ip_top1_ratio` | 0.718 | 13 | top1=0.615 · top1_ip=上海 · distinct=5 |
| `comment_len_mean` | 0.692 | 13 | mean=13.6 |
| `comment_like_rate` | 0.615 | 13 | nonzero=1 · rate=0.077 · with_data=13 |
| `tag_count` | 0.429 | 8 | tag_count=8 · tags=('抗衰', '眼周抗衰', '鼻基底凹陷', '法令纹', '泪沟', '变美新思路') · des |
| `like_comment_ratio` | 0.286 | 1 | ratio=10.01 · liked=1001 · comment_count=100 |
| `publish_burst` | 0.063 | 13 | ratio=0.077 · in_window=1 · window_min=60.0 · ratio_24h=0.077 |
| `brand_mention_ratio` | 0.000 | 13 | ratio=0.0 · hits=0 · words=9 |
| `comment_len_sd` | 0.000 | 13 | sd=30.24 · mean=13.6 · min_len=1 · max_len=118 |
| `comment_time_span` | 0.000 | 13 | span_minutes=261663.2 · first_ms=1775814902000 · last_ms=1791514692000 |
| `cta_lexicon` | 0.000 | 0 | density_per_100=0.0 · strong=[] · weak=[] |
| `structure_markers` | 0.000 | 0 | marker_count=0 · markers=[] |
| `sub_reply_ratio` | 0.000 | 13 | replies=8 · ratio=0.615 |
| `text_exclaim_density` | 0.000 | 629 | exclaims=0 · density_per_100=0.0 |
| `text_length` | 0.000 | 607 | desc_len=607 · title_len=21 |

## 判定过程（规则逐条求值）

| 规则 | 动作 | 值 | 权重 | 贡献 | 说明 |
|---|---|---:|---:|---:|---|
| `ad_gate` | veto | 1.000 | 0.00 | 0.0000 | is_ad=1.000 ≥ 0.85 |
| `risk` | contribute | 0.330 | 0.35 | 0.1155 |  |
| `exaggeration` | contribute | 0.637 | 0.30 | 0.1910 |  |
| `is_ad` | contribute | 0.970 | 0.25 | 0.2425 |  |
| `is_cta` | contribute | 0.680 | 0.10 | 0.0680 |  |
| `l2_stats` | flag | 0.369 | 0.00 | 0.0000 | l2_mean=0.369（仅记录，不计分） |

> 命中 veto 的规则会直接把总分拉满，后续规则不再计入；
> `flag` 动作只记录不计分（如 L2 统计信号）。


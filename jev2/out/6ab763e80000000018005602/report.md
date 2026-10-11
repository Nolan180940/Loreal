# jev2 单篇判定：`6ab763e80000000018005602`

> REDPICK上海活动✨雅诗兰黛邀你解锁全修关系

## 结论

| 项 | 值 |
|---|---|
| 总分 | **1.0000** |
| 档位 | **高风险** |
| 一票否决 | **ad_gate** |
| run_id | `20261011-141239-304fd6` |
| config_hash | `efe851c89c90` |
| 模型 | `jev-1.13` |
| 规则集 | `default` |
| 判定时间 | 2026-10-11T14:13:08 |
| 耗时 | 724 ms |

> 一票否决命中：ad_gate（is_ad ≥ 0.85 一票否决。legacy-jev 实测：加权平均会把纯广告稀释（官方活动贴 is_ad=0.96 被拉到加权 0.642 → 误判中风险），加这道门后高风险召回 40% → 100%。）

## 笔记

| 项 | 值 |
|---|---|
| 标题 | REDPICK上海活动✨雅诗兰黛邀你解锁全修关系 |
| 作者 | 城市情报官 |
| 点赞 | 137 |
| 评论声明 | 20 |
| 评论实得 | 5 |
| 图片 | 3 张 |

## 语义维度（jev-1.13）

| 维度 | 风险值 | 置信度 | 题型 |
|---|---:|---:|---|
| `is_ad` | 0.930 | — | noul |
| `is_cta` | 0.780 | — | noul |
| `has_risk` | 0.200 | — | noul |
| `exaggeration` | 0.130 | 0.61 | score |

## 统计信号

| 信号 | 风险值 | n | 详情 |
|---|---:|---:|---|
| `comment_len_iqr` | 1.000 | 5 | iqr=2.0 |
| `comment_len_mean` | 1.000 | 5 | mean=5.8 |
| `low_effort_ratio` | 1.000 | 5 | low_effort=4 · ratio=0.8 |
| `sub_reply_ratio` | 1.000 | 5 | replies=0 · ratio=0.0 |
| `comment_len_sd` | 0.857 | 5 | sd=2.71 · mean=5.8 · min_len=1 · max_len=9 |
| `comment_time_span` | 0.435 | 5 | span_minutes=2282.1 · first_ms=1790827188000 · last_ms=1790964114000 |
| `like_comment_ratio` | 0.215 | 1 | ratio=6.85 · liked=137 · comment_count=20 |
| `cta_lexicon` | 0.201 | 10 | density_per_100=1.56 · strong=['领取', '先到先得', '限时'] · weak=['搜索', '点击', |
| `structure_markers` | 0.175 | 3 | marker_count=3 · markers=['1️⃣', '2️⃣', '🌟'] |
| `author_reply_ratio` | 0.000 | 5 | author_comments=0 · ratio=0.0 |
| `ip_entropy` | 0.000 | 5 | entropy=0.9602 · distinct=3 |
| `ip_top1_ratio` | 0.000 | 5 | top1=0.4 · top1_ip=上海 · distinct=3 |
| `tag_count` | 0.000 | 2 | tag_count=2 · tags=('这就是全修关系', '雅诗兰黛全修小棕瓶') · desc_len=600 |
| `text_exclaim_density` | 0.000 | 625 | exclaims=0 · density_per_100=0.0 |
| `text_length` | 0.000 | 600 | desc_len=600 · title_len=24 |

**缺失 1 个**（样本不足或数据源限制，未参与打分）：

- `comment_like_rate` —— 5 条评论点赞全为 0 —— 疑似匿名态未填充该字段，不作为刷评证据

## 判定过程（规则逐条求值）

| 规则 | 动作 | 值 | 权重 | 贡献 | 说明 |
|---|---|---:|---:|---:|---|
| `ad_gate` | veto | 1.000 | 0.00 | 0.0000 | is_ad=1.000 ≥ 0.85 |
| `risk` | contribute | 0.200 | 0.35 | 0.0700 |  |
| `exaggeration` | contribute | 0.130 | 0.30 | 0.0390 |  |
| `is_ad` | contribute | 0.930 | 0.25 | 0.2325 |  |
| `is_cta` | contribute | 0.780 | 0.10 | 0.0780 |  |
| `l2_stats` | flag | 0.392 | 0.00 | 0.0000 | l2_mean=0.392（仅记录，不计分） |

> 命中 veto 的规则会直接把总分拉满，后续规则不再计入；
> `flag` 动作只记录不计分（如 L2 统计信号）。


# jev2 单篇判定：`6a57b437000000001702fd1e`

> 山姆买的薇诺娜敏感肌特护霜 壁垒！

## 结论

| 项 | 值 |
|---|---|
| 总分 | **0.1460** |
| 档位 | **低风险** |
| run_id | `20261011-141239-304fd6` |
| config_hash | `efe851c89c90` |
| 模型 | `jev-1.13` |
| 规则集 | `default` |
| 判定时间 | 2026-10-11T14:12:54 |
| 耗时 | 759 ms |

## 笔记

| 项 | 值 |
|---|---|
| 标题 | 山姆买的薇诺娜敏感肌特护霜 壁垒！ |
| 作者 | Isnuch |
| 点赞 | 13 |
| 评论声明 | 26 |
| 评论实得 | 10 |
| 图片 | 1 张 |

## 语义维度（jev-1.13）

| 维度 | 风险值 | 置信度 | 题型 |
|---|---:|---:|---|
| `exaggeration` | 0.347 | 0.00 | score |
| `is_cta` | 0.170 | — | noul |
| `has_risk` | 0.050 | — | noul |
| `is_ad` | 0.030 | — | noul |

## 统计信号

| 信号 | 风险值 | n | 详情 |
|---|---:|---:|---|
| `text_exclaim_density` | 0.203 | 127 | exclaims=2 · density_per_100=1.57 |
| `like_comment_ratio` | 0.020 | 1 | ratio=0.5 · liked=13 · comment_count=26 |
| `author_reply_ratio` | 0.000 | 10 | author_comments=1 · ratio=0.1 |
| `comment_len_iqr` | 0.000 | 10 | iqr=24.5 |
| `comment_len_mean` | 0.000 | 10 | mean=31.1 |
| `comment_len_sd` | 0.000 | 10 | sd=32.92 · mean=31.1 · min_len=7 · max_len=120 |
| `comment_time_span` | 0.000 | 10 | span_minutes=106931.7 · first_ms=1784172661000 · last_ms=1790588563000 |
| `cta_lexicon` | 0.000 | 0 | density_per_100=0.0 · strong=[] · weak=[] |
| `ip_entropy` | 0.000 | 10 | entropy=0.9427 · distinct=7 |
| `ip_top1_ratio` | 0.000 | 10 | top1=0.3 · top1_ip=福建 · distinct=7 |
| `low_effort_ratio` | 0.000 | 10 | low_effort=3 · ratio=0.3 |
| `structure_markers` | 0.000 | 1 | marker_count=1 · markers=['❌'] |
| `sub_reply_ratio` | 0.000 | 10 | replies=5 · ratio=0.5 |
| `tag_count` | 0.000 | 2 | tag_count=2 · tags=('修护肌肤受损屏障', '薇诺娜') · desc_len=109 |
| `text_length` | 0.000 | 109 | desc_len=109 · title_len=17 |

**缺失 1 个**（样本不足或数据源限制，未参与打分）：

- `comment_like_rate` —— 10 条评论点赞全为 0 —— 疑似匿名态未填充该字段，不作为刷评证据

## 判定过程（规则逐条求值）

| 规则 | 动作 | 值 | 权重 | 贡献 | 说明 |
|---|---|---:|---:|---:|---|
| `ad_gate` | veto | 0.000 | 0.00 | 0.0000 | is_ad=0.000 < 0.85 |
| `risk` | contribute | 0.050 | 0.35 | 0.0175 |  |
| `exaggeration` | contribute | 0.347 | 0.30 | 0.1040 |  |
| `is_ad` | contribute | 0.030 | 0.25 | 0.0075 |  |
| `is_cta` | contribute | 0.170 | 0.10 | 0.0170 |  |
| `l2_stats` | flag | 0.015 | 0.00 | 0.0000 | l2_mean=0.015（仅记录，不计分） |

> 命中 veto 的规则会直接把总分拉满，后续规则不再计入；
> `flag` 动作只记录不计分（如 L2 统计信号）。


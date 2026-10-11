# jev2 单篇判定：`6abca4c9000000001a0240e6`

> 惊喜盒子｜雅诗兰黛小棕瓶掉啦

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
| 判定时间 | 2026-10-11T14:13:13 |
| 耗时 | 955 ms |

> 一票否决命中：ad_gate（is_ad ≥ 0.85 一票否决。legacy-jev 实测：加权平均会把纯广告稀释（官方活动贴 is_ad=0.96 被拉到加权 0.642 → 误判中风险），加这道门后高风险召回 40% → 100%。）

## 笔记

| 项 | 值 |
|---|---|
| 标题 | 惊喜盒子｜雅诗兰黛小棕瓶掉啦 |
| 作者 | 🍀落叶🍂 |
| 点赞 | 1586 |
| 评论声明 | 461 |
| 评论实得 | 11 |
| 图片 | 1 张 |

## 语义维度（jev-1.13）

| 维度 | 风险值 | 置信度 | 题型 |
|---|---:|---:|---|
| `is_ad` | 0.850 | — | noul |
| `has_risk` | 0.220 | — | noul |
| `is_cta` | 0.220 | — | noul |
| `exaggeration` | 0.033 | 0.90 | score |

## 统计信号

| 信号 | 风险值 | n | 详情 |
|---|---:|---:|---|
| `comment_len_iqr` | 1.000 | 11 | iqr=2.0 |
| `comment_len_mean` | 1.000 | 11 | mean=6.4 |
| `low_effort_ratio` | 0.950 | 11 | low_effort=8 · ratio=0.727 |
| `comment_len_sd` | 0.886 | 11 | sd=2.57 · mean=6.4 · min_len=1 · max_len=9 |
| `comment_time_span` | 0.351 | 11 | span_minutes=3459.1 · first_ms=1790749271000 · last_ms=1790956817000 |
| `tag_count` | 0.286 | 7 | tag_count=7 · tags=('惊喜盒子', '惊喜盒子来了', '惊喜盒子随机掉落', '雅诗兰黛', '雅诗兰黛全修小棕瓶', |
| `like_comment_ratio` | 0.121 | 1 | ratio=3.44 · liked=1586 · comment_count=461 |
| `cta_lexicon` | 0.030 | 3 | density_per_100=0.91 · strong=['掉落'] · weak=['搜索'] |
| `author_reply_ratio` | 0.000 | 11 | author_comments=0 · ratio=0.0 |
| `ip_entropy` | 0.000 | 10 | entropy=0.9849 · distinct=9 |
| `ip_top1_ratio` | 0.000 | 10 | top1=0.2 · top1_ip=广东 · distinct=9 |
| `structure_markers` | 0.000 | 1 | marker_count=1 · markers=['💡'] |
| `sub_reply_ratio` | 0.000 | 11 | replies=6 · ratio=0.545 |
| `text_exclaim_density` | 0.000 | 278 | exclaims=0 · density_per_100=0.0 |
| `text_length` | 0.000 | 263 | desc_len=263 · title_len=14 |

**缺失 1 个**（样本不足或数据源限制，未参与打分）：

- `comment_like_rate` —— 11 条评论点赞全为 0 —— 疑似匿名态未填充该字段，不作为刷评证据

## 判定过程（规则逐条求值）

| 规则 | 动作 | 值 | 权重 | 贡献 | 说明 |
|---|---|---:|---:|---:|---|
| `ad_gate` | veto | 1.000 | 0.00 | 0.0000 | is_ad=1.000 ≥ 0.85 |
| `risk` | contribute | 0.220 | 0.35 | 0.0770 |  |
| `exaggeration` | contribute | 0.033 | 0.30 | 0.0100 |  |
| `is_ad` | contribute | 0.850 | 0.25 | 0.2125 |  |
| `is_cta` | contribute | 0.220 | 0.10 | 0.0220 |  |
| `l2_stats` | flag | 0.308 | 0.00 | 0.0000 | l2_mean=0.308（仅记录，不计分） |

> 命中 veto 的规则会直接把总分拉满，后续规则不再计入；
> `flag` 动作只记录不计分（如 L2 统计信号）。


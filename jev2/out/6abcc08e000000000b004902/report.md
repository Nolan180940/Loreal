# jev2 单篇判定：`6abcc08e000000000b004902`

> 好消息:掉盒子了，坏消息:是壁纸😅

## 结论

| 项 | 值 |
|---|---|
| 总分 | **0.0720** |
| 档位 | **低风险** |
| run_id | `20261011-141239-304fd6` |
| config_hash | `efe851c89c90` |
| 模型 | `jev-1.13` |
| 规则集 | `default` |
| 判定时间 | 2026-10-11T14:13:14 |
| 耗时 | 728 ms |

## 笔记

| 项 | 值 |
|---|---|
| 标题 | 好消息:掉盒子了，坏消息:是壁纸😅 |
| 作者 | 此momo非彼momo |
| 点赞 | 129 |
| 评论声明 | 35 |
| 评论实得 | 6 |
| 图片 | 1 张 |

## 语义维度（jev-1.13）

| 维度 | 风险值 | 置信度 | 题型 |
|---|---:|---:|---|
| `is_ad` | 0.230 | — | noul |
| `has_risk` | 0.030 | — | noul |
| `is_cta` | 0.030 | — | noul |
| `exaggeration` | 0.003 | 0.99 | score |

## 统计信号

| 信号 | 风险值 | n | 详情 |
|---|---:|---:|---|
| `comment_len_mean` | 0.967 | 6 | mean=9.5 |
| `comment_len_iqr` | 0.922 | 6 | iqr=5.25 |
| `low_effort_ratio` | 0.815 | 6 | low_effort=4 · ratio=0.667 |
| `comment_len_sd` | 0.691 | 6 | sd=3.55 · mean=9.5 · min_len=7 · max_len=15 |
| `sub_reply_ratio` | 0.611 | 6 | replies=1 · ratio=0.167 |
| `comment_time_span` | 0.600 | 6 | span_minutes=887.0 · first_ms=1790768595000 · last_ms=1790821814000 |
| `text_length` | 0.133 | 24 | desc_len=24 · title_len=17 |
| `like_comment_ratio` | 0.129 | 1 | ratio=3.69 · liked=129 · comment_count=35 |
| `author_reply_ratio` | 0.000 | 6 | author_comments=0 · ratio=0.0 |
| `cta_lexicon` | 0.000 | 0 | density_per_100=0.0 · strong=[] · weak=[] |
| `ip_entropy` | 0.000 | 6 | entropy=0.9697 · distinct=5 |
| `ip_top1_ratio` | 0.000 | 6 | top1=0.333 · top1_ip=河北 · distinct=5 |
| `structure_markers` | 0.000 | 0 | marker_count=0 · markers=[] |
| `tag_count` | 0.000 | 2 | tag_count=2 · tags=('惊喜盒子', '雅诗兰黛小棕瓶') · desc_len=24 |
| `text_exclaim_density` | 0.000 | 42 | exclaims=0 · density_per_100=0.0 |

**缺失 1 个**（样本不足或数据源限制，未参与打分）：

- `comment_like_rate` —— 6 条评论点赞全为 0 —— 疑似匿名态未填充该字段，不作为刷评证据

## 判定过程（规则逐条求值）

| 规则 | 动作 | 值 | 权重 | 贡献 | 说明 |
|---|---|---:|---:|---:|---|
| `ad_gate` | veto | 0.000 | 0.00 | 0.0000 | is_ad=0.000 < 0.85 |
| `risk` | contribute | 0.030 | 0.35 | 0.0105 |  |
| `exaggeration` | contribute | 0.003 | 0.30 | 0.0010 |  |
| `is_ad` | contribute | 0.230 | 0.25 | 0.0575 |  |
| `is_cta` | contribute | 0.030 | 0.10 | 0.0030 |  |
| `l2_stats` | flag | 0.325 | 0.00 | 0.0000 | l2_mean=0.324（仅记录，不计分） |

> 命中 veto 的规则会直接把总分拉满，后续规则不再计入；
> `flag` 动作只记录不计分（如 L2 统计信号）。


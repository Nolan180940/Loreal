# jev2 单篇判定：`6aa24385000000002901002b`

> 小黑瓶别只当精华用！我摸索出5个日常用

## 结论

| 项 | 值 |
|---|---|
| 总分 | **0.1850** |
| 档位 | **低风险** |
| run_id | `20261011-141239-304fd6` |
| config_hash | `efe851c89c90` |
| 模型 | `jev-1.13` |
| 规则集 | `default` |
| 判定时间 | 2026-10-11T14:13:03 |
| 耗时 | 930 ms |

## 笔记

| 项 | 值 |
|---|---|
| 标题 | 小黑瓶别只当精华用！我摸索出5个日常用 |
| 作者 | 蔡叨叨 |
| 点赞 | 816 |
| 评论声明 | 14 |
| 评论实得 | 5 |
| 图片 | 5 张 |

## 语义维度（jev-1.13）

| 维度 | 风险值 | 置信度 | 题型 |
|---|---:|---:|---|
| `is_ad` | 0.280 | — | noul |
| `exaggeration` | 0.230 | 0.69 | score |
| `is_cta` | 0.180 | — | noul |
| `has_risk` | 0.080 | — | noul |

## 统计信号

| 信号 | 风险值 | n | 详情 |
|---|---:|---:|---|
| `comment_len_mean` | 1.000 | 5 | mean=9.0 |
| `sub_reply_ratio` | 1.000 | 5 | replies=0 · ratio=0.0 |
| `comment_len_iqr` | 0.750 | 5 | iqr=8.0 |
| `tag_count` | 0.714 | 10 | tag_count=10 · tags=('兰蔻小黑瓶', '小黑瓶隐藏用法', '精华隐藏用法', '肌底精华', '护肤干货', '一物 |
| `like_comment_ratio` | 0.700 | 1 | ratio=58.29 · liked=816 · comment_count=14 |
| `low_effort_ratio` | 0.667 | 5 | low_effort=3 · ratio=0.6 |
| `structure_markers` | 0.350 | 4 | marker_count=4 · markers=['✅', '💡', '⚠️', '▪️'] |
| `comment_len_sd` | 0.207 | 5 | sd=5.97 · mean=9.0 · min_len=1 · max_len=18 |
| `author_reply_ratio` | 0.000 | 5 | author_comments=0 · ratio=0.0 |
| `comment_time_span` | 0.000 | 5 | span_minutes=37981.3 · first_ms=1789097989000 · last_ms=1791376866000 |
| `cta_lexicon` | 0.000 | 0 | density_per_100=0.0 · strong=[] · weak=[] |
| `ip_entropy` | 0.000 | 5 | entropy=0.961 · distinct=4 |
| `ip_top1_ratio` | 0.000 | 5 | top1=0.4 · top1_ip=浙江 · distinct=4 |
| `text_exclaim_density` | 0.000 | 635 | exclaims=1 · density_per_100=0.16 |
| `text_length` | 0.000 | 615 | desc_len=615 · title_len=19 |

**缺失 1 个**（样本不足或数据源限制，未参与打分）：

- `comment_like_rate` —— 5 条评论点赞全为 0 —— 疑似匿名态未填充该字段，不作为刷评证据

## 判定过程（规则逐条求值）

| 规则 | 动作 | 值 | 权重 | 贡献 | 说明 |
|---|---|---:|---:|---:|---|
| `ad_gate` | veto | 0.000 | 0.00 | 0.0000 | is_ad=0.000 < 0.85 |
| `risk` | contribute | 0.080 | 0.35 | 0.0280 |  |
| `exaggeration` | contribute | 0.230 | 0.30 | 0.0690 |  |
| `is_ad` | contribute | 0.280 | 0.25 | 0.0700 |  |
| `is_cta` | contribute | 0.180 | 0.10 | 0.0180 |  |
| `l2_stats` | flag | 0.359 | 0.00 | 0.0000 | l2_mean=0.359（仅记录，不计分） |

> 命中 veto 的规则会直接把总分拉满，后续规则不再计入；
> `flag` 动作只记录不计分（如 L2 统计信号）。


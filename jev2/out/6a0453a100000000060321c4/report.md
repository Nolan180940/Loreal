# jev2 单篇判定：`6a0453a100000000060321c4`

> 修丽可AGE精华 千万别买 不缺钱的随意

## 结论

| 项 | 值 |
|---|---|
| 总分 | **0.3085** |
| 档位 | **中风险** |
| run_id | `20261011-141239-304fd6` |
| config_hash | `efe851c89c90` |
| 模型 | `jev-1.13` |
| 规则集 | `default` |
| 判定时间 | 2026-10-11T14:12:48 |
| 耗时 | 721 ms |

## 笔记

| 项 | 值 |
|---|---|
| 标题 | 修丽可AGE精华 千万别买 不缺钱的随意 |
| 作者 | momo👾👑 |
| 点赞 | 280 |
| 评论声明 | 163 |
| 评论实得 | 18 |
| 图片 | 1 张 |

## 语义维度（jev-1.13）

| 维度 | 风险值 | 置信度 | 题型 |
|---|---:|---:|---|
| `exaggeration` | 0.843 | 0.53 | score |
| `is_cta` | 0.270 | — | noul |
| `has_risk` | 0.060 | — | noul |
| `is_ad` | 0.030 | — | noul |

## 统计信号

| 信号 | 风险值 | n | 详情 |
|---|---:|---:|---|
| `comment_len_iqr` | 0.438 | 18 | iqr=13.0 |
| `like_comment_ratio` | 0.064 | 1 | ratio=1.72 · liked=280 · comment_count=163 |
| `text_exclaim_density` | 0.038 | 128 | exclaims=1 · density_per_100=0.78 |
| `author_reply_ratio` | 0.000 | 18 | author_comments=4 · ratio=0.222 |
| `comment_len_mean` | 0.000 | 18 | mean=28.4 |
| `comment_len_sd` | 0.000 | 18 | sd=22.05 · mean=28.4 · min_len=2 · max_len=92 |
| `comment_time_span` | 0.000 | 18 | span_minutes=133879.7 · first_ms=1778669672000 · last_ms=1786702454000 |
| `cta_lexicon` | 0.000 | 0 | density_per_100=0.0 · strong=[] · weak=[] |
| `ip_entropy` | 0.000 | 18 | entropy=0.9517 · distinct=9 |
| `ip_top1_ratio` | 0.000 | 18 | top1=0.222 · top1_ip=山东 · distinct=9 |
| `low_effort_ratio` | 0.000 | 18 | low_effort=2 · ratio=0.111 |
| `structure_markers` | 0.000 | 0 | marker_count=0 · markers=[] |
| `sub_reply_ratio` | 0.000 | 18 | replies=13 · ratio=0.722 |
| `tag_count` | 0.000 | 0 | tag_count=0 · tags=() · desc_len=107 |
| `text_length` | 0.000 | 107 | desc_len=107 · title_len=20 |

**缺失 1 个**（样本不足或数据源限制，未参与打分）：

- `comment_like_rate` —— 18 条评论点赞全为 0 —— 疑似匿名态未填充该字段，不作为刷评证据

## 判定过程（规则逐条求值）

| 规则 | 动作 | 值 | 权重 | 贡献 | 说明 |
|---|---|---:|---:|---:|---|
| `ad_gate` | veto | 0.000 | 0.00 | 0.0000 | is_ad=0.000 < 0.85 |
| `risk` | contribute | 0.060 | 0.35 | 0.0210 |  |
| `exaggeration` | contribute | 0.843 | 0.30 | 0.2530 |  |
| `is_ad` | contribute | 0.030 | 0.25 | 0.0075 |  |
| `is_cta` | contribute | 0.270 | 0.10 | 0.0270 |  |
| `l2_stats` | flag | 0.036 | 0.00 | 0.0000 | l2_mean=0.036（仅记录，不计分） |

> 命中 veto 的规则会直接把总分拉满，后续规则不再计入；
> `flag` 动作只记录不计分（如 L2 统计信号）。


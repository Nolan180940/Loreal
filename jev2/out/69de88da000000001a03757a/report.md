# jev2 单篇判定：`69de88da000000001a03757a`

> 🇫🇷修丽可AGE面霜，三个月真实感受

## 结论

| 项 | 值 |
|---|---|
| 总分 | **0.0925** |
| 档位 | **低风险** |
| run_id | `20261011-141239-304fd6` |
| config_hash | `efe851c89c90` |
| 模型 | `jev-1.13` |
| 规则集 | `default` |
| 判定时间 | 2026-10-11T14:12:44 |
| 耗时 | 837 ms |

## 笔记

| 项 | 值 |
|---|---|
| 标题 | 🇫🇷修丽可AGE面霜，三个月真实感受 |
| 作者 | Flora在法国 |
| 点赞 | 1148 |
| 评论声明 | 393 |
| 评论实得 | 20 |
| 图片 | 1 张 |

## 语义维度（jev-1.13）

| 维度 | 风险值 | 置信度 | 题型 |
|---|---:|---:|---|
| `exaggeration` | 0.147 | 0.56 | score |
| `is_cta` | 0.100 | — | noul |
| `is_ad` | 0.070 | — | noul |
| `has_risk` | 0.060 | — | noul |

## 统计信号

| 信号 | 风险值 | n | 详情 |
|---|---:|---:|---|
| `comment_len_iqr` | 0.234 | 20 | iqr=16.25 |
| `tag_count` | 0.143 | 6 | tag_count=6 · tags=('修丽可AGE', '法国版', '真实使用感受', '干皮面霜', '抗初老面霜', '面霜分享' |
| `like_comment_ratio` | 0.105 | 1 | ratio=2.92 · liked=1148 · comment_count=393 |
| `author_reply_ratio` | 0.000 | 20 | author_comments=2 · ratio=0.1 |
| `comment_len_mean` | 0.000 | 20 | mean=26.2 |
| `comment_len_sd` | 0.000 | 20 | sd=41.02 · mean=26.2 · min_len=3 · max_len=197 |
| `comment_time_span` | 0.000 | 20 | span_minutes=81946.3 · first_ms=1776269007000 · last_ms=1781185786000 |
| `cta_lexicon` | 0.000 | 0 | density_per_100=0.0 · strong=[] · weak=[] |
| `ip_entropy` | 0.000 | 20 | entropy=0.9686 · distinct=15 |
| `ip_top1_ratio` | 0.000 | 20 | top1=0.15 · top1_ip=安徽 · distinct=15 |
| `low_effort_ratio` | 0.000 | 20 | low_effort=6 · ratio=0.3 |
| `structure_markers` | 0.000 | 0 | marker_count=0 · markers=[] |
| `sub_reply_ratio` | 0.000 | 20 | replies=15 · ratio=0.75 |
| `text_exclaim_density` | 0.000 | 244 | exclaims=0 · density_per_100=0.0 |
| `text_length` | 0.000 | 225 | desc_len=225 · title_len=18 |

**缺失 1 个**（样本不足或数据源限制，未参与打分）：

- `comment_like_rate` —— 20 条评论点赞全为 0 —— 疑似匿名态未填充该字段，不作为刷评证据

## 判定过程（规则逐条求值）

| 规则 | 动作 | 值 | 权重 | 贡献 | 说明 |
|---|---|---:|---:|---:|---|
| `ad_gate` | veto | 0.000 | 0.00 | 0.0000 | is_ad=0.000 < 0.85 |
| `risk` | contribute | 0.060 | 0.35 | 0.0210 |  |
| `exaggeration` | contribute | 0.147 | 0.30 | 0.0440 |  |
| `is_ad` | contribute | 0.070 | 0.25 | 0.0175 |  |
| `is_cta` | contribute | 0.100 | 0.10 | 0.0100 |  |
| `l2_stats` | flag | 0.032 | 0.00 | 0.0000 | l2_mean=0.032（仅记录，不计分） |

> 命中 veto 的规则会直接把总分拉满，后续规则不再计入；
> `flag` 动作只记录不计分（如 L2 统计信号）。


# jev2 单篇判定：`6aabad77000000000b0026a7`

> 赫莲娜白绷带正确使用方法

## 结论

| 项 | 值 |
|---|---|
| 总分 | **0.1120** |
| 档位 | **低风险** |
| run_id | `20261011-141239-304fd6` |
| config_hash | `efe851c89c90` |
| 模型 | `jev-1.13` |
| 规则集 | `default` |
| 判定时间 | 2026-10-11T14:13:05 |
| 耗时 | 780 ms |

## 笔记

| 项 | 值 |
|---|---|
| 标题 | 赫莲娜白绷带正确使用方法 |
| 作者 | momo（护肤版） |
| 点赞 | 8 |
| 评论声明 | 0 |
| 评论实得 | 0 |
| 图片 | 3 张 |

## 语义维度（jev-1.13）

| 维度 | 风险值 | 置信度 | 题型 |
|---|---:|---:|---|
| `is_ad` | 0.190 | — | noul |
| `has_risk` | 0.170 | — | noul |
| `is_cta` | 0.020 | — | noul |
| `exaggeration` | 0.010 | 0.97 | score |

## 统计信号

| 信号 | 风险值 | n | 详情 |
|---|---:|---:|---|
| `tag_count` | 0.714 | 10 | tag_count=10 · tags=('护肤经验howto', '功效护肤请发言', '面霜使用手法', '护肤干货', '贵妇面霜', |
| `cta_lexicon` | 0.000 | 0 | density_per_100=0.0 · strong=[] · weak=[] |
| `structure_markers` | 0.000 | 0 | marker_count=0 · markers=[] |
| `text_exclaim_density` | 0.000 | 140 | exclaims=0 · density_per_100=0.0 |
| `text_length` | 0.000 | 127 | desc_len=127 · title_len=12 |

**缺失 11 个**（样本不足或数据源限制，未参与打分）：

- `author_reply_ratio` —— 评论 0 条 < 3
- `comment_len_iqr` —— 评论 0 条 < 4，IQR 无意义
- `comment_len_mean` —— 评论 0 条 < 3
- `comment_len_sd` —— 评论 0 条 < 3，SD 不可靠
- `comment_like_rate` —— 评论 0 条 < 5
- `comment_time_span` —— 有时间的评论 0 条 < 3
- `ip_entropy` —— 有 IP 的评论 0 条不足
- `ip_top1_ratio` —— 有 IP 的评论 0 条 < 3
- `like_comment_ratio` —— 评论数为 0，比值无意义
- `low_effort_ratio` —— 评论 0 条 < 3
- `sub_reply_ratio` —— 评论 0 条 < 5，比值不稳

## 判定过程（规则逐条求值）

| 规则 | 动作 | 值 | 权重 | 贡献 | 说明 |
|---|---|---:|---:|---:|---|
| `ad_gate` | veto | 0.000 | 0.00 | 0.0000 | is_ad=0.000 < 0.85 |
| `risk` | contribute | 0.170 | 0.35 | 0.0595 |  |
| `exaggeration` | contribute | 0.010 | 0.30 | 0.0030 |  |
| `is_ad` | contribute | 0.190 | 0.25 | 0.0475 |  |
| `is_cta` | contribute | 0.020 | 0.10 | 0.0020 |  |
| `l2_stats` | flag | 0.143 | 0.00 | 0.0000 | l2_mean=0.143（仅记录，不计分） |

> 命中 veto 的规则会直接把总分拉满，后续规则不再计入；
> `flag` 动作只记录不计分（如 L2 统计信号）。


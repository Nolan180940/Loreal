# jev2 单篇判定：`6a2682ff0000000008031b6e`

> 赫莲娜HR白绷带

## 结论

| 项 | 值 |
|---|---|
| 总分 | **0.1440** |
| 档位 | **低风险** |
| run_id | `20261011-141239-304fd6` |
| config_hash | `efe851c89c90` |
| 模型 | `jev-1.13` |
| 规则集 | `default` |
| 判定时间 | 2026-10-11T14:12:51 |
| 耗时 | 1257 ms |

## 笔记

| 项 | 值 |
|---|---|
| 标题 | 赫莲娜HR白绷带 |
| 作者 | 嘿嘿 |
| 点赞 | 26 |
| 评论声明 | 2 |
| 评论实得 | 2 |
| 图片 | 3 张 |

## 语义维度（jev-1.13）

| 维度 | 风险值 | 置信度 | 题型 |
|---|---:|---:|---|
| `exaggeration` | 0.213 | 0.62 | score |
| `is_cta` | 0.210 | — | noul |
| `is_ad` | 0.110 | — | noul |
| `has_risk` | 0.090 | — | noul |

## 统计信号

| 信号 | 风险值 | n | 详情 |
|---|---:|---:|---|
| `tag_count` | 0.714 | 10 | tag_count=10 · tags=('面霜', '赫莲娜', 'HR', '白绷带', '可复美', '大牌面霜') · desc_l |
| `like_comment_ratio` | 0.342 | 1 | ratio=13.0 · liked=26 · comment_count=2 |
| `cta_lexicon` | 0.000 | 0 | density_per_100=0.0 · strong=[] · weak=[] |
| `structure_markers` | 0.000 | 0 | marker_count=0 · markers=[] |
| `text_exclaim_density` | 0.000 | 729 | exclaims=0 · density_per_100=0.0 |
| `text_length` | 0.000 | 720 | desc_len=720 · title_len=8 |

**缺失 10 个**（样本不足或数据源限制，未参与打分）：

- `author_reply_ratio` —— 评论 2 条 < 3
- `comment_len_iqr` —— 评论 2 条 < 4，IQR 无意义
- `comment_len_mean` —— 评论 2 条 < 3
- `comment_len_sd` —— 评论 2 条 < 3，SD 不可靠
- `comment_like_rate` —— 评论 2 条 < 5
- `comment_time_span` —— 有时间的评论 2 条 < 3
- `ip_entropy` —— 有 IP 的评论 2 条不足
- `ip_top1_ratio` —— 有 IP 的评论 2 条 < 3
- `low_effort_ratio` —— 评论 2 条 < 3
- `sub_reply_ratio` —— 评论 2 条 < 5，比值不稳

## 判定过程（规则逐条求值）

| 规则 | 动作 | 值 | 权重 | 贡献 | 说明 |
|---|---|---:|---:|---:|---|
| `ad_gate` | veto | 0.000 | 0.00 | 0.0000 | is_ad=0.000 < 0.85 |
| `risk` | contribute | 0.090 | 0.35 | 0.0315 |  |
| `exaggeration` | contribute | 0.213 | 0.30 | 0.0640 |  |
| `is_ad` | contribute | 0.110 | 0.25 | 0.0275 |  |
| `is_cta` | contribute | 0.210 | 0.10 | 0.0210 |  |
| `l2_stats` | flag | 0.176 | 0.00 | 0.0000 | l2_mean=0.176（仅记录，不计分） |

> 命中 veto 的规则会直接把总分拉满，后续规则不再计入；
> `flag` 动作只记录不计分（如 L2 统计信号）。


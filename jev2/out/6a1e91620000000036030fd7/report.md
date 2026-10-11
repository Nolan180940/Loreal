# jev2 单篇判定：`6a1e91620000000036030fd7`

> 兰蔻小黑瓶精华肌底液到底适不适合你？

## 结论

| 项 | 值 |
|---|---|
| 总分 | **0.6320** |
| 档位 | **高风险** |
| run_id | `20261011-141239-304fd6` |
| config_hash | `efe851c89c90` |
| 模型 | `jev-1.13` |
| 规则集 | `default` |
| 判定时间 | 2026-10-11T14:12:49 |
| 耗时 | 775 ms |

## 笔记

| 项 | 值 |
|---|---|
| 标题 | 兰蔻小黑瓶精华肌底液到底适不适合你？ |
| 作者 | NICEGOO睐斯购 |
| 点赞 | 44 |
| 评论声明 | 0 |
| 评论实得 | 0 |
| 图片 | 1 张 |

## 语义维度（jev-1.13）

| 维度 | 风险值 | 置信度 | 题型 |
|---|---:|---:|---|
| `is_ad` | 0.760 | — | noul |
| `has_risk` | 0.680 | — | noul |
| `exaggeration` | 0.660 | 0.90 | score |
| `is_cta` | 0.060 | — | noul |

## 统计信号

| 信号 | 风险值 | n | 详情 |
|---|---:|---:|---|
| `structure_markers` | 0.700 | 6 | marker_count=6 · markers=['✅', '1️⃣', '2️⃣', '3️⃣', '4️⃣', '🔬'] |
| `tag_count` | 0.286 | 7 | tag_count=7 · tags=('睐斯购', '保税仓', '跨境电商', '兰蔻小黑瓶', '维稳精华', '修护肌底') · d |
| `cta_lexicon` | 0.000 | 0 | density_per_100=0.0 · strong=[] · weak=[] |
| `text_exclaim_density` | 0.000 | 618 | exclaims=2 · density_per_100=0.32 |
| `text_length` | 0.000 | 599 | desc_len=599 · title_len=18 |

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
| `risk` | contribute | 0.680 | 0.35 | 0.2380 |  |
| `exaggeration` | contribute | 0.660 | 0.30 | 0.1980 |  |
| `is_ad` | contribute | 0.760 | 0.25 | 0.1900 |  |
| `is_cta` | contribute | 0.060 | 0.10 | 0.0060 |  |
| `l2_stats` | flag | 0.197 | 0.00 | 0.0000 | l2_mean=0.197（仅记录，不计分） |

> 命中 veto 的规则会直接把总分拉满，后续规则不再计入；
> `flag` 动作只记录不计分（如 L2 统计信号）。


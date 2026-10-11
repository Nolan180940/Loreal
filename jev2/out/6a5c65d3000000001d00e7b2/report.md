# jev2 单篇判定：`6a5c65d3000000001d00e7b2`

> 小黑瓶凭什么稳坐大牌精华C位啊啊啊

## 结论

| 项 | 值 |
|---|---|
| 总分 | **0.3775** |
| 档位 | **中风险** |
| run_id | `20261011-141239-304fd6` |
| config_hash | `efe851c89c90` |
| 模型 | `jev-1.13` |
| 规则集 | `default` |
| 判定时间 | 2026-10-11T14:12:55 |
| 耗时 | 1186 ms |

## 笔记

| 项 | 值 |
|---|---|
| 标题 | 小黑瓶凭什么稳坐大牌精华C位啊啊啊 |
| 作者 | 辣条饲养员 |
| 点赞 | 2684 |
| 评论声明 | 286 |
| 评论实得 | 20 |
| 图片 | 1 张 |

## 语义维度（jev-1.13）

| 维度 | 风险值 | 置信度 | 题型 |
|---|---:|---:|---|
| `exaggeration` | 0.573 | 0.68 | score |
| `is_ad` | 0.470 | — | noul |
| `has_risk` | 0.200 | — | noul |
| `is_cta` | 0.180 | — | noul |

## 统计信号

| 信号 | 风险值 | n | 详情 |
|---|---:|---:|---|
| `tag_count` | 0.571 | 9 | tag_count=9 · tags=('兰蔻小黑瓶', '抗老精华', '修护抗老', '精简护肤', '精华推荐30岁以上', '抗老精 |
| `comment_len_mean` | 0.357 | 20 | mean=18.6 |
| `like_comment_ratio` | 0.273 | 1 | ratio=9.38 · liked=2684 · comment_count=286 |
| `comment_len_iqr` | 0.141 | 20 | iqr=17.75 |
| `text_exclaim_density` | 0.118 | 773 | exclaims=9 · density_per_100=1.16 |
| `author_reply_ratio` | 0.000 | 20 | author_comments=3 · ratio=0.15 |
| `comment_len_sd` | 0.000 | 20 | sd=12.16 · mean=18.6 · min_len=2 · max_len=42 |
| `comment_time_span` | 0.000 | 20 | span_minutes=60310.4 · first_ms=1784457993000 · last_ms=1788076616000 |
| `cta_lexicon` | 0.000 | 0 | density_per_100=0.0 · strong=[] · weak=[] |
| `ip_entropy` | 0.000 | 20 | entropy=0.9614 · distinct=12 |
| `ip_top1_ratio` | 0.000 | 20 | top1=0.15 · top1_ip=广东 · distinct=12 |
| `low_effort_ratio` | 0.000 | 20 | low_effort=5 · ratio=0.25 |
| `structure_markers` | 0.000 | 0 | marker_count=0 · markers=[] |
| `sub_reply_ratio` | 0.000 | 20 | replies=15 · ratio=0.75 |
| `text_length` | 0.000 | 755 | desc_len=755 · title_len=17 |

**缺失 1 个**（样本不足或数据源限制，未参与打分）：

- `comment_like_rate` —— 20 条评论点赞全为 0 —— 疑似匿名态未填充该字段，不作为刷评证据

## 判定过程（规则逐条求值）

| 规则 | 动作 | 值 | 权重 | 贡献 | 说明 |
|---|---|---:|---:|---:|---|
| `ad_gate` | veto | 0.000 | 0.00 | 0.0000 | is_ad=0.000 < 0.85 |
| `risk` | contribute | 0.200 | 0.35 | 0.0700 |  |
| `exaggeration` | contribute | 0.573 | 0.30 | 0.1720 |  |
| `is_ad` | contribute | 0.470 | 0.25 | 0.1175 |  |
| `is_cta` | contribute | 0.180 | 0.10 | 0.0180 |  |
| `l2_stats` | flag | 0.097 | 0.00 | 0.0000 | l2_mean=0.097（仅记录，不计分） |

> 命中 veto 的规则会直接把总分拉满，后续规则不再计入；
> `flag` 动作只记录不计分（如 L2 统计信号）。


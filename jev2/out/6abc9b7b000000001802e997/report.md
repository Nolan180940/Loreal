# jev2 单篇判定：`6abc9b7b000000001802e997`

> 天塌下来我的全修小棕瓶都是白天用的。。。

## 结论

| 项 | 值 |
|---|---|
| 总分 | **0.7465** |
| 档位 | **高风险** |
| run_id | `20261011-141239-304fd6` |
| config_hash | `efe851c89c90` |
| 模型 | `jev-1.13` |
| 规则集 | `default` |
| 判定时间 | 2026-10-11T14:13:12 |
| 耗时 | 1214 ms |

## 笔记

| 项 | 值 |
|---|---|
| 标题 | 天塌下来我的全修小棕瓶都是白天用的。。。 |
| 作者 | 饺子想下锅 |
| 点赞 | 1030 |
| 评论声明 | 44 |
| 评论实得 | 7 |
| 图片 | 2 张 |

## 语义维度（jev-1.13）

| 维度 | 风险值 | 置信度 | 题型 |
|---|---:|---:|---|
| `exaggeration` | 0.807 | 0.58 | score |
| `has_risk` | 0.750 | — | noul |
| `is_cta` | 0.720 | — | noul |
| `is_ad` | 0.680 | — | noul |

## 统计信号

| 信号 | 风险值 | n | 详情 |
|---|---:|---:|---|
| `tag_count` | 0.714 | 10 | tag_count=10 · tags=('修护', '雅诗兰黛小棕瓶', '熬夜', '泛红', '换季', '打工人') · desc_ |
| `like_comment_ratio` | 0.484 | 1 | ratio=23.41 · liked=1030 · comment_count=44 |
| `comment_len_iqr` | 0.406 | 7 | iqr=13.5 |
| `comment_len_mean` | 0.391 | 7 | mean=18.1 |
| `comment_time_span` | 0.253 | 7 | span_minutes=5669.6 · first_ms=1790752101000 · last_ms=1791092274000 |
| `sub_reply_ratio` | 0.214 | 7 | replies=2 · ratio=0.286 |
| `author_reply_ratio` | 0.143 | 7 | author_comments=2 · ratio=0.286 |
| `text_exclaim_density` | 0.103 | 456 | exclaims=5 · density_per_100=1.1 |
| `comment_len_sd` | 0.000 | 7 | sd=7.92 · mean=18.1 · min_len=8 · max_len=30 |
| `cta_lexicon` | 0.000 | 0 | density_per_100=0.0 · strong=[] · weak=[] |
| `ip_entropy` | 0.000 | 7 | entropy=0.963 · distinct=5 |
| `ip_top1_ratio` | 0.000 | 7 | top1=0.286 · top1_ip=安徽 · distinct=5 |
| `low_effort_ratio` | 0.000 | 7 | low_effort=1 · ratio=0.143 |
| `structure_markers` | 0.000 | 0 | marker_count=0 · markers=[] |
| `text_length` | 0.000 | 435 | desc_len=435 · title_len=20 |

**缺失 1 个**（样本不足或数据源限制，未参与打分）：

- `comment_like_rate` —— 7 条评论点赞全为 0 —— 疑似匿名态未填充该字段，不作为刷评证据

## 判定过程（规则逐条求值）

| 规则 | 动作 | 值 | 权重 | 贡献 | 说明 |
|---|---|---:|---:|---:|---|
| `ad_gate` | veto | 0.000 | 0.00 | 0.0000 | is_ad=0.000 < 0.85 |
| `risk` | contribute | 0.750 | 0.35 | 0.2625 |  |
| `exaggeration` | contribute | 0.807 | 0.30 | 0.2420 |  |
| `is_ad` | contribute | 0.680 | 0.25 | 0.1700 |  |
| `is_cta` | contribute | 0.720 | 0.10 | 0.0720 |  |
| `l2_stats` | flag | 0.180 | 0.00 | 0.0000 | l2_mean=0.181（仅记录，不计分） |

> 命中 veto 的规则会直接把总分拉满，后续规则不再计入；
> `flag` 动作只记录不计分（如 L2 统计信号）。


# jev2 单篇判定：`6a9fdee6000000002802974c`

> 得罪人的事我来干—测评修丽可AGE面霜

## 结论

| 项 | 值 |
|---|---|
| 总分 | **0.1540** |
| 档位 | **低风险** |
| run_id | `20261011-141239-304fd6` |
| config_hash | `efe851c89c90` |
| 模型 | `jev-1.13` |
| 规则集 | `default` |
| 判定时间 | 2026-10-11T14:13:02 |
| 耗时 | 797 ms |

## 笔记

| 项 | 值 |
|---|---|
| 标题 | 得罪人的事我来干—测评修丽可AGE面霜 |
| 作者 | 李大漂亮很灵活 |
| 点赞 | 76 |
| 评论声明 | 15 |
| 评论实得 | 11 |
| 图片 | 5 张 |

## 语义维度（jev-1.13）

| 维度 | 风险值 | 置信度 | 题型 |
|---|---:|---:|---|
| `is_cta` | 0.850 | — | noul |
| `exaggeration` | 0.093 | 0.72 | score |
| `is_ad` | 0.080 | — | noul |
| `has_risk` | 0.060 | — | noul |

## 统计信号

| 信号 | 风险值 | n | 详情 |
|---|---:|---:|---|
| `comment_len_mean` | 0.685 | 11 | mean=13.7 |
| `comment_len_iqr` | 0.594 | 11 | iqr=10.5 |
| `author_reply_ratio` | 0.455 | 11 | author_comments=4 · ratio=0.364 |
| `tag_count` | 0.286 | 7 | tag_count=7 · tags=('护肤干货', '成分党', '护肤经验howto', '面霜', '护肤测评', '修丽可') · |
| `text_length` | 0.258 | 931 | desc_len=931 · title_len=19 |
| `like_comment_ratio` | 0.169 | 1 | ratio=5.07 · liked=76 · comment_count=15 |
| `comment_len_sd` | 0.152 | 11 | sd=6.24 · mean=13.7 · min_len=2 · max_len=22 |
| `ip_entropy` | 0.027 | 11 | entropy=0.9163 · distinct=6 |
| `comment_time_span` | 0.000 | 11 | span_minutes=24644.0 · first_ms=1789905919000 · last_ms=1791384561000 |
| `cta_lexicon` | 0.000 | 0 | density_per_100=0.0 · strong=[] · weak=[] |
| `ip_top1_ratio` | 0.000 | 11 | top1=0.364 · top1_ip=湖南 · distinct=6 |
| `low_effort_ratio` | 0.000 | 11 | low_effort=2 · ratio=0.182 |
| `structure_markers` | 0.000 | 0 | marker_count=0 · markers=[] |
| `sub_reply_ratio` | 0.000 | 11 | replies=6 · ratio=0.545 |
| `text_exclaim_density` | 0.000 | 951 | exclaims=0 · density_per_100=0.0 |

**缺失 1 个**（样本不足或数据源限制，未参与打分）：

- `comment_like_rate` —— 11 条评论点赞全为 0 —— 疑似匿名态未填充该字段，不作为刷评证据

## 判定过程（规则逐条求值）

| 规则 | 动作 | 值 | 权重 | 贡献 | 说明 |
|---|---|---:|---:|---:|---|
| `ad_gate` | veto | 0.000 | 0.00 | 0.0000 | is_ad=0.000 < 0.85 |
| `risk` | contribute | 0.060 | 0.35 | 0.0210 |  |
| `exaggeration` | contribute | 0.093 | 0.30 | 0.0280 |  |
| `is_ad` | contribute | 0.080 | 0.25 | 0.0200 |  |
| `is_cta` | contribute | 0.850 | 0.10 | 0.0850 |  |
| `l2_stats` | flag | 0.175 | 0.00 | 0.0000 | l2_mean=0.175（仅记录，不计分） |

> 命中 veto 的规则会直接把总分拉满，后续规则不再计入；
> `flag` 动作只记录不计分（如 L2 统计信号）。


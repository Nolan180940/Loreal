# jev2 单篇判定：`6a7ebdfe00000000080122b8`

> 后悔没早知道白绷带还能这么用！！！！！！

## 结论

| 项 | 值 |
|---|---|
| 总分 | **0.7625** |
| 档位 | **高风险** |
| run_id | `20261011-141239-304fd6` |
| config_hash | `efe851c89c90` |
| 模型 | `jev-1.13` |
| 规则集 | `default` |
| 判定时间 | 2026-10-11T14:12:58 |
| 耗时 | 722 ms |

## 笔记

| 项 | 值 |
|---|---|
| 标题 | 后悔没早知道白绷带还能这么用！！！！！！ |
| 作者 | 别叫我小趴菜 |
| 点赞 | 978 |
| 评论声明 | 94 |
| 评论实得 | 16 |
| 图片 | 1 张 |

## 语义维度（jev-1.13）

| 维度 | 风险值 | 置信度 | 题型 |
|---|---:|---:|---|
| `exaggeration` | 0.980 | 0.94 | score |
| `has_risk` | 0.860 | — | noul |
| `is_ad` | 0.630 | — | noul |
| `is_cta` | 0.100 | — | noul |

## 统计信号

| 信号 | 风险值 | n | 详情 |
|---|---:|---:|---|
| `text_exclaim_density` | 0.500 | 828 | exclaims=36 · density_per_100=4.35 |
| `tag_count` | 0.429 | 8 | tag_count=8 · tags=('赫莲娜白绷带', '新一代赫莲娜白绷带', '抗老面霜', '面霜推荐', '贵妇面霜', '护肤 |
| `like_comment_ratio` | 0.294 | 1 | ratio=10.4 · liked=978 · comment_count=94 |
| `comment_len_iqr` | 0.203 | 16 | iqr=16.75 |
| `structure_markers` | 0.175 | 3 | marker_count=3 · markers=['1️⃣', '2️⃣', '3️⃣'] |
| `comment_len_mean` | 0.142 | 16 | mean=21.9 |
| `author_reply_ratio` | 0.000 | 16 | author_comments=2 · ratio=0.125 |
| `comment_len_sd` | 0.000 | 16 | sd=19.2 · mean=21.9 · min_len=2 · max_len=86 |
| `comment_time_span` | 0.000 | 16 | span_minutes=64093.9 · first_ms=1786711065000 · last_ms=1790556699000 |
| `cta_lexicon` | 0.000 | 1 | density_per_100=0.11 · strong=[] · weak=['码'] |
| `ip_entropy` | 0.000 | 16 | entropy=0.9499 · distinct=10 |
| `ip_top1_ratio` | 0.000 | 16 | top1=0.188 · top1_ip=湖北 · distinct=10 |
| `low_effort_ratio` | 0.000 | 16 | low_effort=3 · ratio=0.188 |
| `sub_reply_ratio` | 0.000 | 16 | replies=11 · ratio=0.688 |
| `text_length` | 0.000 | 807 | desc_len=807 · title_len=20 |

**缺失 1 个**（样本不足或数据源限制，未参与打分）：

- `comment_like_rate` —— 16 条评论点赞全为 0 —— 疑似匿名态未填充该字段，不作为刷评证据

## 判定过程（规则逐条求值）

| 规则 | 动作 | 值 | 权重 | 贡献 | 说明 |
|---|---|---:|---:|---:|---|
| `ad_gate` | veto | 0.000 | 0.00 | 0.0000 | is_ad=0.000 < 0.85 |
| `risk` | contribute | 0.860 | 0.35 | 0.3010 |  |
| `exaggeration` | contribute | 0.980 | 0.30 | 0.2940 |  |
| `is_ad` | contribute | 0.630 | 0.25 | 0.1575 |  |
| `is_cta` | contribute | 0.100 | 0.10 | 0.0100 |  |
| `l2_stats` | flag | 0.116 | 0.00 | 0.0000 | l2_mean=0.116（仅记录，不计分） |

> 命中 veto 的规则会直接把总分拉满，后续规则不再计入；
> `flag` 动作只记录不计分（如 L2 统计信号）。


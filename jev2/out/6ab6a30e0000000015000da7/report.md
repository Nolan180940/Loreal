# jev2 单篇判定：`6ab6a30e0000000015000da7`

> 惊喜盒子｜小棕瓶限时掉落，速来领取！

## 结论

| 项 | 值 |
|---|---|
| 总分 | **1.0000** |
| 档位 | **高风险** |
| 一票否决 | **ad_gate** |
| run_id | `20261011-141239-304fd6` |
| config_hash | `efe851c89c90` |
| 模型 | `jev-1.13` |
| 规则集 | `default` |
| 判定时间 | 2026-10-11T14:13:07 |
| 耗时 | 892 ms |

> 一票否决命中：ad_gate（is_ad ≥ 0.85 一票否决。legacy-jev 实测：加权平均会把纯广告稀释（官方活动贴 is_ad=0.96 被拉到加权 0.642 → 误判中风险），加这道门后高风险召回 40% → 100%。）

## 笔记

| 项 | 值 |
|---|---|
| 标题 | 惊喜盒子｜小棕瓶限时掉落，速来领取！ |
| 作者 | 雅诗兰黛 |
| 点赞 | 5373 |
| 评论声明 | 1980 |
| 评论实得 | 18 |
| 图片 | 2 张 |

## 语义维度（jev-1.13）

| 维度 | 风险值 | 置信度 | 题型 |
|---|---:|---:|---|
| `is_ad` | 0.940 | — | noul |
| `has_risk` | 0.660 | — | noul |
| `is_cta` | 0.490 | — | noul |
| `exaggeration` | 0.443 | 0.59 | score |

## 统计信号

| 信号 | 风险值 | n | 详情 |
|---|---:|---:|---|
| `comment_len_iqr` | 1.000 | 18 | iqr=2.0 |
| `comment_len_mean` | 1.000 | 18 | mean=7.7 |
| `comment_len_sd` | 0.929 | 18 | sd=2.35 · mean=7.7 · min_len=3 · max_len=12 |
| `low_effort_ratio` | 0.815 | 18 | low_effort=12 · ratio=0.667 |
| `cta_lexicon` | 0.471 | 8 | density_per_100=2.57 · strong=['领取', '先到先得', '限时', '掉落'] · weak=[] |
| `comment_time_span` | 0.182 | 18 | span_minutes=8046.7 · first_ms=1790388263000 · last_ms=1790871064000 |
| `text_exclaim_density` | 0.175 | 278 | exclaims=4 · density_per_100=1.44 |
| `like_comment_ratio` | 0.098 | 1 | ratio=2.71 · liked=5373 · comment_count=1980 |
| `author_reply_ratio` | 0.000 | 18 | author_comments=0 · ratio=0.0 |
| `ip_entropy` | 0.000 | 18 | entropy=0.9363 · distinct=11 |
| `ip_top1_ratio` | 0.000 | 18 | top1=0.222 · top1_ip=湖南 · distinct=11 |
| `structure_markers` | 0.000 | 0 | marker_count=0 · markers=[] |
| `sub_reply_ratio` | 0.000 | 18 | replies=13 · ratio=0.722 |
| `tag_count` | 0.000 | 4 | tag_count=4 · tags=('雅诗兰黛小棕瓶', '雅诗兰黛全修小棕瓶', '雅诗兰黛精华', '这就是全修关系') · des |
| `text_length` | 0.000 | 259 | desc_len=259 · title_len=18 |

**缺失 1 个**（样本不足或数据源限制，未参与打分）：

- `comment_like_rate` —— 18 条评论点赞全为 0 —— 疑似匿名态未填充该字段，不作为刷评证据

## 判定过程（规则逐条求值）

| 规则 | 动作 | 值 | 权重 | 贡献 | 说明 |
|---|---|---:|---:|---:|---|
| `ad_gate` | veto | 1.000 | 0.00 | 0.0000 | is_ad=1.000 ≥ 0.85 |
| `risk` | contribute | 0.660 | 0.35 | 0.2310 |  |
| `exaggeration` | contribute | 0.443 | 0.30 | 0.1330 |  |
| `is_ad` | contribute | 0.940 | 0.25 | 0.2350 |  |
| `is_cta` | contribute | 0.490 | 0.10 | 0.0490 |  |
| `l2_stats` | flag | 0.311 | 0.00 | 0.0000 | l2_mean=0.311（仅记录，不计分） |

> 命中 veto 的规则会直接把总分拉满，后续规则不再计入；
> `flag` 动作只记录不计分（如 L2 统计信号）。


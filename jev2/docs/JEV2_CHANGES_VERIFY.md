# 1~5 改动验证

- 注册信号 `ALL_SIGNALS`：17 个
- 默认启用 `ACTIVE_SIGNALS`：16 个
- 默认禁用 `INACTIVE_BY_DEFAULT`：['nickname_dup_rate']
- config high = 0.6  low = 0.3
- config_hash = efe851c89c90

## 新信号在 40 篇上的表现

| 信号 | 非缺失 | 非零 | min | 中位 | max | 均 |
|---|---:|---:|---:|---:|---:|---:|
| `tag_count` | 40 | 16 | 0.00 | 0.00 | 1.00 | 0.21 |
| `structure_markers` | 40 | 5 | 0.00 | 0.00 | 0.70 | 0.05 |
| `cta_lexicon` | 40 | 4 | 0.00 | 0.00 | 0.47 | 0.03 |

## 新信号 AUC 复核（应与原型一致）

| 信号 | AUC(vs high) | AUC(vs high+medium) |
|---|---:|---:|
| `tag_count` | 0.643 | 0.734 |
| `structure_markers` | 0.680 | 0.588 |
| `cta_lexicon` | 0.697 | 0.611 |

- `high=0.70`：二值 97.5% · 三档 75.0% · kappa 0.560 · F1 0.923
- `high=0.60`：二值 100.0% · 三档 77.5% · kappa 0.606 · F1 1.000

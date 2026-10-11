# PLAN：让 19 个统计信号真正参与判定（信号独立计分）

> 状态：**ROUGH DRAFT 待确认**（2026-10-12）
> 依据：引擎源码核实 + 离线扫描（零模型调用）+ 一次数据漂移发现
> 实施后，`jev2/README.md` 的「融合权重全部来自语义维度」一节**作废重写**。

---

## 0. 问题（已用实验证明）

当前 19 个信号对总分**零影响**：把 `l2_mean` 置 0 / 置 1 / 不提供，
`total` 恒为 0.7960。原因：信号只以 `l2_mean` 进 context，
而 `weights` 表没有这个键，`weighted()` 只对权重表里的键计权。

三档判定（high/medium/low）100% 由语义 4 维决定。

## 1. 已完成的验证

### 1.1 离线扫描（信号总权重该给多少）

数据全部免费：语义维度从 `scores.jsonl` 读（模型已判过），信号现算。
40 篇标注上对比：

| 方案 | 二值一致 | kappa | F1 | 三档一致 | 漏 high |
|---|---:|---:|---:|---:|---:|
| A 现状（信号不参与） | 100% | 0.654 | 1.000 | 80.0% | 0 |
| **B 总权重 0.15** | **100%** | **0.776** | **1.000** | **87.5%** | **0** |
| B 总权重 0.25 | 100% | 0.776 | 1.000 | 87.5% | 0 |
| B 总权重 0.40 | 95.0% ↓ | 0.633 | 0.833 | 80.0% | 2 |
| B 总权重 0.60 | 92.5% ↓ | 0.533 | 0.727 | 75.0% | 3 |

结论：**最优区间 0.15~0.25**（kappa +0.122，三档 +7.5pp，二值不降、零漏判）；
**0.40 起开始稀释**（`6a1e9162`、`6a7ebdfe` 等 gold=high 被拉成 medium ——
与当年「加权平均稀释纯广告」同病，稀释源换成了信号）。

### 1.2 数据漂移发现（影响验证步骤）

扫描基线与 `eval_round1` 记录有出入（kappa 0.654 vs 0.606）。
定位结果：**37/40 篇的 `l2_mean` 与产物里存的不一致** ——
产物是 **17 信号时代**跑的，源码已是 19 信号，均值分母变了。

后果：
- 扫描用的是**当前数据 + 19 信号**，这正是实施后生产环境的状态，
  所以扫描结论可用；
- 但 `scores.jsonl` 里的旧行已过时 —— 实施后**必须全量重跑**（本来
  config_hash 也会变），重跑后扫描要在**真引擎产物**上复验定稿。

## 2. 设计决策

| # | 决策 | 理由 |
|---|---|---|
| D1 | **12 个信号计分，6 个保持 flag** | 6 个 AUC<0.60 无区分度证据（brand_mention 0.594、ip_top1 0.511、author_reply 0.495、ip_entropy 0.460、text_length 0.424、comment_like_rate 全缺失），给权重=掺噪声。保持 flag 继续观测，证据足了再升级（与 l2_stats 同一纪律） |
| D2 | **信号总权重 0.20**（区间中点） | 扫描最优带 0.15~0.25 的中点；最终由联合扫描定稿 |
| D3 | **权重按 AUC 先验分配比例，扫描只调总量** | 12 个自由参数必过拟合；先验锁比例后扫描只有 1 个自由度 |
| D4 | **长度簇内递减**（mean 0.0333 > sd 0.0200 > iqr 0.0133） | 三者是同一组评论长度的三个视角，等权=把一个证据数三遍 |
| D5 | **12 条规则声明为 flag，靠 auto-promote 启用** | 回滚 = 删 config 的 12 个键 → 引擎自动降级回 flag。与 l2_stats 现有机制完全一致，零新机制 |
| D6 | **ctx 注入全部非缺失信号**（不止 12 个） | 未来给任何信号加权重键 = 改一行 config，零代码 |
| D7 | **strict / semantic_only 规则集不动** | strict 继续走 l2_mean 路线；semantic_only 本来就不看信号。缩小爆炸半径 |

## 3. 权重表（总 0.20 版）

语义 1.00 : 信号 0.20 ≈ **83% : 17%**。
（语义单维 AUC 0.72~0.96 普遍高于信号 0.60~0.81 —— 主证与佐证的关系。）

| 信号 | 权重 | AUC | 备注 |
|---|---:|---:|---|
| `comment_len_mean` | 0.0333 | 0.809 | 长度簇代表 |
| `low_effort_ratio` | 0.0267 | 0.742 | |
| `comment_len_sd` | 0.0200 | 0.785 | 簇内第二 |
| `comment_time_span` | 0.0200 | 0.737 | |
| `text_exclaim_density` | 0.0167 | 0.714 | |
| `like_comment_ratio` | 0.0167 | 0.714 | |
| `comment_len_iqr` | 0.0133 | 0.761 | 簇内第三 |
| `cta_lexicon` | 0.0133 | 0.697 | |
| `publish_burst` | 0.0133 | 0.691 | |
| `structure_markers` | 0.0100 | 0.680 | |
| `tag_count` | 0.0100 | 0.643 | |
| `sub_reply_ratio` | 0.0067 | 0.603 | |
| **合计** | **0.2000** | | |

保持 flag（不计分）：`l2_stats` 聚合 + 上述 6 个弱信号。
（`comment_like_rate` 待批量重抓激活后，若 AUC ≥0.65 可入下一轮。）

## 4. 实现步骤（按文件）

### 4.1 `pipeline/runner.py` — ctx 注入（~5 行）

```python
# 组装 context：语义维度 + 全部非缺失信号值 + L2 聚合
ctx: dict[str, float] = {d.name: d.value for d in dims}
for name, r in sig.items():
    if not r.missing and r.value is not None:
        ctx[name] = r.value          # 信号以自己的名字进 ctx（D6）
l2 = self._aggregate_l2(sig)
if l2 is not None:
    ctx["l2_mean"] = l2
```

### 4.2 `fuse/rules.py` — 12 条 flag 规则（~40 行）

```python
#: 12 个计分信号（2026-10-12 离线扫描选定，总权重 0.20，见
#: docs/SIGNAL_FUSE_PLAN.md）。**声明为 flag**，由 config.fuse.weights
#: 里的同名键自动提升为 contribute（engine._resolve_action）——
#: 回滚 = 删 config 键，零代码。
SCORING_SIGNALS: dict[str, tuple[float, str]] = {
    "comment_len_mean":     (0.0333, "AUC 0.809，长度簇代表"),
    "low_effort_ratio":     (0.0267, "AUC 0.742"),
    # ... 12 项，见 §3 权重表
}
SIGNAL_RULES: tuple[Rule, ...] = tuple(
    Rule(name=f"sig_{name}", action="flag", formula=F.identity,
         inputs=(name,), weight=w, note=note)
    for name, (w, note) in SCORING_SIGNALS.items()
)
```

`DEFAULT_RULES` 追加 `*SIGNAL_RULES`。trace 里规则名带 `sig_` 前缀，
与语义规则一眼区分。

### 4.3 `config.toml` — weights 加 12 个键

```toml
weights = { has_risk = 0.35, exaggeration = 0.30, is_ad = 0.25, is_cta = 0.10,
            # ---- 12 个计分信号（总 0.20，2026-10-12 扫描定，见
            #      docs/SIGNAL_FUSE_PLAN.md；在考卷上改答案，候选值）----
            comment_len_mean = 0.0333, low_effort_ratio = 0.0267,
            comment_len_sd = 0.0200,   comment_time_span = 0.0200,
            text_exclaim_density = 0.0167, like_comment_ratio = 0.0167,
            comment_len_iqr = 0.0133,  cta_lexicon = 0.0133,
            publish_burst = 0.0133,    structure_markers = 0.0100,
            tag_count = 0.0100,        sub_reply_ratio = 0.0067 }
```

### 4.4 `fuse/formulas.py` — 修 docstring（文档错误）

`weighted()` 的 docstring 写「缺失的维度**不从分母里扣**」，
实测（4 维去 1）分母**会被扣**（`if name not in pairs: continue` 跳过了
wsum 累加）。README 说的「分母也相应扣掉」才是对的。
修正 docstring + 加单测钉住实际行为。

对新设计的实际影响：评论少的篇缺失信号多，在场信号的权重会被
归一化放大。实测缺失通常 2~4/18，影响有限，但必须写清楚。

### 4.5 `tools/sweep_signal_weights.py` — 扫描脚本转正

把临时扫描脚本转正为工具（以后调权重复用）：
- 读 `scores.jsonl` 的语义维度 + 从 `data/` 现算信号（免费、永远最新）
- 对比：现状 / 若干信号总权重 × high 阈值的组合
- 输出二值一致率 / kappa / F1 / 三档一致 / 漏判清单

### 4.6 测试（新增 ~8 个 + 修受影响的）

新增：
1. ctx 含信号值（runner 注入）
2. 权重表有信号键 → 该规则 contribute；删键 → 自动回 flag
   （扩展现有 l2_mean 的 auto-promote 测试）
3. 信号缺失 → 规则 skipped 且分母扣减（钉住 weighted 实际行为）
4. 端到端：新配置下 total ≠ 语义-only total，trace 含 `sig_*` 行
5. 回滚：删 12 个键 → total 回到语义-only 值
6. `--no-semantic`：total = 纯信号分（非 0），警告文案仍在

受影响需修：`test_fuse` 里断言 default 规则集 trace 内容/长度的用例
（trace 从 6 行 → 最多 18 行，flag 规则缺失也进 trace）。

### 4.7 文档（3 处必改，因为原论述将变假）

| 位置 | 现状 | 改为 |
|---|---|---|
| 根 README「融合权重全部来自语义维度」整节 | 说信号一个都不计分 | 语义 1.00 : 信号 0.20；12 计分 + 6 flag；--no-semantic 警告更新 |
| `report.py` 未跑语义层警告 | 「融合权重**全部**来自语义维度…」 | 「语义层未跑 —— 总分只反映统计信号（佐证），缺主证，不构成判定结果」 |
| `jev2/README` 信号表 | 无计分标记 | 加「计分」列（12 个 ✅ / 6 个 flag） |

## 5. 行为变化（必须知道的 4 条）

1. **`--no-semantic` 的输出从恒 0.000 变成纯信号分**（如 0.167 low）。
   「不构成判定结果」的警告**保留**但理由改写（缺主证，只剩佐证）；
   「不算已判过」的逻辑（`model=""` 检查）不变。
2. **trace 从 6 行 → 最多 18 行**（1 veto + 4 语义 + 12 信号 + 1 flag）。
   每篇「为什么判这个档」从此能看到信号层的具体贡献。
3. **config_hash 变化** → 旧 43 篇产物与新配置不可比（报告会警告混运行）。
   处置：`judge --force` 全量重跑（35s / $0.0019）。
4. **`jev2 rules` 输出多 12 行**（12 条 sig_ 规则，显示生效动作与权重）。

## 6. 验证清单（按序）

1. 单测全绿（292 + 新增）
2. `judge --force` 重跑 43 篇（$0.0019）—— 消除 17/19 信号时代的数据漂移
3. **真引擎复验**：用转正的扫描工具对**新产物**算 kappa/F1，
   确认「0.15~0.25 最优、0.40 起稀释」在真引擎上复现
   （我的离线 fuse 是重实现，定稿以真引擎为准）
4. **联合扫描**：信号总权重 {0.15, 0.20, 0.25} × high {0.55, 0.60, 0.65}，
   按二值一致 → kappa → F1 选最优组合，回填 config
5. 抽查 3 篇 trace：1 veto 篇（6ab6a30e）/ 1 临界篇 / 1 低分篇
6. 回滚演练：临时删 12 个 config 键 → total 回到语义-only 值 → 恢复

## 7. 风险与声明

| 风险 | 缓解 |
|---|---|
| **在考卷上改答案**：40 篇自评基准上选的权重 | 沿用既有声明：候选值，换数据验证前不算定稿；基准本身是 AI 判读非真人 ground truth |
| 过拟合：12 个自由参数 | D3：比例由 AUC 先验锁死，扫描只调总量（1 个自由度） |
| 信号把临界篇推错方向 | 扫描显示 0.40 以下零漏判；联合扫描再确认 |
| 旧产物不可比 | 全量重跑消除（§5.3） |

## 8. 工作量与提交

| 步骤 | 估时 |
|---|---|
| 4.1~4.4 代码 + docstring | 40 min |
| 4.6 测试（新增 + 修受影响） | 50 min |
| 4.5 扫描工具转正 + 联合扫描 | 30 min |
| 重跑 43 篇 + 真引擎复验 + 抽查 | 20 min |
| 4.7 文档 | 30 min |
| **合计** | **~2.8h** |

提交拆 2 个：① 实现 + 测试；② 扫描工具 + 文档 + 重跑产物。

## 9. 待确认的决策点

- **D1**：12 计分 + 6 flag（推荐）—— 还是 19 个全上？
- **D2**：总权重 0.20 起步、联合扫描定稿（推荐）
- **D3**：接受 `--no-semantic` 输出变化（0.000 → 纯信号分）？必须接受才能做
- **D4**：strict / semantic_only 不动（推荐）

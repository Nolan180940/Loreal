# 证据卡接口规范 v1.0

证据卡是本模块（图像取证）对外的**唯一接口**。下游不需要知道任何特征实现细节。

## 字段

| 字段 | 类型 | 说明 |
|---|---|---|
| `sample_id` | str | 样本标识（默认取文件名主干） |
| `image` | str | 输入图片路径 |
| `verdict` | enum | `suspicious` / `insufficient_evidence` / `no_anomaly_supported` |
| `verdict_text` | str | 判定档位的中文说明 |
| `p_suspect` | float | 综合可疑概率 ∈ [0,1] |
| `backend` | str | `lr_main`（6 维）或 `stack_jev`（含语义侧第 7 维） |
| `degraded` | bool | 是否处于降级路径（语义侧不可用等） |
| `degraded_reason` | str | 降级原因，例如 `jev_not_provided` |
| `thresholds` | obj | `tau_low` / `tau_high`，来源 `data/models/thresholds.json` |
| `features` | obj | 六维（或七维）特征值，均 ∈ [0,1] |
| `contributions` | obj | 标准化空间逐维贡献 $w_i z_i$，可直接读作"这一维把分数推高/压低多少" |
| `heatmaps` | obj | 各特征热区 PNG 路径（相对项目根）；**定位证据** |
| `overlay` | str | 原图叠加加权热区的可视化路径 |
| `evidence_text` | list[str] | 中文依据句（贡献绝对值 top3，模板生成，不经 LLM） |
| `recommendation` | str | 处理建议 |
| `actions` | obj | 行动门控结果（由 `gating.decide` 产生，见下） |
| `disclaimer` | str | 固定免责声明，禁止下游删除 |

## `actions` 字段（门控层）

| 字段 | 语义 |
|---|---|
| `auto_flag` | 自动打标：需取证侧与语义侧**同时**过线（AND，保守） |
| `human_review` | 进人工复核队列：任一可疑**或**判定为不确定（OR，保召回） |
| `policy` | 策略说明字符串 |
| `thresholds` | `t1_lr` / `t2_jev` |
| `degraded` | 语义侧不可用时为 true（此时 `auto_flag` 恒为 false） |
| `explain` | 人类可读的门控理由 |

## 使用纪律（下游必须遵守）

1. `verdict == no_anomaly_supported` **只能**理解为"未发现所支持的异常"，
   不得表述为"内容为真"或"已证明真实"。
2. `p_suspect` 是合成数据上训练的分数，**不是**真实平台概率，禁止对外宣传
   为准确率或生产指标。
3. 引用判定时**必须**同时引用 `evidence_text` 与 `heatmaps`，即"给出判定依据"。
4. `degraded == true` 时，任何结论都必须标注"仅取证侧证据，未含语义侧核验"。
5. 不得把 `ai_like` 相关结论与真实 AI 生成图结论混为一谈。

## 生成方式

```powershell
# 仅取证侧（离线，断网可用）
d:\LOreal-ai\.venv\Scripts\python.exe -m forensic.cli analyze data\images\s001.png --out card.json

# 带语义侧（需 OPENCODE_API_KEY）
d:\LOreal-ai\.venv\Scripts\python.exe -m forensic.cli analyze data\images\s001.png --jev 0.83 --out card.json

# 单独执行门控
d:\LOreal-ai\.venv\Scripts\python.exe -m forensic.cli gate card.json
```

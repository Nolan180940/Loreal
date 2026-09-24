# Loreal · 赛道2 信任守护师 —— 图像鉴伪取证模块

> 黑客松第二赛道（美妆内容 AI 鉴真）。本仓库为图像侧独立实现：判断配图是否被篡改、拼接或伪造，并输出可复查的证据（可疑区域热区 + 逐维贡献 + 中文依据句）。
> 与文本侧仓库零依赖，纯 CPU 可跑，零大模型权重，零外部数据下载。

## 快速开始

```powershell
# 1. 建环境
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt

# 2. 生成程序化数据（可复现，种子固定；约 310 条）
.venv\Scripts\python.exe forensic\datagen.py data

# 3. 标定 + 特征提取 + 训练 + 阈值（约 1.8 秒/图）
.venv\Scripts\python.exe -u -m forensic.train

# 4. 评估报告
.venv\Scripts\python.exe -m forensic.cli eval

# 5. 单图证据卡（离线，断网可用）
.venv\Scripts\python.exe -m forensic.cli analyze data\images\s219.png --out reports\card.json
```

语义侧（可选，需 `OPENCODE_API_KEY`）：

```powershell
$env:OPENCODE_API_KEY = "<key>"
.venv\Scripts\python.exe -m forensic.cli jev-smoke
.venv\Scripts\python.exe -m forensic.cli analyze data\images\s219.png --post-text "正文..." --out reports\card.json
```

## 架构

```
证据层（无学习）              融合层（可学习）          决策层（布尔门控）
x1 复制-移动（自相关+像素验证）  p = σ(w·x + b)         auto_flag: AND（保守）
x2 重压缩不一致 ELA（相位对齐）  6 维逻辑回归            review:    OR（保召回）
x3 局部噪声异常                  可选第 7 维：           降级：仅 x1..x6
x4 接缝异常                      x7 = logit(p_Jev)
x5 频谱异常（辅助）              → logit 堆叠
x6 元数据/C2PA
每维附热区                       权重由数据学出          逻辑门只在此层
```

## 实测结果（程序化合成集，非真实平台指标）

| 指标 | 结果 |
|---|---|
| val AUC / AP | 0.8431 / 0.8847 |
| val 误报率 | 4.44%（目标 ≤ 5%） |
| 涂改数字检出 / 定位命中 | 100% / 100% |
| 拼接定位命中 | 98.3% |
| 复制-移动定位命中 | 53% |
| 原始干净图误报 | 0% |

详见 `reports/eval_synth.md`（含 bootstrap 区间、分层报告、已知局限）。

## 目录

```
forensic/            取证包（features/datagen/train/fusion/gating/evidence/evaluate/cli/jev_adapter）
docs/                EVIDENCE_CARD.md（证据卡接口）、PROGRESS.md（决策与踩坑记录）
reports/             eval_synth.md、card_s219.json（示例证据卡）
data/                生成物（images/base/masks 为本地生成，不入库；labels.csv/features.csv/models 入库）
IMAGE_LABEL_POLICY.md 标注口径（先行文件）
```

`data/images`、`data/base`、`data/masks`、热区 PNG 均为本地生成物（约 500MB），
可通过 `datagen.py` + `train.py` 复现，不提交到仓库。

## 诚实性纪律

- 合成集数字不得对外宣称为真实平台准确率。
- `no_anomaly_supported` = 未发现所支持的异常，不是证明为真。
- 已知局限见 `reports/eval_synth.md` 第 6 节（良性重压缩与篡改的本质歧义等）。

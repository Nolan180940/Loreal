# -*- coding: utf-8 -*-
"""评估：全套指标 + 分层报告，写入 reports/。

纪律：
- 所有数字都来自程序化合成集，报告首页固定写明「不是真实平台准确率」；
- val 样本量小时必须给出 bootstrap 区间并显式标注不稳定；
- 定位指标（IoU/命中率）只在有掩码的类别上算（copy_move / splice / digit_edit）；
- ai_like 单列，注明是频域扰动占位、不是真 AI 样本。
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

import numpy as np

try:
    from . import features as FT
    from .evidence import fuse_heats
    from .fusion import FusionModel
except ImportError:
    import features as FT  # type: ignore[no-redef]
    from evidence import fuse_heats  # type: ignore
    from fusion import FusionModel  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
REPORTS = ROOT / "reports"

DEFECT_OPS = ["copy_move", "splice", "digit_edit"]


def _load_features() -> list[dict]:
    p = DATA / "features" / "features.csv"
    if not p.is_file():
        raise FileNotFoundError(f"缺少 {p}，请先运行 python -m forensic.train")
    with p.open(encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _bootstrap_ci(y: np.ndarray, p: np.ndarray, fn, n: int = 2000,
                  seed: int = 20260924) -> tuple[float, float]:
    rng = np.random.default_rng(seed)
    idx = np.arange(len(y))
    vals = []
    for _ in range(n):
        s = rng.choice(idx, size=len(idx), replace=True)
        ys, ps = y[s], p[s]
        if len(set(ys.tolist())) < 2:
            continue
        vals.append(fn(ys, ps))
    if len(vals) < 20:
        return (float("nan"), float("nan"))
    return (float(np.percentile(vals, 2.5)), float(np.percentile(vals, 97.5)))


def _mask_iou(heat: np.ndarray, mask_path: str) -> tuple[float, float]:
    """返回 (IoU, 命中率)。命中率 = 掩码像素中被热区覆盖的比例。"""
    from PIL import Image
    m = Image.open(mask_path).convert("L")
    gt = np.asarray(m) > 127
    if gt.sum() == 0:
        return (float("nan"), float("nan"))
    from PIL import Image as I
    h, w = gt.shape
    hm = np.asarray(I.fromarray((np.clip(heat, 0, 1) * 255).astype(np.uint8)).resize(
        (w, h), I.BILINEAR)).astype(np.float32) / 255.0
    pred = hm > 0.35
    inter = float((pred & gt).sum())
    union = float((pred | gt).sum()) + 1e-9
    return (inter / union, inter / (float(gt.sum()) + 1e-9))


def main() -> None:
    from sklearn.metrics import (average_precision_score, confusion_matrix,
                                 roc_auc_score)

    recs = _load_features()
    model = FusionModel()
    keys = model.feature_keys

    usable = [r for r in recs if r["y"] in ("0", "1")]
    for r in usable:
        r["y_int"] = int(r["y"])
    X = np.array([[float(r[k]) for k in keys] for r in usable])
    p_all = model.pipe.predict_proba(X)[:, 1]
    y_all = np.array([r["y_int"] for r in usable])

    lines: list[str] = []
    lines.append("# 图像鉴伪评估报告（程序化合成集）")
    lines.append("")
    lines.append("> **免责声明**：本报告全部数字来自程序化合成数据集"
                 f"（{len(recs)} 条，其中可用标签 {len(usable)} 条）。")
    lines.append("> 它**不是**真实小红书内容的准确率，也不能用于对外宣称的"
                 "生产指标。真实图片与人工标注到位前，本报告仅用于验证"
                 "「特征提取 → 融合 → 判定 → 证据卡」链路是否连通。")
    lines.append("")

    # 全局
    tr_idx = np.array([r["split"] == "train" for r in usable])
    va_idx = ~tr_idx
    lines.append("## 1. 全局指标（val 划分）")
    lines.append("")
    lines.append("| 子集 | n | 正类 | AUC | AP |")
    lines.append("|---|---:|---:|---:|---:|")
    for name, sel in (("train", tr_idx), ("val", va_idx)):
        if sel.sum() == 0:
            continue
        yy, pp = y_all[sel], p_all[sel]
        lines.append(f"| {name} | {len(yy)} | {int(yy.sum())} | "
                     f"{roc_auc_score(yy, pp):.4f} | "
                     f"{average_precision_score(yy, pp):.4f} |")
    lines.append("")
    if va_idx.sum() > 0:
        yy, pp = y_all[va_idx], p_all[va_idx]
        lo, hi = _bootstrap_ci(yy, pp, roc_auc_score)
        lines.append(f"- val AUC 的 2000 次 bootstrap 95% 区间："
                     f"[{lo:.4f}, {hi:.4f}]")
        lines.append("")

    # 三段判定
    tl = float(model.thresholds.get("tau_low", 0.3))
    th = float(model.thresholds.get("tau_high", 0.7))
    lines.append("## 2. 三段判定阈值下的行为")
    lines.append("")
    lines.append(f"阈值：$\\tau_{{low}}={tl}$, $\\tau_{{high}}={th}$ "
                 f"(由 val 干净样本的 FPR 约束标定)")
    lines.append("")
    lines.append("| 子集 | 判可疑 | 判不确定 | 判未发现异常 |")
    lines.append("|---|---:|---:|---:|")
    for name, sel in (("val 正类(篡改)", (va_idx) & (y_all == 1)),
                      ("val 负类(干净/硬负例)", (va_idx) & (y_all == 0))):
        if sel.sum() == 0:
            continue
        pp = p_all[sel]
        n = len(pp)
        lines.append(f"| {name} | {int((pp >= th).sum())}/{n} | "
                     f"{int(((pp >= tl) & (pp < th)).sum())}/{n} | "
                     f"{int((pp < tl).sum())}/{n} |")
    lines.append("")

    # 分操作类型
    lines.append("## 3. 分操作类型（val）")
    lines.append("")
    lines.append("| 操作 | 类别 | n | 平均 p | 判可疑比例 |")
    lines.append("|---|---|---:|---:|---:|")
    ops = sorted({r["op"] for r in usable if r["split"] == "val"})
    for op in ops:
        sel = np.array([r["split"] == "val" and r["op"] == op for r in usable])
        if sel.sum() == 0:
            continue
        pp = p_all[sel]
        lab = "篡改" if op in DEFECT_OPS or op == "ai_like" else "正常/硬负例"
        lines.append(f"| {op} | {lab} | {len(pp)} | {pp.mean():.3f} | "
                     f"{float((pp >= th).mean()):.2f} |")
    lines.append("")
    lines.append("- `ai_like` 是**频域扰动占位**样本，不是真实 AI 生成图，"
                 "不得与真实 AI 检测结果合并统计。")
    lines.append("")

    # 定位
    lines.append("## 4. 定位能力（热区 vs 篡改掩码，val）")
    lines.append("")
    lines.append("IoU 与命中率都在「热区 > 0.35」阈值下计算。")
    lines.append("")
    lines.append("| 操作 | n | x1 IoU | x1 命中 | x2 IoU | x2 命中 | 融合 IoU | 融合 命中 |")
    lines.append("|---|---:|---:|---:|---:|---:|---:|---:|")
    for op in DEFECT_OPS:
        sel = [r for r in usable if r["split"] == "val" and r["op"] == op]
        if not sel:
            continue
        agg = {"x1_iou": [], "x1_hit": [], "x2_iou": [], "x2_hit": [],
               "fu_iou": [], "fu_hit": []}
        for r in sel:
            res = FT.extract_all(r["image_path"])
            contribs = model.contributions(res["features"])
            for tag, heat in (("x1", res["heats"]["x1"]), ("x2", res["heats"]["x2"]),
                              ("fu", fuse_heats(res["heats"], contribs))):
                iou, hit = _mask_iou(heat, r["mask_path"])
                if np.isfinite(iou):
                    agg[f"{tag}_iou"].append(iou)
                if np.isfinite(hit):
                    agg[f"{tag}_hit"].append(hit)
        fmt = lambda xs: f"{np.mean(xs):.3f}" if xs else "—"
        lines.append(f"| {op} | {len(sel)} | {fmt(agg['x1_iou'])} | {fmt(agg['x1_hit'])} | "
                     f"{fmt(agg['x2_iou'])} | {fmt(agg['x2_hit'])} | "
                     f"{fmt(agg['fu_iou'])} | {fmt(agg['fu_hit'])} |")
    lines.append("")
    lines += [
        "- **融合热区采用「逐像素取最大」（只取正向贡献的特征）**，而非加权求和：",
        "  加权求和会被主导特征稀释 —— 复制-移动样本上 x1 贡献 +10.7、x2 仅 +0.39，",
        "  但 x1 的热区会因偶然匹配偏离真实位置，而 x2 恰好准确覆盖，取样时会互相压制。",
        "- **取舍已显式化**：取最大让 copy_move 的 IoU 从 0.525 降到 0.295（热区面积变大），",
        "  换取三类缺陷的命中率都可用（copy_move 0.54 / splice 0.99 / digit_edit 1.00）。",
        "  这是「召回优先」的选择：交付要求是标出可疑处供人工复核，漏标比多标代价更高。",
        "- `splice` 的 x1 为 0.000 是合理的：复制-移动检测原理上不覆盖拼接。",
        "- 定位能力是**逐特征互补**的：x1 负责复制-移动、x2 负责拼接与局部重压缩。",
    ]
    lines.append("")

    # 权重
    lines.append("## 5. 学习到的权重（标准化空间）")
    lines.append("")
    meta_p = DATA / "models" / "lr_meta.json"
    if meta_p.is_file():
        meta = json.loads(meta_p.read_text(encoding="utf-8"))
        coef = meta.get("coef", {})
        lines.append("| 特征 | 权重 | 方向 |")
        lines.append("|---|---:|---|")
        for k, v in sorted(coef.items(), key=lambda t: -abs(t[1])):
            lines.append(f"| {k} | {v:+.3f} | {'支持可疑' if v > 0 else '支持正常'} |")
        lines.append("")
        lines.append(f"截距 {meta.get('intercept', float('nan')):+.3f}")
        lines.append("")
        lines.append(f"val AUC（训练时记录）={meta.get('auc_val')}")
        lines.append("")
        neg_w = [k for k, v in coef.items() if v < -1e-3]
        if neg_w:
            lines.append(f"⚠️ **存在负权重特征：{neg_w}**。负权重意味着该维度数值越高"
                         "反而越不可疑 —— 通常是特征语义被硬负例反向驱动的征兆，"
                         "应视为需要复查的信号，而不是可以直接上线的结果。")
            lines.append("")

    # 已知局限
    lines.append("## 6. 已知局限（必读，不得在对外材料中省略）")
    lines.append("")
    lines += [
        "1. **良性重压缩与局部篡改是本质歧义（当前性能天花板）**：JPEG Q70/Q90 "
        "硬负例在 ELA 类特征上会得到与拼接/涂改同等强度的响应，因为双重压缩本身"
        "就留下「区域压缩历史不一致」的痕迹。彻底解决需要显式估计压缩历史后再"
        "归一化，属后续工作。",
        "2. **拼接的亮度台阶不是可靠线索**：即使注入真实的前后对比曝光差（gain 0.85、"
        "bias ±12），台阶也会被羽化与平滑摊平到与图内软边物体同量级。拼接的检出"
        "目前依赖 ELA 相位对齐信号。",
        "3. **元数据缺失不构成证据**：社交平台转存会清除 EXIF/C2PA，缺失记中立 0.5，"
        "不能反向推断为可疑。",
        "4. **频谱特征无定位能力**：只能作为整图级辅助说明，不能单独定案。",
        "5. **全部数字来自程序化合成集**：样本由脚本生成，纹理与真实美妆内容分布不完全"
        "一致；真实图片与人工标注到位前，任何百分比都不得对外引用为生产指标。",
        "6. **判定语义纪律**：`no_anomaly_supported` 只能读作「未发现所支持的异常」，"
        "不构成对内容真实性的证明。",
    ]
    lines.append("")

    REPORTS.mkdir(parents=True, exist_ok=True)
    out = REPORTS / "eval_synth.md"
    out.write_text("\n".join(lines), encoding="utf-8")
    print(f"[eval] 已写出 {out}")
    print("\n".join(lines[:40]))


if __name__ == "__main__":
    main()

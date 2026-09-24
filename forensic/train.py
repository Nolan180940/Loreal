# -*- coding: utf-8 -*-
"""训练与标定流水线：标定 → 特征提取 → LR 融合 → 双阈值 → 模型保存。

用法（项目根目录）：
    .venv\\Scripts\\python.exe -m forensic.train

产出：
    data/features/features.csv        每样本六维特征 + 标签
    data/models/calibration.json      干净训练集上标定的映射区间
    data/models/lr_main.joblib        主模型（6 维逻辑回归）
    data/models/thresholds.json       双阈值（三段判定）
"""

from __future__ import annotations

import csv
import json
import time
from pathlib import Path

import numpy as np

try:
    from . import features as FT
except ImportError:  # 允许 python -m 与直接运行两种方式
    import features as FT  # type: ignore[no-redef]

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
FEAT_DIR = DATA / "features"
MODEL_DIR = DATA / "models"

FEATURE_KEYS = ["x1_copy_move", "x2_ela", "x3_noise", "x4_seam",
                "x5_spectrum", "x6_meta"]


def _read_labels() -> list[dict]:
    with (DATA / "labels.csv").open(encoding="utf-8") as f:
        return list(csv.DictReader(f))


def calibrate_from_clean(rows: list[dict], verbose: bool = True) -> dict:
    """只用 train 划分的干净图（y=0, op=original）标定各特征映射区间。

    这是防泄漏的关键：val 与任何篡改样本都不得参与标定。
    """
    clean = [r for r in rows if r["split"] == "train" and r["op"] == "original"]
    if not clean:
        raise RuntimeError("没有 train 划分的干净样本，无法标定")
    stats: dict[str, list[float]] = {"x2": [], "x3": [], "x4": [], "x5": []}
    gammas: list[float] = []
    for r in clean:
        g = FT.load_gray(r["image_path"])
        stats["x2"].append(FT.extract_x2(r["image_path"])[2]["raw"])
        stats["x3"].append(FT.extract_x3(g)[2]["raw"])
        stats["x4"].append(FT.extract_x4(g)[2]["raw"])
        aux5 = FT.extract_x5(g)[2]
        stats["x5"].append(aux5["raw"])
        gammas.append(aux5["gamma"])

    calib = {}
    for k, v in stats.items():
        a = np.asarray(v, dtype=float)
        lo = float(np.median(a))
        hi = float(a.max()) * 1.25 + 1e-6
        if hi - lo < 1e-6:          # 退化情形：给一个最小宽度，避免除零
            hi = lo + 1.0
        calib[k] = {"lo": round(lo, 4), "hi": round(hi, 4)}
    gamma_ref = float(np.median(gammas))
    gamma_scale = float(max(np.percentile(np.abs(np.asarray(gammas) - gamma_ref), 90), 0.05))

    cfg = {"calib": calib, "x5": {"gamma_ref": round(gamma_ref, 4),
                                  "gamma_scale": round(gamma_scale, 4)},
           "n_clean": len(clean), "source_split": "train/original"}
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    (MODEL_DIR / "calibration.json").write_text(
        json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")

    FT.CALIB.update({k: {"lo": v["lo"], "hi": v["hi"]} for k, v in calib.items()})
    FT.GAMMA_REF = gamma_ref
    FT.GAMMA_SCALE = gamma_scale
    if verbose:
        print(f"[calib] n_clean={len(clean)}")
        for k, v in calib.items():
            print(f"  {k}: lo={v['lo']} hi={v['hi']}")
        print(f"  x5: gamma_ref={gamma_ref:.3f} gamma_scale={gamma_scale:.3f}")
    return cfg


def extract_features(rows: list[dict], verbose: bool = True) -> list[dict]:
    FEAT_DIR.mkdir(parents=True, exist_ok=True)
    out: list[dict] = []
    t0 = time.time()
    for i, r in enumerate(rows, 1):
        res = FT.extract_all(r["image_path"])
        f = res["features"]
        rec = {"sample_id": r["sample_id"], "op": r["op"], "split": r["split"],
               "y": r["y"], "image_path": r["image_path"],
               "mask_path": r["mask_path"], "base_id": r["base_id"],
               "source": r["source"], "params_json": r["params_json"]}
        rec.update({k: float(v) for k, v in f.items()})
        out.append(rec)
        if verbose and (i % 20 == 0 or i == len(rows)):
            el = time.time() - t0
            print(f"[feat] {i}/{len(rows)}  {el:.1f}s  "
                  f"({el / i:.2f}s/图, 预计剩余 {el / i * (len(rows) - i):.0f}s)")

    path = FEAT_DIR / "features.csv"
    with path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(out[0].keys()))
        w.writeheader()
        w.writerows(out)
    # 同时保存热图（选样，供证据卡与人工复核使用）
    if verbose:
        print(f"[feat] 已写出 {path}  ({len(out)} 行)")
    return out


def train_lr(recs: list[dict], verbose: bool = True):
    from sklearn.linear_model import LogisticRegression
    from sklearn.pipeline import Pipeline
    from sklearn.preprocessing import StandardScaler

    usable = [r for r in recs if r["y"] in (0, 1, "0", "1")]
    tr = [r for r in usable if r["split"] == "train"]
    va = [r for r in usable if r["split"] == "val"]

    def mat(rs):
        X = np.array([[float(r[k]) for k in FEATURE_KEYS] for r in rs], dtype=float)
        y = np.array([int(r["y"]) for r in rs], dtype=int)
        return X, y

    Xtr, ytr = mat(tr)
    Xva, yva = mat(va)
    # sklearn >= 1.8 弃用了 penalty 参数，改用 l1_ratio（默认 0 即 L2 正则）
    pipe = Pipeline([("scaler", StandardScaler()),
                     ("lr", LogisticRegression(C=1.0, l1_ratio=0.0,
                                               solver="lbfgs", max_iter=2000))])
    pipe.fit(Xtr, ytr)

    # 逐维权重（在标准化空间里，可直接读作重要性）
    scaler = pipe.named_steps["scaler"]
    lr = pipe.named_steps["lr"]
    coef = lr.coef_[0]
    if verbose:
        print(f"[lr] train n={len(tr)} val n={len(va)}")
        print(f"[lr] 标准化空间权重（正=更像篡改）:")
        for k, c in sorted(zip(FEATURE_KEYS, coef), key=lambda t: -abs(t[1])):
            print(f"   {k:14s} {c:+.3f}")
        print(f"[lr] 截距 {lr.intercept_[0]:+.3f}")

    from sklearn.metrics import roc_auc_score
    pv = pipe.predict_proba(Xva)[:, 1]
    if len(set(yva.tolist())) > 1:
        auc = float(roc_auc_score(yva, pv))
        if verbose:
            print(f"[lr] val AUC = {auc:.4f}")
    else:
        auc = float("nan")
    return pipe, {"auc_val": auc, "coef": {k: float(c) for k, c in zip(FEATURE_KEYS, coef)},
                  "intercept": float(lr.intercept_[0])}


def pick_thresholds(pipe, recs: list[dict], target_fpr: float = 0.05) -> dict:
    """在 val 上标定双阈值：tau_low 取误报率<=target_fpr 的分位点。

    纪律：阈值只在 val 上定一次并写死；样本太小时显式标记不可靠。
    """
    usable = [r for r in recs if r["y"] in (0, 1, "0", "1")]
    va = [r for r in usable if r["split"] == "val"]
    X = np.array([[float(r[k]) for k in FEATURE_KEYS] for r in va], dtype=float)
    y = np.array([int(r["y"]) for r in va], dtype=int)
    p = pipe.predict_proba(X)[:, 1]
    neg = np.sort(p[y == 0])
    pos = np.sort(p[y == 1])
    n_neg, n_pos = len(neg), len(pos)

    # tau_low：在 val 上取「满足 FPR <= target_fpr 的最小阈值」，以保留最多召回。
    # 用搜索而非下标算术：阈值等于某个负样本分数时，该样本会被计入误报
    # （判据是 p >= tau），故候选阈值必须取「比候选负样本略高」。下标公式的
    # 版本实测 FPR 为 6.67% 而非目标 5%（off-by-one），这里改为可证明正确的搜索。
    if n_neg:
        tau_low = 1.0
        for v in neg:  # neg 已升序，取第一个满足约束者＝最小可行阈值
            cand = float(v) + 1e-9
            if float((neg >= cand).mean()) <= target_fpr:
                tau_low = cand
                break
    else:
        tau_low = 0.5
    tau_low = float(np.clip(tau_low, 0.0, 0.99))
    # tau_high：在可接受的误报内的更高分位，用于"高置信可疑"
    if n_pos:
        tau_high = float(np.percentile(pos, 25))
    else:
        tau_high = tau_low + 0.3
    tau_high = float(np.clip(max(tau_high, tau_low + 0.05), tau_low + 0.05, 0.99))

    fpr = float((p[y == 0] >= tau_low).mean()) if n_neg else float("nan")
    rec = float((p[y == 1] >= tau_low).mean()) if n_pos else float("nan")
    rec_hi = float((p[y == 1] >= tau_high).mean()) if n_pos else float("nan")
    out = {"tau_low": round(tau_low, 4), "tau_high": round(tau_high, 4),
           "target_fpr": target_fpr, "val_n_neg": n_neg, "val_n_pos": n_pos,
           "val_fpr_at_tau_low": round(fpr, 4), "val_recall_at_tau_low": round(rec, 4),
           "val_recall_at_tau_high": round(rec_hi, 4),
           "stable": bool(n_neg >= 20 and n_pos >= 20),
           "note": "阈值/指标基于程序化合成集，不是真实平台准确率"}
    return out


def main(reuse_features: bool = False):
    import joblib

    rows = _read_labels()
    print(f"[data] 共 {len(rows)} 条样本")
    if not reuse_features:
        calibrate_from_clean(rows)
        recs = extract_features(rows)
    else:
        # 复用已提取的特征（标定参数从 calibration.json 载入）
        calib = FT.load_calibration()
        print(f"[calib] 载入 calibration.json: {calib['loaded']}")
        if not calib["loaded"]:
            raise RuntimeError("缺少 calibration.json，不能复用特征，请去掉 --reuse-features")
        csv_p = FEAT_DIR / "features.csv"
        if not csv_p.is_file():
            raise FileNotFoundError(f"缺少 {csv_p}，请先完整跑一次 train")
        with csv_p.open(encoding="utf-8") as f:
            recs = list(csv.DictReader(f))
        if len(recs) != len(rows):
            raise RuntimeError(f"features.csv 行数 {len(recs)} 与 labels.csv {len(rows)} 不一致，"
                               "请重新提取特征")
        print(f"[feat] 复用 {len(recs)} 行已提取特征")

    pipe, meta = train_lr(recs)
    thr = pick_thresholds(pipe, recs)
    print("[thr]", json.dumps(thr, ensure_ascii=False))

    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    joblib.dump(pipe, MODEL_DIR / "lr_main.joblib")
    (MODEL_DIR / "thresholds.json").write_text(
        json.dumps(thr, ensure_ascii=False, indent=2), encoding="utf-8")
    (MODEL_DIR / "lr_meta.json").write_text(
        json.dumps({"feature_keys": FEATURE_KEYS, **meta}, ensure_ascii=False, indent=2),
        encoding="utf-8")
    print(f"[save] {MODEL_DIR / 'lr_main.joblib'}")


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--reuse-features", action="store_true",
                    help="复用 data/features/features.csv，跳过标定与特征提取")
    main(reuse_features=ap.parse_args().reuse_features)

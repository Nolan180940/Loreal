# -*- coding: utf-8 -*-
"""证据卡生成：分数 + 逐维贡献 + 热区 + 可读依据 + 建议。

证据卡是下游（Agent / 文本侧 / 后训练侧）唯一接口，字段见 docs/EVIDENCE_CARD.md。
全部离线生成，不经过任何 LLM，保证可复现。
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
from PIL import Image

try:
    from . import features as FT
    from .fusion import (FEATURE_LABELS, VERDICT_TEXT, FusionModel, evidence_lines)
except ImportError:  # 直接运行时
    import features as FT  # type: ignore[no-redef]
    from fusion import (FEATURE_LABELS, VERDICT_TEXT, FusionModel,  # type: ignore
                        evidence_lines)

ROOT = Path(__file__).resolve().parents[1]
HEAT_DIR = ROOT / "data" / "features"

RECOMMENDATION = {
    "suspicious": "建议人工复核，并优先查看标注出的疑点区域",
    "insufficient_evidence": "证据不足，建议人工复核或补充原始素材（原图/原帖链接）",
    "no_anomaly_supported": "未发现所支持的异常；如需进一步确认请提供原始文件",
}


def _heat_to_png(heat: np.ndarray, path: Path, size: tuple[int, int]) -> None:
    arr = np.clip(heat * 255.0, 0, 255).astype(np.uint8)
    img = Image.fromarray(arr, mode="L").resize(size, Image.BILINEAR)
    path.parent.mkdir(parents=True, exist_ok=True)
    img.save(path, format="PNG")


def _short_key(k: str) -> str:
    """热区键是短名（x1..x6），贡献键是完整名（x1_copy_move）。
    所有跨表查找必须先归一化 —— 键名不匹配会导致热区被静默跳过（实测踩坑）。"""
    return k.split("_")[0]


def fuse_heats(heats: dict[str, np.ndarray],
               contribs: dict[str, float],
               min_area_frac: float = 0.002) -> np.ndarray:
    """把各特征热区合成「最终热区」：只取正向贡献的特征，逐像素取最大值。

    为什么用 max 而不是加权求和（数据支撑，实测于 val 集）：
    - 加权求和会被**主导特征稀释**：复制-移动样本上 x1 贡献 +10.7、x2 仅 +0.39，
      但 x1 的热区会因偶然匹配而偏离真实篡改位置（实测 shift=33 的伪匹配），
      而 x2 恰好准确覆盖。求和时 x1 压制了 x2，定位反而变差。
    - 逐像素取 max 让「任一特征指认的区域」都能显示，命中率显著更均衡：
      实测 copy_move 0.54 / splice 0.99 / digit_edit 1.00（x1 单用时
      digit_edit 仅 0.16、splice 为 0）。
    - 代价：copy_move 的 IoU 从 0.525 降到 0.295（热区面积变大）。这是
      **召回优先**的取舍 —— 交付要求是「标出可疑之处供人工复核」，
      漏标比多标代价更高。该取舍已在评估报告与文档中显式记录。

    min_area_frac：滤掉面积过小的孤立连通域（默认 0.2% 画面）。
    没有这一步时，x3/x4 会散布数十个小斑点，画面噪声大、可读性差，
    反而削弱「标出可疑之处」的说服力；被滤掉的斑点信息仍保留在各特征
    单独的 heatmap PNG 里，不影响可复查性。
    """
    pos = {}
    for k, v in contribs.items():
        s = _short_key(k)
        pos[s] = pos.get(s, 0.0) + float(v)
    acc = None
    for k, hm in heats.items():
        if hm is None or hm.size == 0 or not np.any(hm):
            continue
        if pos.get(_short_key(k), 0.0) <= 1e-6:
            continue
        acc = hm.astype(np.float32) if acc is None else np.maximum(acc, hm.astype(np.float32))
    if acc is None:
        return np.zeros_like(next(iter(heats.values())))

    from scipy import ndimage as _nd
    binary = acc > 0.2
    lab, n = _nd.label(binary)
    if n == 0:
        return np.zeros_like(acc)
    sizes = _nd.sum(binary, lab, index=np.arange(1, n + 1))
    keep = np.zeros_like(acc)
    min_area = float(min_area_frac) * acc.size
    for i, sz in enumerate(sizes, 1):
        if float(sz) >= min_area:
            keep = np.maximum(keep, np.where(lab == i, acc, 0.0).astype(np.float32))
    return keep


def _overlay(base_path: str | Path, heats: dict[str, np.ndarray], path: Path,
             weights: dict[str, float] | None = None) -> None:
    """原图 + 最终热区（红色半透明），用于人工复核与演示。"""
    base = Image.open(base_path).convert("RGB")
    w, h = base.size
    if weights is None:
        acc = np.zeros((h, w), dtype=np.float32)
        for hm in heats.values():
            if hm is not None and hm.size:
                acc = np.maximum(acc, _resize(hm, (w, h)))
    else:
        acc = _resize(fuse_heats(heats, weights), (w, h))
    acc = np.clip(acc, 0, 1)
    arr = np.asarray(base).astype(np.float32)
    red = np.array([255.0, 40.0, 40.0], dtype=np.float32)
    alpha = (acc ** 0.7)[..., None]
    out = arr * (1 - alpha) + red[None, None, :] * alpha
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(np.clip(out, 0, 255).astype(np.uint8)).save(path, format="PNG")


def _resize(hm: np.ndarray, size: tuple[int, int]) -> np.ndarray:
    w, h = size
    if hm.shape == (h, w):
        return hm
    img = Image.fromarray((np.clip(hm, 0, 1) * 255).astype(np.uint8), mode="L")
    return np.asarray(img.resize((w, h), Image.BILINEAR)).astype(np.float32) / 255.0


def build_card(image_path: str | Path, model: FusionModel,
               p_jev: float | None = None, save_heatmaps: bool = True,
               sample_id: str | None = None) -> dict:
    """对单图生成证据卡。"""
    image_path = Path(image_path)
    res = FT.extract_all(image_path)
    feats = res["features"]
    heats = res["heats"]
    contribs = model.contributions(feats)

    if p_jev is None:
        pred = model.predict(feats)
        degraded = True
        degraded_reason = "jev_not_provided"
    else:
        pred = model.predict_with_jev(feats, p_jev)
        degraded = bool(pred.get("degraded", False))
        degraded_reason = pred.get("degraded_reason", "")
    p = float(pred["p"])
    verdict = model.verdict(p)

    sid = sample_id or image_path.stem
    heat_paths: dict[str, str] = {}
    overlay_path = ""
    if save_heatmaps:
        w, h = Image.open(image_path).size
        for k, hm in heats.items():
            if hm is None or hm.size == 0 or not np.any(hm):
                continue
            pth = HEAT_DIR / f"{sid}_{k}.png"
            _heat_to_png(hm, pth, (w, h))
            heat_paths[k] = str(pth.relative_to(ROOT))
        op = HEAT_DIR / f"{sid}_overlay.png"
        _overlay(image_path, heats, op, weights=contribs)
        overlay_path = str(op.relative_to(ROOT))

    card = {
        "sample_id": sid,
        "image": str(image_path),
        "verdict": verdict,
        "verdict_text": VERDICT_TEXT[verdict],
        "p_suspect": round(p, 4),
        "backend": pred.get("backend", "lr_main"),
        "degraded": degraded,
        "degraded_reason": degraded_reason,
        "thresholds": {"tau_low": model.thresholds.get("tau_low"),
                       "tau_high": model.thresholds.get("tau_high")},
        "features": {k: round(float(v), 4) for k, v in feats.items()},
        "contributions": {k: round(float(v), 4) for k, v in contribs.items()},
        "heatmaps": heat_paths,
        "overlay": overlay_path,
        "evidence_text": evidence_lines(feats, contribs),
        "recommendation": RECOMMENDATION[verdict],
        "disclaimer": ("本卡为离线取证证据汇总，基于程序化合成数据训练，"
                       "不代表真实平台准确率；低于阈值仅表示未发现所支持的异常，"
                       "不构成对内容真实性的证明。"),
    }
    return card


def save_card(card: dict, path: str | Path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(card, ensure_ascii=False, indent=2), encoding="utf-8")

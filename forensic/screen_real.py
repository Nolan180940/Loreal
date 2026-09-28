# -*- coding: utf-8 -*-
"""真实数据筛查：对目录内所有图片跑取证特征，输出 CSV 与分层小结。

与 train/evaluate 的区别：这里**不输出真伪结论**。真实数据没有可核对的
篡改掩码，任何"真假"断言都无法验证，因此本工具只做三件事：
1. 报告可确证的元数据事实（是否截图、编辑软件痕迹、格式异常）；
2. 报告取证特征的原始统计量，供人判断该数据集是否**适合**像素取证；
3. 明确列出「不可判定」的图片及原因。

用法：
    python -m forensic.screen_real <图片目录> [--out reports/real_screen.csv]
"""

from __future__ import annotations

import argparse
import csv
import time
from pathlib import Path

import numpy as np
from PIL import Image

try:
    from . import features as FT
except ImportError:
    import features as FT  # type: ignore[no-redef]

ROOT = Path(__file__).resolve().parents[1]

EDITOR_MARKS = ("photoshop", "gimp", "meitu", "美图", "snapseed", "lightroom",
                "vsco", "picsart", "canva", "facetune", "airbrush")


def probe_metadata(p: Path) -> dict:
    """只读元数据，不做任何像素分析。全部结论都可逐字复核。"""
    out: dict = {"name": p.name, "suffix": p.suffix.lower(),
                 "kb": round(p.stat().st_size / 1024, 1)}
    try:
        img = Image.open(p)
    except Exception as e:  # noqa: BLE001
        out.update({"readable": False, "reason": f"{type(e).__name__}",
                    "magic": p.read_bytes()[:12].hex()})
        return out
    out["readable"] = True
    out["w"], out["h"] = img.size
    ex = img.getexif()
    out["exif_fields"] = len(ex)
    desc = str(ex.get(0x010e, ""))
    xmp = str(img.info.get("XML:com.adobe.xmp", ""))
    out["is_screenshot"] = ("screenshot" in desc.lower()
                           or "screenshot" in xmp.lower()
                           or "screenshot" in str(ex.get(0x9286, "")).lower())
    out["date_time"] = str(ex.get(0x0132, ""))
    blob = (desc + xmp).lower()
    hits = [m for m in EDITOR_MARKS if m in blob]
    out["editor_marks"] = ",".join(hits)
    out["has_icc"] = "icc_profile" in img.info
    return out


def probe_pixels(p: Path) -> dict:
    """跑取证特征并保留原始量（不套用模型的标定区间）。"""
    t0 = time.time()
    res = FT.extract_all(p)
    aux = res["aux"]
    f = res["features"]
    return {
        "x1_score": round(f["x1_copy_move"], 3),
        "x1_region": aux["x1"].get("largest_region", 0),
        "x1_shift": str(aux["x1"].get("shift", "")),
        "x2_score": round(f["x2_ela"], 3),
        "x2_raw": aux["x2"].get("raw", 0),
        "x3_score": round(f["x3_noise"], 3),
        "x3_sigma": aux["x3"].get("sigma_med", 0),
        "x4_score": round(f["x4_seam"], 3),
        "x4_raw": aux["x4"].get("raw", 0),
        "x5_score": round(f["x5_spectrum"], 3),
        "x5_gamma": aux["x5"].get("gamma", 0),
        "x6_score": round(f["x6_meta"], 3),
        "noise_sigma": round(float(aux["x1"].get("sigma", 0.0)), 3),
        "seconds": round(time.time() - t0, 1),
    }


def judgeability(row: dict) -> tuple[str, str]:
    """判断该图片在**像素取证**层面是否可判定，以及原因。

    核心逻辑：像素取证检测的是「图像自身的采集/压缩历史是否一致」。
    若图片经历了会重写全部像素的环节（例如手机屏幕截图 —— 屏幕渲染会把
    原始压缩痕迹整体重新渲染一遍，且 PNG 保存后完全不含传感器噪声），
    则原始痕迹已不可恢复，任何基于残差/噪声/频谱的判据都失去意义。
    """
    reasons: list[str] = []
    if not row.get("readable"):
        return "不可读", f"文件无法解析（{row.get('reason')}），可能是 HEIC 等容器被改了扩展名"
    if row.get("noise_sigma", 0) < 0.5:
        reasons.append("图像噪声估计≈0（无传感器噪声，典型为屏幕截图或纯合成渲染）")
    if row.get("is_screenshot"):
        reasons.append("元数据自述为 Screenshot")
    if row.get("x2_raw", 0) > 100 and row.get("noise_sigma", 0) < 0.5:
        reasons.append("ELA 残差极高但无噪声，属截图重编码特征而非局部篡改")
    if reasons:
        return "不可判定（像素层）", "；".join(reasons)
    return "可进入人工复核", "未发现上述破坏性环节，但**仍无真值可核对**，只能作为待复核线索"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("folder")
    ap.add_argument("--out", default=str(ROOT / "reports" / "real_screen.csv"))
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()

    folder = Path(args.folder)
    files = sorted(f for f in folder.iterdir() if f.is_file())
    if args.limit:
        files = files[: args.limit]
    print(f"[screen] 目录 {folder}  文件 {len(files)} 个")

    rows: list[dict] = []
    skipped: list[Path] = []
    for i, f in enumerate(files, 1):
        meta = probe_metadata(f)
        if not meta.get("readable"):
            meta.update({"judgement": "不可读", "judge_reason": meta.get("reason", "")})
            rows.append(meta)
            skipped.append(f)
            print(f"  [{i}/{len(files)}] {f.name} 不可读，跳过像素分析")
            continue
        px = probe_pixels(f)
        row = {**meta, **px}
        verdict, why = judgeability(row)
        row["judgement"] = verdict
        row["judge_reason"] = why
        rows.append(row)
        print(f"  [{i}/{len(files)}] {f.name} {px['seconds']}s  "
              f"sigma={px['noise_sigma']} x1={px['x1_score']} x2={px['x2_score']} "
              f"→ {verdict}")

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    keys: list[str] = []
    for r in rows:
        for k in r:
            if k not in keys:
                keys.append(k)
    with out.open("w", newline="", encoding="utf-8-sig") as fh:
        w = csv.DictWriter(fh, fieldnames=keys)
        w.writeheader()
        w.writerows(rows)
    print(f"\n[screen] 已写出 {out}  ({len(rows)} 行)")

    # 分层小结
    n = len(rows)
    shots = sum(1 for r in rows if r.get("is_screenshot"))
    unread = sum(1 for r in rows if not r.get("readable"))
    no_noise = sum(1 for r in rows if r.get("readable") and r.get("noise_sigma", 9) < 0.5)
    editors = [r for r in rows if r.get("editor_marks")]
    print(f"\n[screen] 小结（共 {n} 张）")
    print(f"  元数据自述为截图 : {shots}")
    print(f"  无法解析         : {unread}")
    print(f"  噪声≈0（截图/纯渲染）: {no_noise}")
    print(f"  含编辑软件痕迹   : {len(editors)}"
          + (f"  {[r['name'] for r in editors]}" if editors else ""))
    jd: dict[str, int] = {}
    for r in rows:
        jd[r["judgement"]] = jd.get(r["judgement"], 0) + 1
    print("  可判定性分布：")
    for k, v in sorted(jd.items(), key=lambda t: -t[1]):
        print(f"    {k}: {v}")


if __name__ == "__main__":
    main()

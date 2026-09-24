# -*- coding: utf-8 -*-
"""六维取证特征提取器。统一签名：
extract_xk(img) -> (score∈[0,1], heat HxW float32∈[0,1], aux dict)
只用 numpy / scipy / Pillow。
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image
from scipy import fftpack, ndimage


def load_gray(path: str | Path) -> np.ndarray:
    img = Image.open(path).convert("RGB")
    arr = np.asarray(img).astype(np.float32)
    gray = 0.299 * arr[..., 0] + 0.587 * arr[..., 1] + 0.114 * arr[..., 2]
    return gray


def _norm01(a: np.ndarray) -> np.ndarray:
    a = a.astype(np.float32)
    lo, hi = float(a.min()), float(a.max())
    if hi - lo < 1e-9:
        return np.zeros_like(a)
    return (a - lo) / (hi - lo)


# ---------- 标定（干净训练集上估计，训练前为占位默认值） ----------
#
# 为什么必须标定：x2/x3/x4 的原始统计量是「全图分块离群度的最大值」，属于
# 极值统计量，天生重尾（即使全是干净图，几千个块的 max|z| 也能到几十）。
# 用固定阈值必然要么全判异常（实测：约 1.0 覆盖所有类别），要么全判正常。
# 正确做法是在 train 划分的干净图上测量该统计量的分布，取中位数作下界、
# 取干净图最大值（留余量）作上界，把「异常程度」映射到 [0,1]。
CALIB: dict[str, dict[str, float]] = {
    "x2": {"lo": 9.0, "hi": 136.0},   # x2 原始量是 相位对齐离群块的连通面积
    "x3": {"lo": 6.5, "hi": 26.0},
    "x4": {"lo": 91.0, "hi": 145.0},  # x4 原始量是 行/列剖面 的 max|z|
    "x5": {"lo": 0.08, "hi": 0.35},   # x5 原始量是 |gamma - gamma_ref|
}


def calibrate(raw: float, key: str) -> float:
    c = CALIB.get(key)
    if not c:
        return float(np.clip(raw, 0.0, 1.0))
    lo, hi = c["lo"], c["hi"]
    if hi - lo < 1e-9:
        return 0.0
    return float(np.clip((raw - lo) / (hi - lo), 0.0, 1.0))


def load_calibration(path: str | Path | None = None) -> dict:
    """读取 train.py 标定的常数（各特征映射区间 + 谱斜率参考值）。"""
    global GAMMA_REF, GAMMA_SCALE
    if path is None:
        path = Path(__file__).resolve().parents[1] / "data" / "models" / "calibration.json"
    path = Path(path)
    if not path.is_file():
        return {"loaded": False, "calib": dict(CALIB),
                "GAMMA_REF": GAMMA_REF, "GAMMA_SCALE": GAMMA_SCALE}
    import json
    cfg = json.loads(path.read_text(encoding="utf-8"))
    for k, v in cfg.get("calib", {}).items():
        if k in ("x2", "x3", "x4", "x5"):
            CALIB[k] = {"lo": float(v["lo"]), "hi": float(v["hi"])}
        elif k == "x1":
            pass
    x5 = cfg.get("x5", {})
    GAMMA_REF = float(x5.get("gamma_ref", GAMMA_REF))
    GAMMA_SCALE = float(x5.get("gamma_scale", GAMMA_SCALE))
    return {"loaded": True, "calib": dict(CALIB),
            "GAMMA_REF": GAMMA_REF, "GAMMA_SCALE": GAMMA_SCALE}


# ---------- x1 复制-移动 ----------

def extract_x1(img: np.ndarray, min_shift: int = 24, max_shift: int = 400,
               min_region: int = 400, k_cand: int = 120, std_win: int = 8,
               min_local_std: float = 2.5, tol_ratio: float = 0.45,
               full_scale: float = 4096.0, hp_sigma: float = 1.5,
               nms_size: int = 41, tile: int = 16, tile_frac: float = 0.30):
    """复制-移动检测：高通 + FFT 自相关多候选位移 + 噪声自适应像素差验证。

    为什么不用分块匹配：分块网格（即使步长 8）与随机像素位移不对齐时，被复制
    的内容落在网格上的采样相位不同，块描述子根本不会相等——这是前几版在
    合成复制样本上「真阳性为 0」的直接原因。自相关在全域所有整数位移上搜索，
    天然对齐任何像素级位移，且一次 FFT 得到全部位移。

    四条必要的判据（每条都是实测踩坑后补的）：
    1. 高通预滤波：全局自相关中复制区域只占总能量千分之几，会被大尺度结构
       （垂直渐变在水平位移下几乎不变、软边物体）完全淹没；先减去高斯低频，
       让细节纹理主导相关面，真实复制峰才浮现。
    2. 大半径非极大值抑制 + 多候选验证：复制在自相关面上形成的是「宽平台」
       （宽度约等于复制区尺寸），用小半径找局部极大会被切成上千个点、导致真实
       峰排名虚高（实测排名 21~1587）。必须用 ~40px 半径 NMS 让每个平台只出
       一个代表点，再取前 k_cand 个逐一验证（验证便宜且极具体，误报率极低）。
    3. 噪声自适应容差：容差取图像噪声尺度（MAD 估计）的固定比例而非绝对值，
       否则过度平滑的图（滤镜/缩放）会因绝对差本来就小而被判成匹配。
    4. 纹理约束：平坦区（纯色填充、强模糊）与自身在任何位移下都近乎相同，
       必须要求匹配区局部标准差高于阈值，否则滤镜/缩放/纯色填充全被误报。
    """
    h, w = img.shape
    gf = img.astype(np.float32)

    # 噪声尺度估计（MAD of 中值滤波残差），用于自适应容差
    resid = gf - ndimage.median_filter(gf, size=3)
    sigma = float(1.4826 * np.median(np.abs(resid))) + 1e-6
    tol = max(0.8, tol_ratio * sigma)

    # 局部标准差图（纹理度），用于排除平坦区
    m1 = ndimage.uniform_filter(gf, std_win)
    m2 = ndimage.uniform_filter(gf * gf, std_win)
    lstd = np.sqrt(np.maximum(m2 - m1 * m1, 0.0))
    textured = lstd > min_local_std

    # 高通后做自相关
    hp = gf - ndimage.gaussian_filter(gf, hp_sigma)
    g = (hp - hp.mean()) / (hp.std() + 1e-6)
    Fc = np.fft.rfft2(g)
    ac_raw = np.fft.irfft2(Fc * np.conj(Fc), s=g.shape)
    total = float(ac_raw[0, 0]) + 1e-9
    ac = np.fft.fftshift(ac_raw) / total

    cy, cx = h // 2, w // 2
    dy_axis = np.arange(h) - cy
    dx_axis = np.arange(w) - cx
    yy, xx = dy_axis[:, None], dx_axis[None, :]
    r = np.sqrt(yy ** 2 + xx ** 2)
    valid = (r > min_shift) & (r < max_shift)

    env = ndimage.uniform_filter(ac, size=31)
    anomaly = ac - env
    anomaly[~valid] = -np.inf

    mx = ndimage.maximum_filter(anomaly, size=nms_size)
    is_peak = (anomaly >= mx) & np.isfinite(anomaly) & (anomaly > 0)
    pys, pxs = np.nonzero(is_peak)
    if len(pys) == 0:
        return 0.0, np.zeros((h, w), dtype=np.float32), {
            "peak": 0.0, "reason": "no_peak"}
    vals = anomaly[pys, pxs]
    order = np.argsort(vals)[::-1][:k_cand]

    best = None  # (largest, dy, dx, slice_info, comp, peak_value)
    for oi in order:
        py, px = int(pys[oi]), int(pxs[oi])
        dy, dx = int(dy_axis[py]), int(dx_axis[px])
        ys0, ys1 = max(0, dy), min(h, h + dy)
        xs0, xs1 = max(0, dx), min(w, w + dx)
        a = gf[ys0:ys1, xs0:xs1]
        b = gf[ys0 - dy:ys1 - dy, xs0 - dx:xs1 - dx]
        tex = textured[ys0:ys1, xs0:xs1] & textured[ys0 - dy:ys1 - dy, xs0 - dx:xs1 - dx]
        hit = (np.abs(a - b) < tol) & tex

        # 廉价瓦片预筛：真复制区内必有整块高命中瓦片；零散命中没有。
        # 不做预筛时每个候选都要跑全图开运算+连通域，实测每图 >3 秒。
        Hh, Ww = hit.shape
        if Hh < tile or Ww < tile:
            continue
        hc, wc = Hh // tile, Ww // tile
        tsum = hit[:hc * tile, :wc * tile].reshape(hc, tile, wc, tile).sum(axis=(1, 3))
        if int(tsum.max()) < tile_frac * tile * tile:
            continue

        hit = ndimage.binary_opening(hit, structure=np.ones((3, 3)))
        lab, nlab = ndimage.label(hit)
        if nlab == 0:
            continue
        sizes = ndimage.sum(hit, lab, index=np.arange(1, nlab + 1))
        k = int(np.argmax(sizes)) + 1
        largest = int(sizes[k - 1])
        if largest < min_region:
            continue
        if best is None or largest > best[0]:
            best = (largest, dy, dx, (ys0, ys1, xs0, xs1), (lab == k),
                    float(anomaly[py, px]))
        if largest >= full_scale * 3:
            break  # 已足够显著，提前退出

    if best is None:
        return 0.0, np.zeros((h, w), dtype=np.float32), {
            "largest_region": 0, "sigma": round(sigma, 2), "tol": round(tol, 2),
            "n_cand": int(len(order))}

    largest, dy, dx, (ys0, ys1, xs0, xs1), comp, peak_val = best
    score = float(np.clip(largest / full_scale, 0.0, 1.0))
    heat = np.zeros((h, w), dtype=np.float32)
    heat[ys0:ys1, xs0:xs1] += comp.astype(np.float32)
    heat[ys0 - dy:ys1 - dy, xs0 - dx:xs1 - dx] += comp.astype(np.float32)
    heat = _norm01(ndimage.gaussian_filter(heat, 2))
    aux = {"largest_region": largest, "shift": [dy, dx], "peak": round(peak_val, 5),
           "sigma": round(sigma, 2), "tol": round(tol, 2),
           "n_cand": int(len(order))}
    return score, heat, aux


# ---------- x2 ELA ----------

def extract_x2(path: str | Path, quality: int = 90, blk: int = 8,
               period: int = 2, k: float = 3.0, z_cap: float = 60.0):
    """ELA 相位对齐版：重压缩残差在**同相位**邻块间的区域性离群面积。

    为什么必须是 8px 块 + 同相位比较（两版失败的教训）：
    1. 用 16px 分析网格去量 JPEG 的 8px 块效应会产生**拍频混叠**：16px 块跨
       两个不同相位的 JPEG 块，块效应在 16px 尺度上表现为周期性抖动，被局部
       基线误判成"区域性异常"。实测后果：JPEG 重压缩硬负例的 ELA 异常度被推到
       1.0，而 LR 只能学出一个**负权重**（-0.395）去压制它 —— 这是"特征语义
       反了"的典型征兆。
    2. 改用 8px 块（与 JPEG 网格同尺度）并与**间隔 period 个块**的邻居比较：
       间隔 2 个块 = 16px = 同一 JPEG 相位，周期性块效应在比较中相互抵消，
       只剩区域性差异。实测效果：干净图归一化值 0.000、
       涂改数字 1.000、**拼接 1.000（旧版完全检不出）**，特征权重翻正为 +1.078。
    3. z 必须做稳健截断（cap=60）：退化情形的 MAD 可趋近 0，实测单图 z 达
       2.2e6，会污染标定区间。

    已知局限（如实记录）：**良性重压缩与局部篡改产生同类证据**，这是图像取证
    的本质歧义 —— 实测 JPEG Q70/Q90 硬负例同样得到 1.000，当前只能靠 LR 的
    阈值与其它维度联合压制。彻底解决需要显式估计压缩历史再做归一化（后续工作）。
    """
    from io import BytesIO
    img = Image.open(path).convert("RGB")
    buf = BytesIO()
    img.save(buf, format="JPEG", quality=quality)
    buf.seek(0)
    re_img = Image.open(buf).convert("RGB")
    a = np.asarray(img).astype(np.float32)
    b = np.asarray(re_img).astype(np.float32)
    diff = np.abs(a - b).mean(axis=2)
    h, w = diff.shape
    hb, wb = h // blk, w // blk
    if hb < 2 * period + 2 or wb < 2 * period + 2:
        return 0.0, np.zeros((h, w), dtype=np.float32), {"raw": 0.0, "note": "too_small"}
    bm = diff[:hb * blk, :wb * blk].reshape(hb, blk, wb, blk).mean(axis=(1, 3))

    diffs = []
    for dy in (period, -period):
        d = np.full_like(bm, np.nan)
        if dy > 0:
            d[dy:, :] = np.abs(bm[dy:, :] - bm[:-dy, :])
        else:
            d[:dy, :] = np.abs(bm[:dy, :] - bm[-dy:, :])
        diffs.append(d)
    for dx in (period, -period):
        d = np.full_like(bm, np.nan)
        if dx > 0:
            d[:, dx:] = np.abs(bm[:, dx:] - bm[:, :-dx])
        else:
            d[:, :dx] = np.abs(bm[:, :dx] - bm[:, -dx:])
        diffs.append(d)
    dev = np.nan_to_num(np.nanmax(np.stack(diffs), axis=0))
    med = float(np.median(dev))
    mad = float(np.median(np.abs(dev - med))) * 1.4826 + 1e-6
    z = np.clip((dev - med) / mad, 0.0, z_cap)

    m = ndimage.binary_opening(z > k, structure=np.ones((1, 2)))
    m2 = ndimage.binary_opening((z.T > k), structure=np.ones((1, 2))).T
    l1, n1 = ndimage.label(m)
    l2, n2 = ndimage.label(m2)
    a1 = max([int((l1 == i).sum()) for i in range(1, n1 + 1)] + [0])
    a2 = max([int((l2 == i).sum()) for i in range(1, n2 + 1)] + [0])
    area = float(max(a1, a2))
    score = calibrate(area, "x2")
    # 热区：达阈值块（含两个方向）映射回原尺寸
    hit = ((z > k) | (z.T > k).T).astype(np.float32)
    heat = ndimage.zoom(hit, (blk, blk), order=0)[:h, :w]
    heat = _norm01(ndimage.gaussian_filter(heat, 4))
    return score, heat, {"raw": round(area, 1), "z_max": round(float(z.max()), 2),
                         "med_dev": round(med, 3)}


# ---------- x3 噪声残差 ----------

def extract_x3(img: np.ndarray, blk: int = 16, nbhd: int = 5, z_heat_k: float = 3.0):
    """噪声水平局部异常：局部噪声强度与周围不一致。

    机制：中值滤波残差（近似高频噪声）的分块能量，再与邻域基线比较。
    能抓到三类现象：
    - 纯色/无噪声填充（数字涂改）：局部噪声≈0，远低于周围；
    - 拼接：两半噪声相位/水平不同；
    - AI 重绘/抹除：过度平滑区域噪声缺失。
    同样必须用邻域而非全局基线：整图滤镜/美颜会整体改变噪声水平（硬负例），
    全局基线会把它们全判成异常。
    """
    r = img - ndimage.median_filter(img, size=3)
    h, w = r.shape
    hb, wb = h // blk, w // blk
    if hb < nbhd or wb < nbhd:
        return 0.0, np.zeros((h, w), dtype=np.float32), {"note": "too_small"}
    sig = r[:hb * blk, :wb * blk]
    # 分块噪声强度：用块内 |r| 的中位数估计（对纹理边缘稳健）
    sigmap = np.median(np.abs(sig).reshape(hb, blk, wb, blk).transpose(0, 2, 1, 3),
                       axis=(2, 3)) * 1.4826
    local_med = ndimage.median_filter(sigmap, size=nbhd)
    local_mad = ndimage.median_filter(np.abs(sigmap - local_med), size=nbhd) * 1.4826 + 1e-6
    z = (sigmap - local_med) / local_mad
    maxz = float(np.abs(z).max())
    score = calibrate(maxz, "x3")
    # 热区只标记真正离群的块（|z| > k），否则 _norm01 会把整图拉亮，
    # 使"标出可疑之处"变成一片红、失去定位意义（实测旧版覆盖 786429/786432 像素）。
    heat_blocks = np.zeros_like(z, dtype=np.float32)
    heat_blocks[np.abs(z) > z_heat_k] = 1.0
    heat = _norm01(ndimage.zoom(heat_blocks, (blk, blk), order=1)[:h, :w])
    return score, heat, {"raw": round(maxz, 2), "n_hot_blocks": int(heat_blocks.sum()),
                         "sigma_med": round(float(np.median(sigmap)), 2)}


# ---------- x4 DCT 网格 ----------

def extract_x4(img: np.ndarray, hp_sigma: float = 1.5, med: int = 41,
               rel_floor: float = 0.05):
    """行/列剖面的孤立离群度：高通能量 + 低频亮度剖面。

    归一化必须用「剖面自身的动态范围」做下界，不能用下面两种：
    - 绝对灰度下界：剖面水平 ~130 而波动只有几，下界（2.6）会压死所有信号，
      实测所有类别 z 都收敛到同一个 ~1.0；
    - 偏差的 MAD：平滑单调的剖面会让 dev≈常数，MAD(dev)≈0，z 虚高到百万量级，
      实测全图皆异常。
    用 0.05 × (P95−P5) 作为下界后，两者都解决。

    已知局限（如实记录，不掩盖）：本特征针对**沿整条直线**的接缝。实测在
    「两半同源、仅注入轻度曝光差」的合成拼接上，亮度台阶被高斯羽化摊平到
    约 25 像素宽，逐像素梯度与图内软边物体同量级，**不足以稳定区分**。真实
    世界的假「前后对比」图主要靠两侧**内容语义**（场景/尺度/光照）矛盾暴露，
    那属于语义层（x7 / 人工复核）的职责，不是像素层能解决的。
    """
    gf = img.astype(np.float32)
    hp = np.abs(gf - ndimage.gaussian_filter(gf, hp_sigma))
    blur = ndimage.gaussian_filter(gf, 4.0)

    def prof_z(prof: np.ndarray) -> tuple[float, np.ndarray]:
        base = ndimage.median_filter(prof, size=med, mode="nearest")
        dev = prof - base
        spread = float(np.percentile(prof, 95) - np.percentile(prof, 5))
        floor = max(rel_floor * spread, 1e-3)
        mad = float(np.median(np.abs(dev - np.median(dev)))) * 1.4826
        z = dev / max(mad, floor)
        return float(np.abs(z).max()), z

    zc_hf, z_c = prof_z(hp.mean(axis=0))
    zr_hf, z_r = prof_z(hp.mean(axis=1))
    zc_dc, zc_d = prof_z(blur.mean(axis=0))
    zr_dc, zr_d = prof_z(blur.mean(axis=1))

    z_hf = max(zc_hf, zr_hf)
    z_dc = max(zc_dc, zr_dc)
    maxz = max(z_hf, z_dc)
    score = calibrate(maxz, "x4")

    # 热区：只画**最离群的 top-K 条**行/列。
    # 不能用固定 |z| > k 阈值：高频剖面的 MAD 可能极小，导致 z 整体虚高
    # （实测 z_hf=86.92 → 250 条"热线条"，热区占 26% 画面，等于没有定位）。
    # 取 top-K 既保证稀疏可读，语义上也正确：最异常的那几条线才是候选接缝。
    def topk_mask(z: np.ndarray, k: int = 3) -> np.ndarray:
        m = np.zeros_like(z, dtype=np.float32)
        if z.size == 0:
            return m
        idx = np.argsort(np.abs(z))[::-1][:k]
        m[idx] = 1.0
        return ndimage.binary_dilation(m > 0, iterations=2).astype(np.float32)

    if z_dc >= z_hf:
        rows_m, cols_m = topk_mask(zr_d), topk_mask(zc_d)
    else:
        rows_m, cols_m = topk_mask(z_r), topk_mask(z_c)
    heat = np.outer(rows_m, np.ones_like(cols_m)) + np.outer(np.ones_like(rows_m), cols_m)
    heat = _norm01(np.clip(heat, 0, 1).astype(np.float32))
    return score, heat, {"raw": round(maxz, 2), "z_hf": round(z_hf, 2),
                         "z_dc": round(z_dc, 2),
                         "n_hot_lines": int(rows_m.sum() + cols_m.sum())}


# ---------- x5 频谱 ----------

# 参考径向谱斜率与尺度，由 train.py 在 train 划分的原图上标定后写入
# data/models/calibration.json；缺省值只是占位（未标定时 x5 不可用于判定）。
GAMMA_REF = -2.0
GAMMA_SCALE = 0.35


def extract_x5(img: np.ndarray, gamma_ref: float | None = None,
               gamma_scale: float | None = None):
    """径向功率谱斜率异常：整图级处理/AI 生成会改变自然图像的谱斜率。

    注意这是「整图」证据，不能定位，也不可能区分具体篡改方式，因此
    在证据卡里只做辅助说明。未标定参考值时分数不可用于判定。
    """
    ref = GAMMA_REF if gamma_ref is None else gamma_ref
    scale = GAMMA_SCALE if gamma_scale is None else gamma_scale
    F = np.fft.fftshift(np.fft.fft2(img - img.mean()))
    mag = np.abs(F)
    h, w = mag.shape
    yy, xx = np.ogrid[:h, :w]
    rr = np.sqrt((yy - h / 2) ** 2 + (xx - w / 2) ** 2).astype(int)
    rmax = min(h, w) // 2
    radial = np.asarray(ndimage.mean(mag, labels=rr, index=np.arange(1, rmax)),
                        dtype=np.float64) + 1e-9
    x = np.log(np.arange(1, len(radial) + 1))
    y = np.log(radial)
    A = np.vstack([x, np.ones_like(x)]).T
    gamma = float(np.linalg.lstsq(A, y, rcond=None)[0][0])
    raw = abs(gamma - ref)
    score = calibrate(raw, "x5")
    heat = np.zeros_like(img, dtype=np.float32)  # 非定位，仅用于展示
    return score, heat, {"raw": round(raw, 3), "gamma": round(gamma, 3),
                         "gamma_ref": round(ref, 3)}


# ---------- x6 元数据 ----------

def extract_x6(path: str | Path):
    img = Image.open(path)
    score, note = 0.5, "no exif -> neutral"
    try:
        exif = img.getexif()
        if exif and len(exif) > 0:
            soft = str(exif.get(0x0131, "")) + str(exif.get(0x9286, ""))
            if any(k in soft.lower() for k in ("photoshop", "gimp", "meitu", "snapseed")):
                score, note = 0.7, f"editor trace: {soft[:60]}"
            else:
                score, note = 0.4, "exif present, no editor trace"
    except Exception as e:  # noqa: BLE001
        note = f"exif read fail: {e}"
    h, w = Image.open(path).size[1], Image.open(path).size[0]
    heat = np.zeros((h, w), dtype=np.float32)
    return score, heat, {"note": note}


# ---------- 统一入口 ----------

def extract_all(path: str | Path):
    gray = load_gray(path)
    out: dict = {}
    heats: dict = {}
    aux: dict = {}
    s, heat, a = extract_x1(gray)
    out["x1_copy_move"], heats["x1"], aux["x1"] = s, heat, a
    s, heat, a = extract_x2(path)
    out["x2_ela"], heats["x2"], aux["x2"] = s, heat, a
    s, heat, a = extract_x3(gray)
    out["x3_noise"], heats["x3"], aux["x3"] = s, heat, a
    s, heat, a = extract_x4(gray)
    out["x4_seam"], heats["x4"], aux["x4"] = s, heat, a
    s, heat, a = extract_x5(gray)
    out["x5_spectrum"], heats["x5"], aux["x5"] = s, heat, a
    s, heat, a = extract_x6(path)
    out["x6_meta"], heats["x6"], aux["x6"] = s, heat, a
    return {"features": out, "heats": heats, "aux": aux}

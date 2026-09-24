# -*- coding: utf-8 -*-
"""程序化数据生成器：合成底图 / 篡改 / 硬负例 / 掩码 / labels.csv。

只用 numpy + Pillow。种子固定可复现。
"""

from __future__ import annotations

import csv
import hashlib
import json
import random
from dataclasses import dataclass, asdict
from io import BytesIO
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter
from scipy import ndimage

SEED = 20260924
W, H = 1024, 768  # 统一尺寸


# ---------- 底图 ----------

def make_base(rng: np.random.Generator, w: int = W, h: int = H) -> Image.Image:
    """照片式合成底图：渐变 + 多尺度分形纹理 + 软边物体 + 终末传感器噪声。

    关键：噪声必须在所有绘制之后叠加。若噪声先加，绘制出的硬边实体色块会
    含有大量逐像素完全相同的块，使复制-移动检测在干净图上疯狂误报（这是
    前几版冒烟失败的直接原因）。
    """
    # 1) 垂直渐变背景
    top = rng.integers(150, 210, 3).astype(np.float32)
    bottom = rng.integers(80, 140, 3).astype(np.float32)
    t = np.linspace(0, 1, h, dtype=np.float32)[:, None, None]
    base = (top[None, None, :] * (1 - t) + bottom[None, None, :] * t)
    base = np.broadcast_to(base, (h, w, 3)).copy()
    # 2) 多尺度分形纹理（模拟布料/桌面/皮肤的非均匀质感）
    for scale, amp in ((64, 14.0), (24, 8.0), (8, 4.0)):
        small = rng.normal(0, 1, (max(2, h // scale), max(2, w // scale), 1))
        up = ndimage.zoom(small, (h / small.shape[0], w / small.shape[1], 1), order=1)
        base += amp * up[:h, :w]
    img = Image.fromarray(np.clip(base, 0, 255).astype(np.uint8))

    # 3) 软边物体（模拟产品/包装，用独立图层 + 高斯模糊边缘）
    layer = Image.new("RGB", (w, h), (0, 0, 0))
    lmask = Image.new("L", (w, h), 0)
    ld, lm = ImageDraw.Draw(layer), ImageDraw.Draw(lmask)
    for _ in range(int(rng.integers(3, 7))):
        x = int(rng.integers(0, w - 200))
        y = int(rng.integers(0, h - 200))
        bw = int(rng.integers(120, 320))
        bh = int(rng.integers(120, 320))
        color = tuple(int(v) for v in rng.integers(40, 220, 3))
        ld.rectangle((x, y, min(w, x + bw), min(h, y + bh)), fill=color)
        lm.rectangle((x, y, min(w, x + bw), min(h, y + bh)), fill=210)
    lmask = lmask.filter(ImageFilter.GaussianBlur(2.5))
    img = Image.composite(layer, img, lmask)

    # 4) 文字条（位置写入 info，供数字涂改使用）
    img = img.filter(ImageFilter.GaussianBlur(0.8))
    draw = ImageDraw.Draw(img)
    x = int(rng.integers(30, w - 320))
    y = int(rng.integers(30, h - 60))
    draw.rectangle((x, y, x + 260, y + 36), fill=(245, 245, 245))
    price = f"{int(rng.integers(19, 399))}.{int(rng.integers(0, 9))}"
    draw.text((x + 12, y + 10), f"price {price} shade 02", fill=(20, 20, 20))

    # 5) 终末传感器噪声：保证任意两块不再逐像素相同（照片的基本性质）
    arr = np.asarray(img).astype(np.float32) + rng.normal(0, 7.0, (h, w, 3))
    img = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))
    img.info["text_box"] = (x, y, x + 260, y + 36)
    return img


def feather(mask: Image.Image, radius: int = 1) -> Image.Image:
    if radius <= 0:
        return mask
    return mask.filter(ImageFilter.GaussianBlur(radius))


# ---------- 篡改算子 ----------

@dataclass
class Sample:
    sample_id: str
    image_path: str
    mask_path: str
    y: int | None  # 1 假 / 0 真 / None 不确定（本生成器不产 NA）
    op: str
    params: dict
    split: str
    base_id: str
    source: str


def _save(img: Image.Image, path: Path) -> None:
    img.save(path, format="PNG")


def op_copy_move(img: Image.Image, rng: np.random.Generator,
                 size: int, src: tuple[int, int], dst: tuple[int, int]):
    """复制源块贴到目标处。返回 (新图, 掩码)。"""
    arr = np.asarray(img).copy()
    sx, sy = src
    dx, dy = dst
    patch = arr[sy:sy + size, sx:sx + size].copy()
    arr[dy:dy + size, dx:dx + size] = patch
    out = Image.fromarray(arr)
    mask = Image.new("L", img.size, 0)
    d = ImageDraw.Draw(mask)
    d.rectangle((sx, sy, sx + size, sy + size), fill=255)
    d.rectangle((dx, dy, dx + size, dy + size), fill=255)
    return out, mask


def _recolor(img: Image.Image, gain: float, wb: tuple[float, float, float],
             bias: float) -> Image.Image:
    """模拟不同的曝光/白平衡（真实「假前后对比」图两侧常有的差异）。"""
    arr = np.asarray(img).astype(np.float32)
    arr = arr * gain * np.asarray(wb, dtype=np.float32)[None, None, :] + bias
    return Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))


def op_splice(img_a: Image.Image, img_b: Image.Image, rng: np.random.Generator,
              seam_x: int, feather_px: int = 1):
    """左右半区拼接，缝两侧羽化。

    关键（来自实测）：若两半来自「同源同曝光」的合成底图，拼接在像素统计上
    与真实图完全不可分（实测 DC 台阶 8.75 vs 干净图 8.75，高频剖面相差不多）
    —— 即不存在任何可检测的像素证据。真实世界的「假前后对比」拼接图几乎
    总伴随两侧照明/色温/锐度/曝光的差异（不同时间、不同光源拍摄），故生成器
    显式注入这类差异，使样本与真实现象一致。
    已知盲区：两侧完全同源同曝光的无缝拼接仍可能检不出，报告中单列。
    """
    gain = float(rng.uniform(0.82, 1.18))
    wb = tuple(float(v) for v in rng.uniform(0.94, 1.06, 3))
    bias = float(rng.uniform(-12.0, 12.0))
    img_b2 = _recolor(img_b, gain, wb, bias)
    if rng.random() < 0.5:
        img_b2 = img_b2.filter(ImageFilter.GaussianBlur(1.1))
    else:
        img_b2 = img_b2.filter(ImageFilter.UnsharpMask(radius=2, percent=90))

    w, h = img_a.size
    seam = Image.new("L", (w, h), 0)
    d = ImageDraw.Draw(seam)
    d.rectangle((0, 0, seam_x, h), fill=255)
    seam = feather(seam, feather_px)
    out = Image.composite(img_a, img_b2, seam)
    mask = Image.new("L", (w, h), 0)
    d = ImageDraw.Draw(mask)
    d.rectangle((max(0, seam_x - 8), 0, min(w, seam_x + 8), h), fill=255)
    return out, mask, {"gain": round(gain, 3), "wb": [round(v, 3) for v in wb],
                       "bias": round(bias, 2)}


def op_digit_edit(img: Image.Image, rng: np.random.Generator,
                  box: tuple[int, int, int, int], new_text: str = "￥29.9 05号色"):
    """覆盖重写文字条数字。"""
    out = img.copy()
    d = ImageDraw.Draw(out)
    d.rectangle(box, fill=(245, 245, 245))
    d.text((box[0] + 12, box[1] + 10), new_text, fill=(20, 20, 20))
    mask = Image.new("L", img.size, 0)
    ImageDraw.Draw(mask).rectangle(box, fill=255)
    return out, mask


def op_ai_like(img: Image.Image, rng: np.random.Generator):
    """频谱异常模拟（占位，非真 AI 样本）：抑制中高频 + 网格伪影。"""
    import numpy.fft as fft
    arr = np.asarray(img).astype(np.float32)
    out = np.zeros_like(arr)
    for c in range(3):
        F = fft.fftshift(fft.fft2(arr[..., c]))
        yy, xx = np.ogrid[:H, :W]
        r = np.sqrt((yy - H / 2) ** 2 + (xx - W / 2) ** 2)
        F[r > min(H, W) * 0.25] *= 0.55  # 抑制中高频
        F[::8, :] *= 1.06  # 网格伪影
        out[..., c] = np.abs(fft.ifft2(fft.ifftshift(F)))
    out = np.clip(out, 0, 255).astype(np.uint8)
    mask = Image.new("L", img.size, 0)  # 全图异常，无定位
    return Image.fromarray(out), mask


def op_hard_negative(img: Image.Image, rng: np.random.Generator, kind: str):
    """硬负例：滤镜/美颜/压缩/缩放/锐化。返回 (新图, 全黑掩码)。"""
    if kind == "blur_beauty":
        out = img.filter(ImageFilter.GaussianBlur(3.0))
        out = Image.blend(img, out, 0.6)
    elif kind == "warm_filter":
        arr = np.asarray(img).astype(np.float32)
        arr[..., 0] *= 1.08
        arr[..., 2] *= 0.92
        out = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))
    elif kind == "jpeg_q70":
        buf = BytesIO()
        img.save(buf, format="JPEG", quality=70)
        buf.seek(0)
        out = Image.open(buf).convert("RGB")
    elif kind == "jpeg_q90":
        buf = BytesIO()
        img.save(buf, format="JPEG", quality=90)
        buf.seek(0)
        out = Image.open(buf).convert("RGB")
    elif kind == "rescale":
        small = img.resize((W * 3 // 4, H * 3 // 4), Image.BILINEAR)
        out = small.resize((W, H), Image.BILINEAR)
    elif kind == "sharpen":
        out = img.filter(ImageFilter.UnsharpMask(radius=2, percent=120))
    else:
        raise ValueError(kind)
    return out, Image.new("L", img.size, 0)


# ---------- 主流程 ----------

def generate(root: Path, n_base: int = 50, seed: int = SEED,
             train_ratio: float = 0.7) -> list[Sample]:
    rng = np.random.default_rng(seed)
    py_rng = random.Random(seed)
    img_dir = root / "images"
    mask_dir = root / "masks"
    base_dir = root / "base"
    for d in (img_dir, mask_dir, base_dir):
        d.mkdir(parents=True, exist_ok=True)

    samples: list[Sample] = []
    base_ids = [f"base_{i:03d}" for i in range(n_base)]
    # 按 base_id 划分 split（防泄漏）
    py_rng.shuffle(base_ids)
    n_train = int(n_base * train_ratio)
    split_of = {b: ("train" if i < n_train else "val") for i, b in enumerate(base_ids)}

    sid = 0

    def add(img, mask, y, op, params, base_id, source="synth"):
        nonlocal sid
        sid += 1
        sample_id = f"s{sid:03d}"
        ipath = img_dir / f"{sample_id}.png"
        mpath = mask_dir / f"{sample_id}.png"
        _save(img, ipath)
        _save(mask.convert("L"), mpath)
        samples.append(Sample(sample_id, str(ipath), str(mpath), y, op,
                              params, split_of[base_id], base_id, source))

    bases: dict[str, Image.Image] = {}
    for b in base_ids:
        img = make_base(rng)
        bases[b] = img
        img.save(base_dir / f"{b}.png")

    neg_kinds = ["blur_beauty", "warm_filter", "jpeg_q70", "jpeg_q90",
                 "rescale", "sharpen"]

    for b in base_ids:
        img = bases[b]
        # 真样本：原图
        add(img, Image.new("L", img.size, 0), 0, "original", {}, b)
        # copy_move
        size = int(rng.integers(64, 161))
        sx = int(rng.integers(0, W - size))
        sy = int(rng.integers(0, H - size))
        dx = int(np.clip(sx + int(rng.integers(64, 300))
                         * (1 if rng.random() < 0.5 else -1), 0, W - size))
        dy = int(np.clip(sy + int(rng.integers(64, 220))
                         * (1 if rng.random() < 0.5 else -1), 0, H - size))
        out, mask = op_copy_move(img, rng, size, (sx, sy), (dx, dy))
        add(out, mask, 1, "copy_move",
            {"size": size, "src": [sx, sy], "dst": [dx, dy]}, b)
        # splice（与下一张底图拼接，注入真实的前后对比差异）
        b2 = base_ids[(base_ids.index(b) + 1) % len(base_ids)]
        seam_x = int(rng.integers(W // 3, 2 * W // 3))
        out, mask, mism = op_splice(img, bases[b2], rng, seam_x)
        add(out, mask, 1, "splice", {"seam_x": seam_x, "other": b2, **mism}, b)
        # digit_edit（用底图真实文字条位置，保证涂改落在文字上）
        box = img.info.get("text_box", (60, 60, 320, 96))
        out, mask = op_digit_edit(img, rng, box)
        add(out, mask, 1, "digit_edit", {"box": list(box)}, b)
        # ai_like 占位（仅部分底图）
        if base_ids.index(b) % 5 == 0:
            out, mask = op_ai_like(img, rng)
            add(out, mask, 1, "ai_like", {}, b, source="ai_like")
        # 硬负例轮转 2 种
        for k in py_rng.sample(neg_kinds, 2):
            out, mask = op_hard_negative(img, rng, k)
            add(out, mask, 0, f"neg_{k}", {"kind": k}, b)

    # labels.csv
    with (root / "labels.csv").open("w", newline="", encoding="utf-8") as f:
        w_ = csv.writer(f)
        w_.writerow(["sample_id", "image_path", "mask_path", "y", "op",
                     "params_json", "split", "base_id", "source"])
        for s in samples:
            w_.writerow([s.sample_id, s.image_path, s.mask_path, s.y, s.op,
                         json.dumps(s.params, ensure_ascii=False),
                         s.split, s.base_id, s.source])
    return samples


if __name__ == "__main__":
    import sys
    root = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("data")
    ss = generate(root)
    print(f"generated {len(ss)} samples -> {root.resolve()}")

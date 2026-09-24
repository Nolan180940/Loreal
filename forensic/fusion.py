# -*- coding: utf-8 -*-
"""融合与判定：加载主模型、输出概率与逐维贡献、三段判定。

三段判定的纪律（写在枚举语义里，避免下游误读）：
    suspicious              发现可疑：给出证据与热区
    insufficient_evidence   证据不足：建议人工复核
    no_anomaly_supported    未发现所支持的异常（**不是**「证明为真」）
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

try:
    from . import features as FT
except ImportError:
    import features as FT  # type: ignore[no-redef]

ROOT = Path(__file__).resolve().parents[1]
MODEL_DIR = ROOT / "data" / "models"

VERDICT_SUSPICIOUS = "suspicious"
VERDICT_UNCERTAIN = "insufficient_evidence"
VERDICT_NO_ANOMALY = "no_anomaly_supported"

FEATURE_LABELS = {
    "x1_copy_move": "复制-移动痕迹",
    "x2_ela": "重压缩不一致(ELA)",
    "x3_noise": "局部噪声异常",
    "x4_seam": "直线接缝异常",
    "x5_spectrum": "频谱斜率异常",
    "x6_meta": "元数据/内容凭证",
}


def _sigmoid(z: float) -> float:
    return float(1.0 / (1.0 + np.exp(-np.clip(z, -30, 30))))


class FusionModel:
    """6 维主模型 + 可选 logit 堆叠（Jev 语义信号作第 7 维）。"""

    def __init__(self, model_path: Path | None = None,
                 feature_keys: list[str] | None = None):
        import joblib
        self.model_path = Path(model_path) if model_path else MODEL_DIR / "lr_main.joblib"
        if not self.model_path.is_file():
            raise FileNotFoundError(
                f"未找到主模型 {self.model_path}，请先运行 python -m forensic.train")
        self.pipe = joblib.load(self.model_path)
        meta_path = MODEL_DIR / "lr_meta.json"
        if feature_keys is None and meta_path.is_file():
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            feature_keys = meta.get("feature_keys")
        self.feature_keys = feature_keys or [
            "x1_copy_move", "x2_ela", "x3_noise", "x4_seam", "x5_spectrum", "x6_meta"]
        self.stack = None
        sp = MODEL_DIR / "lr_stack.joblib"
        if sp.is_file():
            try:
                self.stack = joblib.load(sp)
            except Exception:  # noqa: BLE001
                self.stack = None
        self.thresholds = self._load_thresholds()

    @staticmethod
    def _load_thresholds() -> dict:
        p = MODEL_DIR / "thresholds.json"
        if p.is_file():
            return json.loads(p.read_text(encoding="utf-8"))
        return {"tau_low": 0.30, "tau_high": 0.70}

    # ---- 主模型 ----

    def contributions(self, x: dict[str, float]) -> dict[str, float]:
        """标准化空间里的逐维贡献 w_i * z_i，直接可读作「这一维把分数推高多少」。"""
        vec = np.array([[float(x.get(k, 0.0)) for k in self.feature_keys]])
        scaler = self.pipe.named_steps["scaler"]
        lr = self.pipe.named_steps["lr"]
        z = scaler.transform(vec)[0]
        coef = lr.coef_[0]
        return {k: float(c * zi) for k, c, zi in zip(self.feature_keys, coef, z)}

    def predict(self, x: dict[str, float]) -> dict:
        vec = np.array([[float(x.get(k, 0.0)) for k in self.feature_keys]])
        p = float(self.pipe.predict_proba(vec)[0, 1])
        return {"p": p, "backend": "lr_main"}

    # ---- 堆叠（Jev 缺席时自动降级） ----

    def predict_with_jev(self, x: dict[str, float],
                         p_jev: float | None) -> dict:
        base = self.predict(x)
        if p_jev is None or self.stack is None:
            return {**base, "degraded": True,
                    "degraded_reason": ("no_jev_input" if p_jev is None
                                        else "no_stack_model")}
        def logit(q: float) -> float:
            q = float(np.clip(q, 1e-4, 1 - 1e-4))
            return float(np.log(q / (1 - q)))
        v = np.array([[logit(base["p"]), float(np.clip(logit(p_jev), -6, 6))]])
        p = float(self.stack.predict_proba(v)[0, 1])
        return {"p": p, "p_lr": base["p"], "p_jev": float(p_jev),
                "backend": "stack_jev", "degraded": False}

    # ---- 三段判定 ----

    def verdict(self, p: float) -> str:
        tl = float(self.thresholds.get("tau_low", 0.30))
        th = float(self.thresholds.get("tau_high", 0.70))
        if p >= th:
            return VERDICT_SUSPICIOUS
        if p >= tl:
            return VERDICT_UNCERTAIN
        return VERDICT_NO_ANOMALY


VERDICT_TEXT = {
    VERDICT_SUSPICIOUS: "发现可疑：已标出疑点区域与判定依据",
    VERDICT_UNCERTAIN: "证据不足：建议人工复核",
    VERDICT_NO_ANOMALY: "未发现所支持的异常（不代表已证明为真）",
}


def evidence_lines(features: dict[str, float], contribs: dict[str, float],
                   top_k: int = 3) -> list[str]:
    """把逐维贡献翻译成中文依据句，用于证据卡。不经过任何 LLM，离线可复现。"""
    order = sorted(contribs.items(), key=lambda t: -abs(t[1]))
    lines: list[str] = []
    for k, c in order[:top_k]:
        label = FEATURE_LABELS.get(k, k)
        v = features.get(k, 0.0)
        direction = "偏高" if v >= 0.5 else "正常"
        sign = "支持可疑" if c > 0 else "支持正常"
        lines.append(f"{label}：特征值 {v:.2f}（{direction}），贡献 {c:+.2f}（{sign}）")
    return lines

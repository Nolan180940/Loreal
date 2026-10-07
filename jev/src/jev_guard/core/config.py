"""配置。

优先级（后者覆盖前者）::

    内置默认值  <  环境变量  <  ~/.config/jev-guard/config.json  <  命令行参数

凭据来源优先级::

    $JEV_API_KEY  >  opencode auth.json 的 opencode-go provider

设计原则
--------
配置**只在这里**集中解析，下游模块只接收显式参数，不读环境变量。
这样测试时可以注入假配置，不需要 monkeypatch os.environ。
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field, fields
from pathlib import Path
from typing import Any

from .errors import ConfigError

ENV_PREFIX = "JEV_"
DEFAULT_CONFIG_PATH = (
    Path(os.environ.get("USERPROFILE", "~")) / ".config" / "jev-guard" / "config.json"
)

# opencode auth.json 的候选位置
AUTH_CANDIDATES = (
    Path(os.environ.get("USERPROFILE", "~")) / ".local" / "share" / "opencode" / "auth.json",
    Path(os.environ.get("USERPROFILE", "~")) / ".config" / "opencode" / "auth.json",
    Path(os.environ.get("APPDATA", "~")) / "opencode" / "auth.json",
)
# 这些 provider 的凭据可用于 OpenCode Zen 网关
ZEN_PROVIDERS = ("opencode-go", "opencode", "zen")

# Cloudflare 会拦 Python urllib 的默认 UA（`Python-urllib/3.x`），
# 返回 `HTTP 403: error code: 1010`（browser signature banned）。
# 实测：同一个 key、同一端点，仅换 UA 就从 403 变 200 —— 连 /models 都拿不到。
# 所以这个值不能省。
BROWSER_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)


@dataclass(slots=True)
class RiskThresholds:
    """风险分档阈值。

    这些默认值来自 jev-1.13-free 在 42 篇小红书美妆笔记上的实测分布
    （见 docs/PLAN.md 第四节），**不是**统计最优值，是工程起点。
    一旦有了人工标注数据，应用 `jev-guard calibrate` 重新拟合。
    """

    high: float = 0.70      # >= 判高风险
    medium: float = 0.30    # >= 判中风险，低于此判低风险

    def __post_init__(self) -> None:
        if not 0.0 <= self.medium < self.high <= 1.0:
            raise ConfigError(
                f"阈值非法: medium={self.medium} high={self.high}，"
                "需满足 0 <= medium < high <= 1"
            )


@dataclass(slots=True)
class WeightConfig:
    """各维度合成总风险分的权重。

    权��和不必为 1，:meth:`RiskScore.aggregate` 会归一化。
    默认值体现「夸大 > 软广 > 风险用语」的优先级：
    对 Track2「信任守护」而言，**夸大宣称比广告身份更值得警惕** ——
    一篇真诚的广告仍是广告，一篇真诚的测评说「能治痘」则是害人的。
    """

    has_risk: float = 0.35      # 医疗/绝对化/误导性承诺
    exaggeration: float = 0.30  # 夸大程度
    is_ad: float = 0.25         # 商业推广身份
    is_cta: float = 0.10        # 明确购买引导（弱信号，营销号也常有）


@dataclass(slots=True)
class Config:
    """全局配置。"""

    # --- 模型服务 ---
    endpoint: str = "https://opencode.ai/zen/v1/systemone"
    model: str = "jev-1.13-free"
    api_key: str = ""
    timeout: int = 60
    max_retries: int = 3
    retry_backoff: float = 1.5

    # --- 限流控制 ---
    qps: float = 2.5               # 每秒最多请求数
    min_interval: float = 0.4      # 两次请求最小间隔秒
    daily_budget: int = 500        # 单次运行最多请求数，超出即停并保留进度

    # --- 批处理 ---
    checkpoint_every: int = 20     # 每N 条落盘一次
    text_max_chars: int = 2000     # 送进模型前截断长度

    # --- 判定 ---
    thresholds: RiskThresholds = field(default_factory=RiskThresholds)
    weights: WeightConfig = field(default_factory=WeightConfig)

    # --- 路径 ---
    data_root: Path = Path("data")
    out_dir: Path = Path("out")

    # --- 开关 ---
    use_comment_labels: bool = True   # 是否对评论也打标

    def __post_init__(self) -> None:
        self.data_root = Path(self.data_root)
        self.out_dir = Path(self.out_dir)
        if not self.api_key:
            self.api_key = resolve_api_key()

    # ---------------- 序列化 ----------------
    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["data_root"] = str(self.data_root)
        d["out_dir"] = str(self.out_dir)
        d["api_key"] = "***" if self.api_key else ""   # 永不落盘明文
        return d

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "Config":
        known = {f.name for f in fields(cls)}
        kw: dict[str, Any] = {k: v for k, v in raw.items() if k in known}
        for key in ("thresholds", "weights"):
            if key in kw and isinstance(kw[key], dict):
                sub = {"high", "medium"} if key == "thresholds" else set(
                    WeightConfig.__slots__
                )
                kw[key] = {k: v for k, v in kw[key].items() if k in sub}
        return cls(**kw)


def _mask(key: str) -> str:
    """掩码显示，避免在日志/终端泄露凭据。"""
    if not key:
        return "<空>"
    if len(key) <= 10:
        return key[:2] + "*" * (len(key) - 4) + key[-2:]
    return f"{key[:4]}...{key[-4:]}(len={len(key)})"


def resolve_api_key() -> str:
    """按优先级找 API key。

    ``$JEV_API_KEY`` > opencode ``auth.json`` 的 ``opencode-go``。

    找不到时抛 :class:`ConfigError`，消息里给出可操作的两条路，
    而不是让调用方拿到一个空字符串后在几百行之后莫名失败。
    """
    k = os.environ.get(f"{ENV_PREFIX}API_KEY", "").strip()
    if k:
        return k

    for p in AUTH_CANDIDATES:
        if not p.is_file():
            continue
        try:
            auth = json.loads(p.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        for name in ZEN_PROVIDERS:
            v = auth.get(name)
            if isinstance(v, dict) and v.get("key"):
                return str(v["key"])
        # 兜底：任何带 key 的 provider（可能改了名字）
        for v in auth.values():
            if isinstance(v, dict) and v.get("key"):
                return str(v["key"])
    return ""


def load_config(overrides: dict[str, Any] | None = None) -> Config:
    """加载配置：默认 -> 文件 -> 环境变量 -> overrides。"""
    raw: dict[str, Any] = {}

    cfg_path = Path(os.environ.get(f"{ENV_PREFIX}CONFIG", str(DEFAULT_CONFIG_PATH)))
    if cfg_path.is_file():
        try:
            raw.update(json.loads(cfg_path.read_text(encoding="utf-8")))
        except json.JSONDecodeError as e:
            raise ConfigError(f"配置文件解析失败 {cfg_path}: {e}") from e

    # 环境变量：JEV_MODEL=xxx / JEV_QPS=1.5 / JEV_DATA_ROOT=data
    for f in fields(Config):
        env_key = f"{ENV_PREFIX}{f.name.upper()}"
        if env_key not in os.environ:
            continue
        raw_val = os.environ[env_key]
        if f.name in ("thresholds", "weights"):
            try:
                raw[f.name] = json.loads(raw_val)
            except json.JSONDecodeError:
                raw[f.name] = _parse_threshold_env(f.name, raw_val)
        elif f.type in ("int", int) and not isinstance(f.type, str):
            raw[f.name] = int(raw_val)
        elif f.name in ("qps", "min_interval", "retry_backoff", "daily_budget"):
            raw[f.name] = float(raw_val) if "." in raw_val else int(raw_val)
        else:
            raw[f.name] = raw_val

    if overrides:
        raw.update({k: v for k, v in overrides.items() if v is not None})

    cfg = Config.from_dict(raw)
    if not cfg.api_key:
        raise ConfigError(
            "找不到 API key。两条路任选其一：\n"
            "  1. 设环境变量：$env:JEV_API_KEY='<你的 key>'\n"
            "  2. 让 opencode 登录过（auth.json 里要有 opencode-go provider）\n"
            f"key 获取地址：https://opencode.ai/auth"
        )
    return cfg


def _parse_threshold_env(name: str, raw: str) -> dict[str, float]:
    """解析 ``JEV_THRESHOLDS='high=0.8,medium=0.4'`` 这类简写。"""
    out: dict[str, float] = {}
    for part in raw.split(","):
        if "=" not in part:
            continue
        k, v = part.split("=", 1)
        k = k.strip()
        if k in ("high", "medium"):
            out[k] = float(v)
    if not out:
        raise ConfigError(f"{name} 环境变量格式错误: {raw!r}，"
                          "应形如 'high=0.8,medium=0.4'")
    return out
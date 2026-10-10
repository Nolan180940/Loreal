"""配置的数据结构。

设计原则
--------
1. **全部有默认值**：没有 config.toml 也能跑（用内置默认）。
2. **未敲定的量全部集中在这里**：阈值、权重、启用哪些维度/信号 ——
   它们都是**数据**，改它们不该动代码。
3. **``schema_version``**：一起写进 config、一起写进产物。
   以后配置格式变了，旧结果文件仍能解读（知道自己是被哪版配置跑的）。
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field, fields
from pathlib import Path
from typing import Any

#: 配置格式版本。**改字段语义时必须 +1**，否则旧产物会被误读。
SCHEMA_VERSION = 1


@dataclass
class PathConfig:
    """路径。

    ``data_root`` 默认 ``data``，**相对路径会按 CWD → 仓库根的顺序解析**
    （见 ``config.resolve_path``）—— 因为工具既能从仓库根跑，
    也能从 ``jev2/`` 跑，不兜底就会出现「同一个路径在两处指向不同目录」
    这种极难排查的问题。
    """

    data_root: Path = Path("data")
    out_dir: Path = Path("out")


@dataclass
class SignalsConfig:
    """信号层开关。

    ``active`` 为空 = 全部启用（见 ``Registry.select`` 的约定）。
    """

    active: list[str] = field(default_factory=list)
    #: 样本量下限，低于此值的信号必须有 missing_reason。
    #: 放在配置里是因为「多少算够」会随数据规模变。
    min_samples: int = 3


@dataclass
class SemanticConfig:
    """语义层（jev-1.13）开关。

    ``dims`` 决定**问哪些问题**；``state`` 决定**喂什么文本**。
    两者都是数据，加维度/改上下文不用动 runner。
    """

    enabled: bool = True
    model: str = "jev-1.13"
    endpoint: str = "https://opencode.ai/zen/v1/systemone"
    dims: list[str] = field(default_factory=lambda: ["is_ad", "has_risk",
                                                     "exaggeration", "is_cta"])

    # ---- state 拼装规则 ----
    include_title: bool = True
    include_desc: bool = True
    include_tags: bool = True
    #: 送几条一级评论给模型（0 = 不送）。评论能提供「作者有没有自评」等线索。
    top_comments: int = 5
    text_max_chars: int = 2000

    # ---- 调用节流 ----
    qps: float = 2.5
    min_interval: float = 0.4
    timeout: int = 60
    max_retries: int = 3
    retry_backoff: float = 1.0


@dataclass
class FuseConfig:
    """融合层开关 —— **所有未敲定的决策量都在这里**。"""

    #: 用哪套规则（``rules.py`` 里的具名规则集）
    rule_set: str = "default"

    #: 三档阈值。**改二值只改这里**（把 low 设成 high 就退化成二值）。
    high: float = 0.70
    low: float = 0.30

    #: 各维度权重。**加一个键就等于让该维度参与加权**（L2 信号同理）——
    #: 这就是「第一版 L2 只展示不进权重，以后想进就加键」的实现方式。
    weights: dict[str, float] = field(default_factory=lambda: {
        "has_risk": 0.35,
        "exaggeration": 0.30,
        "is_ad": 0.25,
        "is_cta": 0.10,
    })

    #: 一票否决规则：``{维度名: 阈值}``，命中直接判 HIGH。
    #: 依据：legacy-jev 实测 is_ad≥0.85 一票否决把高风险召回从 40% 提到 100%
    #: （加权平均会把官方活动贴 is_ad=0.96 稀释到 0.642 误判中风险）。
    veto: dict[str, float] = field(default_factory=lambda: {"is_ad": 0.85})

    #: L2 统计信号聚合成一个标量的方式：mean | max | median
    l2_aggregate: str = "mean"
    #: 哪些信号参与 L2 聚合（空 = 全部非缺失信号）
    l2_signals: list[str] = field(default_factory=list)


@dataclass
class Config:
    """总配置。"""

    schema_version: int = SCHEMA_VERSION
    paths: PathConfig = field(default_factory=PathConfig)
    signals: SignalsConfig = field(default_factory=SignalsConfig)
    semantic: SemanticConfig = field(default_factory=SemanticConfig)
    fuse: FuseConfig = field(default_factory=FuseConfig)

    #: 运行期注入，**永不落盘**（to_dict 里恒为 "***"）
    api_key: str = ""

    # ---- 序列化 ----

    def to_dict(self) -> dict[str, Any]:
        """序列化。**api_key 永远是掩码**。

        刻意不提供「取出明文 key」的口子 —— 需要 key 的地方直接读
        ``cfg.api_key``（那是内存里的值，不进日志/产物）。
        一个能返回明文的 ``to_dict(mask_key=False)`` 迟早会被误用。
        """
        d = asdict(self)
        d["paths"]["data_root"] = str(self.paths.data_root)
        d["paths"]["out_dir"] = str(self.out_dir)
        d["api_key"] = "***" if self.api_key else ""
        return d

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "Config":
        """从 dict 构造。**忽略未知键**（向前兼容：新配置里有旧代码不认识的项）。

        但嵌套的 dataclass 需要显式过滤字段，否则 ``PathConfig(**多余键)``
        会 TypeError 而不是忽略 —— 那就失去了向前兼容的意义。
        """
        def pick(dc_cls, sub: dict[str, Any] | None):
            if not isinstance(sub, dict):
                return dc_cls()
            known = {f.name for f in fields(dc_cls)}
            return dc_cls(**{k: v for k, v in sub.items() if k in known})

        known_top = {f.name for f in fields(cls)}
        cfg = cls(**{k: v for k, v in raw.items()
                     if k in known_top and k not in
                     ("paths", "signals", "semantic", "fuse")})
        cfg.paths = pick(PathConfig, raw.get("paths"))
        cfg.signals = pick(SignalsConfig, raw.get("signals"))
        cfg.semantic = pick(SemanticConfig, raw.get("semantic"))
        cfg.fuse = pick(FuseConfig, raw.get("fuse"))
        return cfg

    @property
    def out_dir(self) -> Path:
        return self.paths.out_dir


__all__ = [
    "SCHEMA_VERSION", "PathConfig", "SignalsConfig",
    "SemanticConfig", "FuseConfig", "Config",
]

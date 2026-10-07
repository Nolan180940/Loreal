"""jev-guard：基于 jev-1.13 (System One) 的小红书内容核验。

设计要点
--------
1. **判断与采集解耦**：本包不抓数据，只消费 ``xhs-cli`` 的产出。
2. **零训练**：不做分类器，用 jev 的带类型概率 + 显式规则合成风险分。
3. **可解释**：每个维度独立可查，命中证据定位到具体句子。
4. **可恢复**：限流是常态，断点续跑是一等公民。
"""

from __future__ import annotations

__version__ = "0.1.0"

from .core.config import Config, RiskThresholds, WeightConfig, load_config
from .core.errors import (
    AuthError, ConfigError, DataError, JevGuardError, ProviderError, RateLimitError,
)
from .core.models import (
    DimensionScore, Label, QuestionSpec, RiskLevel, RiskScore, SubjectKind,
)
from .core.questions import COMMENT_SPECS, NOTE_SPECS
from .core.scoring import RuleEngine, extract_evidence

__all__ = [
    "__version__",
    "Config", "RiskThresholds", "WeightConfig", "load_config",
    "JevGuardError", "ConfigError", "ProviderError", "RateLimitError",
    "AuthError", "DataError",
    "DimensionScore", "Label", "QuestionSpec", "RiskLevel", "RiskScore",
    "SubjectKind",
    "NOTE_SPECS", "COMMENT_SPECS",
    "RuleEngine", "extract_evidence",
]
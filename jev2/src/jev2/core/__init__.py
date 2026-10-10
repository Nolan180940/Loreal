"""核心层：类型 / 异常 / 注册表。"""

from __future__ import annotations

from .errors import (AuthError, ConfigError, DataError, JevError,
                     ProviderError, RateLimitError)
from .registry import Registry
from .types import (CommentRow, DimScore, Level, NoteRecord, RuleTrace,
                    SemanticResult, SignalResult, Verdict)

__all__ = [
    # errors
    "JevError", "ConfigError", "DataError",
    "ProviderError", "AuthError", "RateLimitError",
    # registry
    "Registry",
    # types
    "Level", "CommentRow", "NoteRecord",
    "SignalResult", "DimScore", "SemanticResult",
    "RuleTrace", "Verdict",
]

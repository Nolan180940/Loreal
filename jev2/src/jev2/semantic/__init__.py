"""语义层：jev-1.13 打分。

- ``provider.py``   HTTP 客户端（从 legacy-jev 移植，坑都实测过）
- ``questions.py``  问题注册表（措辞已 A/B 校准）
- ``runner.py``     state 拼装 + 调用 + 归一化
"""

from __future__ import annotations

from .provider import JevProvider, health_check
from .questions import QUESTIONS, QuestionSpec, specs_for, to_payload
from .runner import SemanticRunner, build_state, normalize_answer

__all__ = [
    "JevProvider", "health_check",
    "QuestionSpec", "QUESTIONS", "specs_for", "to_payload",
    "SemanticRunner", "build_state", "normalize_answer",
]

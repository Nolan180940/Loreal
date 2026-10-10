"""融合层：公式库 + 规则集 + 求值引擎。

三层分离
--------
- ``formulas.py``  纯数学（指标函数 / 逻辑门），可单独测试
- ``rules.py``     决策逻辑，**声明式数据**，可整套替换
- ``engine.py``    求值引擎，跑规则、出裁决、留痕

换决策逻辑 = 换 ``rules.py`` 的规则集（或改 config 的权重/阈值），
引擎一行不改。
"""

from __future__ import annotations

from . import formulas
from .engine import EngineConfig, FuseEngine
from .rules import DEFAULT_RULES, RULE_SETS, Rule, describe_rules, get_rules

__all__ = [
    "formulas",
    "Rule", "DEFAULT_RULES", "RULE_SETS", "get_rules", "describe_rules",
    "EngineConfig", "FuseEngine",
]

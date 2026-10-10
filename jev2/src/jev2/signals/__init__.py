"""信号包：自动发现 + 统一出口。

加一个新信号
------------
1. 在 ``signals/`` 下新建 ``<name>.py``
2. 写一个 ``@signal(NAME, group="...")`` 装饰的函数
3. **完事** —— 下面的 ``_discover()`` 会用 ``pkgutil`` 自动导入
   本包内所有模块，装饰器执行时自动登记

不需要在任何地方 register，也不需要在 ``__init__`` 里 import。
文件名不用和信号名一致（信号名由装饰器参数决定），
但约定俗成保持一致，便于检索。

为什么用 pkgutil 而不是显式 import 列表
--------------------------------------
显式列表的问题：加文件忘记加 import → 信号静默不生效，
排查起来是「我明明写了这个信号，为什么报告里没有」。
自动发现让「写文件」和「生效」之间没有中间步骤。

代价：导入顺序不确定（``pkgutil`` 按名字排序，实际是确定的）。
所以信号之间**不许有依赖** —— 需要共享计算就放 ``_lib.py``。
"""

from __future__ import annotations

import importlib
import pkgutil

from .base import SIGNALS, SignalContext, SignalSet, signal, signal_groups
from ._lib import (
    band_risk, clamp01, entropy, iqr, lens_of, mean, median,
    normalized_entropy, quantile, safe_div, saturate, sd, top1_ratio,
)


def _discover() -> tuple[str, ...]:
    """导入本包下所有模块，触发 ``@signal`` 注册。

    跳过下划线开头的模块（``_lib`` 是工具库，不是信号）。
    """
    loaded: list[str] = []
    for info in pkgutil.iter_modules(__path__):
        if info.name.startswith("_"):
            continue
        importlib.import_module(f"{__name__}.{info.name}")
        loaded.append(info.name)
    return tuple(sorted(loaded))


#: 被自动加载的信号模块名（调试用：能看出哪些文件被跳过了）
LOADED_MODULES = _discover()

#: 全部已注册的信号名
ALL_SIGNALS = SIGNALS.names()

__all__ = [
    "SIGNALS", "SignalContext", "SignalSet", "signal", "signal_groups",
    "ALL_SIGNALS", "LOADED_MODULES",
    # 数学工具（信号文件从 _lib 直接 import，这里再导出方便外部复用）
    "safe_div", "mean", "sd", "quantile", "iqr", "median",
    "entropy", "normalized_entropy", "top1_ratio",
    "clamp01", "saturate", "band_risk", "lens_of",
]

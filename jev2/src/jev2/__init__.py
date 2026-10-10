"""jev2 —— 种草真实性判别系统。

分层::

    loader    notes.json → NoteRecord      （唯一认识数据结构的地方）
    signals/  统计信号（纯 Python，零成本）
    semantic/ jev-1.13 语义判定
    fuse/     公式库 + 规则集 + 求值引擎
    pipeline/ 编排与落盘

设计总纲：**引擎写一次，内容全部数据化。**
不确定的量（阈值/权重/维度/规则）都在 config 里，改它们不动代码。
"""

from __future__ import annotations

__version__ = "0.1.0"

__all__ = ["__version__"]

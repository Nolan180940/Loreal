"""信号基座：注册表 + 协议 + 批量执行。

加一个新信号
------------
1. 在 ``signals/`` 下新建 ``<name>.py``
2. 写一个 ``@SIGNALS.decorator(NAME, group="...")`` 装饰的函数
3. 完事 —— ``signals/__init__.py`` 用 ``pkgutil`` 自动发现，
   不需要在任何地方登记

函数签名统一为::

    def compute(record: NoteRecord, *, ctx: SignalContext) -> SignalResult

``ctx`` 提供跨信号共享的配置（``min_samples`` 等），
避免每个信号自己去读全局配置。

为什么单信号异常要被吞掉
------------------------
40 篇批处理里，一个信号因为某个边界数据挂了，不该让整篇没结果。
所以 ``SignalSet.compute`` 捕获异常并转成 ``missing`` 结果 ——
**报告里能看到它挂了、为什么挂**，而不是静默消失。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Protocol

from ..core.registry import Registry
from ..core.types import NoteRecord, SignalResult

#: 全局信号注册表。名字冲突会立刻报错（见 Registry.register）。
SIGNALS: Registry[SignalFn] = Registry("signal")


@dataclass(frozen=True)
class SignalContext:
    """跑信号时共享的上下文。

    刻意做得小 —— 上下文越大，信号之间的隐式耦合越难查。
    """

    min_samples: int = 3
    #: 额外参数入口（实验期调参用，避免为了试一个阈值改签名）
    options: dict[str, Any] = field(default_factory=dict)

    def get(self, key: str, default: Any = None) -> Any:
        return self.options.get(key, default)


class SignalFn(Protocol):
    """信号函数协议（仅用于类型提示）。"""

    signal_name: str
    signal_group: str

    def __call__(self, record: NoteRecord, *,
                 ctx: SignalContext) -> SignalResult: ...


def signal(name: str, *, group: str = "general") -> Callable:
    """装饰器：登记一个信号。"""
    return SIGNALS.decorator(name, group=group)


class SignalSet:
    """对一篇笔记跑一组信号。"""

    def __init__(self, *, active: list[str] | None = None,
                 ctx: SignalContext | None = None) -> None:
        self._fns = SIGNALS.select(active)
        self._ctx = ctx or SignalContext()

    @property
    def names(self) -> tuple[str, ...]:
        return tuple(self._fns)

    def compute(self, record: NoteRecord) -> dict[str, SignalResult]:
        """跑全部信号，返回 ``{名字: 结果}``。

        单个信号抛异常 → 记成 ``missing``（带异常信息）。
        """
        out: dict[str, SignalResult] = {}
        for name, fn in self._fns.items():
            try:
                out[name] = fn(record, ctx=self._ctx)
            except Exception as exc:      # noqa: BLE001
                # 故意捕获所有异常：批处理不能因为一个边界数据全挂。
                # 但**必须留下痕迹** —— missing_reason 会进报告。
                out[name] = SignalResult.missing_(
                    name, f"信号异常 {type(exc).__name__}: {exc}")
        return out


def signal_groups() -> dict[str, tuple[str, ...]]:
    """按 group 归类，供报告展示。"""
    groups: dict[str, list[str]] = {}
    for name, fn in SIGNALS.items():
        groups.setdefault(getattr(fn, "jeva_group", "general"), []).append(name)
    return {g: tuple(sorted(ns)) for g, ns in sorted(groups.items())}


__all__ = ["SIGNALS", "SignalContext", "SignalFn", "SignalSet",
           "signal", "signal_groups"]

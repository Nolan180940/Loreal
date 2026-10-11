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

#: **实测无效/反向、默认不参与计算**的信号。
#:
#: 为什么用「默认禁用」而不是直接删文件：
#: 1. 换数据源后可能变有用（如 IP 信号需要 50+ 条评论，现在只有 5 条）
#: 2. 报告里仍能看到它们的值，便于复核当初的判断
#: 3. 删除会让「当初为什么不用它」这段历史消失
#:
#: ⚠️ 往这里加名字时，必须在那个信号文件的 docstring 里写明**实测依据**。
INACTIVE_BY_DEFAULT: frozenset[str] = frozenset({
    # AUC=0.259（反向）：官方帖评论者全是唯一昵称（真人领奖），
    # 个人帖反而多 momo 默认昵称 —— 它测的是「默认昵称流行度」。
    # 依据：docs/JEV2_EVALUATION.md 第三节。
    "nickname_dup_rate",
})


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
                 ctx: SignalContext | None = None,
                 include_inactive: bool = False) -> None:
        """
        Parameters
        ----------
        active
            ``None`` / 空 = 除 ``INACTIVE_BY_DEFAULT`` 之外的全部。
            显式列出名字时**按字面执行** —— 即使列了被默认禁用的信号，
            也会跑（便于复现与复核）。
        include_inactive
            强制把默认禁用的也纳入（跑诊断脚本时用）。
        """
        selected = SIGNALS.select(active)
        if active:
            # 显式指定 → 字面执行，不做过滤
            self._fns = selected
        elif include_inactive:
            self._fns = selected
        else:
            self._fns = {k: v for k, v in selected.items()
                         if k not in INACTIVE_BY_DEFAULT}
        self._ctx = ctx or SignalContext()

    @property
    def names(self) -> tuple[str, ...]:
        return tuple(self._fns)

    @property
    def skipped_inactive(self) -> tuple[str, ...]:
        """被默认禁用而没跑的（报告里可展示）。"""
        if self._fns.keys() >= set(SIGNALS.names()):
            return ()
        return tuple(n for n in SIGNALS.names()
                     if n not in self._fns and n in INACTIVE_BY_DEFAULT)

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


__all__ = ["SIGNALS", "INACTIVE_BY_DEFAULT", "SignalContext", "SignalFn",
           "SignalSet", "signal", "signal_groups"]

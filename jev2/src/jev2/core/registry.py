"""通用注册表。

为什么信号和问题共用一套
------------------------
两者都是「名字 → 定义」的映射，都需要：
自动发现、按名字取、列出全部、按配置筛选。

差别只在定义的类型不同（一个是函数，一个是 dataclass）。
所以这里只做**映射管理**，不关心存的是什么。
"""

from __future__ import annotations

from typing import Any, Callable, Generic, Iterator, TypeVar

T = TypeVar("T")


class Registry(Generic[T]):
    """一个具名注册表。

    刻意不做成模块级全局单例 —— 每个用途一个实例
    （``SIGNALS = Registry("signal")``），这样测试里能造干净实例，
    不会互相污染。
    """

    __slots__ = ("_kind", "_items")

    def __init__(self, kind: str) -> None:
        self._kind = kind          # 用于错误信息，如 "signal" / "question"
        self._items: dict[str, T] = {}

    # ------------------------------------------------------------------ 写
    def register(self, name: str, item: T, *, override: bool = False) -> T:
        """登记一项。

        重名默认**报错**而不是静默覆盖 —— 静默覆盖会让「我明明改了
        这个信号却没生效」变成一场调试噩梦（真正生效的是后注册的那个）。
        """
        if name in self._items and not override:
            raise KeyError(
                f"{self._kind} 名字重复: {name!r}。"
                "如果你确实要覆盖，传 override=True。"
            )
        self._items[name] = item
        return item

    def decorator(self, name: str, **meta: Any) -> Callable[[T], T]:
        """当装饰器用：``@SIGNALS.decorator("x")``。"""
        def deco(fn: T) -> T:
            self.register(name, fn)
            # 把元信息挂到函数上（内省/报告用），不污染签名
            for k, v in meta.items():
                try:
                    setattr(fn, f"jeva_{k}", v)
                except (AttributeError, TypeError):   # noqa: PERF203
                    pass
            return fn
        return deco

    # ------------------------------------------------------------------ 读
    def get(self, name: str) -> T:
        if name not in self._items:
            raise KeyError(
                f"未知的 {self._kind}: {name!r}。"
                f"已注册: {', '.join(sorted(self._items)) or '(空)'}"
            )
        return self._items[name]

    def maybe(self, name: str) -> T | None:
        return self._items.get(name)

    def names(self) -> tuple[str, ...]:
        return tuple(self._items)

    def items(self) -> Iterator[tuple[str, T]]:
        return iter(self._items.items())

    def select(self, names: list[str] | tuple[str, ...] | None) -> dict[str, T]:
        """按名字列表筛选；``None`` / 空列表 = 全选。

        配置里 ``active = []`` 的语义就是「不限制」，不是「一个都不要」——
        后者是空结果，没人会想要。这个约定写在这里，避免各处各猜。
        """
        if not names:
            return dict(self._items)
        return {n: self.get(n) for n in names}

    def __len__(self) -> int:
        return len(self._items)

    def __contains__(self, name: object) -> bool:
        return name in self._items

    def __iter__(self) -> Iterator[str]:
        return iter(self._items)


__all__ = ["Registry"]

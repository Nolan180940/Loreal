"""异常层级。

为什么要细分而不是一个 ``JevError``
----------------------------------
调用方对不同类型的失败**处置方式不同**：

- ``DataError``      数据问题 → 跳过这一篇，继续下一篇
- ``AuthError``      凭据问题 → 整个批处理必须停（重试没意义）
- ``RateLimitError`` 限流     → 退避后重试
- ``ConfigError``    配置问题 → 启动时就该失败，别跑到一半才炸

所以 ``pipeline.runner`` 里对不同异常有不同的 except 分支。
"""

from __future__ import annotations


class JevError(RuntimeError):
    """所有 jev2 异常的基类。"""


class ConfigError(JevError):
    """配置缺失/非法。这是**启动期**错误，不该在批处理中途出现。"""


class DataError(JevError):
    """数据缺失或格式错误。可跳过单篇继续跑。"""


class CollectError(JevError):
    """采集失败（链接不支持 / 网络 / 反爬 / 落盘）。

    与 :class:`DataError` 的区别：

    - ``DataError``   数据**已经有**但坏了 → 跳过这一篇继续
    - ``CollectError``数据**还没拿到** → 得先解决链接或采集器

    混同会让「短链过期」在批处理里显示成「这一篇数据有问题」。

    ``code`` 沿用采集器的退出码（2 链接 / 3 抓取 / 4 落盘），
    整条链路语义一致 —— 调用方（脚本、服务）能区分
    「链接不对，重试没用」和「抓取失败，可以重试」。
    """

    def __init__(self, message: str, code: int = 0) -> None:
        super().__init__(message)
        self.code = code


class ProviderError(JevError):
    """模型调用失败（网络/服务端/协议）。"""


class AuthError(ProviderError):
    """凭据无效或无权限。重试无意义，应当停止整批。"""


class RateLimitError(ProviderError):
    """触发限流。``retry_after`` 是服务端建议的等待秒数（可能为 None）。"""

    def __init__(self, message: str, retry_after: float | None = None) -> None:
        super().__init__(message)
        self.retry_after = retry_after


__all__ = [
    "JevError", "ConfigError", "DataError", "CollectError",
    "ProviderError", "AuthError", "RateLimitError",
]

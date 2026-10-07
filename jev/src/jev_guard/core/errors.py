"""异常体系。

分三层，便于调用方精确捕获：

- :class:`JevGuardError` —— 所有本项目异常的基类
- :class:`ConfigError`   —— 配置/凭据问题（改配置能解决）
- :class:`ProviderError` —— 模型服务问题（重试/换模型能解决）
  - :class:`RateLimitError`  —— 触发限流（需要等待或换付费模型）
  - :class:`AuthError`       —— key 无效
- :class:`DataError`     —— 输入数据问题（重跑采集能解决）
"""

from __future__ import annotations


class JevGuardError(Exception):
    """本项目所有异常的基类。"""

    exit_code = 1


class ConfigError(JevGuardError):
    """配置或凭据缺失/非法。"""

    exit_code = 2


class ProviderError(JevGuardError):
    """模型服务调用失败。"""

    exit_code = 3


class RateLimitError(ProviderError):
    """触发限流。

    ``retry_after`` 是服务端建议的等待秒数（若提供）。
    """

    exit_code = 4

    def __init__(self, message: str, retry_after: float | None = None) -> None:
        super().__init__(message)
        self.retry_after = retry_after


class AuthError(ProviderError):
    """凭据无效或无权限。"""

    exit_code = 5


class DataError(JevGuardError):
    """输入数据缺失或格式不符。"""

    exit_code = 6
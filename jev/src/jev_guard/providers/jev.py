"""JevProvider：调用 OpenCode Zen 的 jev-1.13（System One）。

协议要点
--------
``POST /zen/v1/systemone``，body 为 ``{model, state, questions}``，
返回 ``{answers: {qid: answer}, usage: {...}}``。

三种题型返回不同结构：noul 给 0..1；choice/score 给 choice/score +
confidence + legend + probabilities。本项目在
:func:`~jev_guard.core.models.normalize_answer` 里统一成 0..1。

必须伪装 UA
-----------
Cloudflare 会拦 Python urllib 的默认 UA，返回 ``HTTP 403 error code: 1010``
（browser signature banned）。实测同一key、同一端点，仅换 UA 就 403→200，
所以这不是可选项。

重试与限流
----------
- 4xx（除 429）不重试 —— 请求本身有问题，重试没意义。
- 429 抛 :class:`RateLimitError`，由批处理层决定等待还是降级。
- 5xx 和网络错误指数退避重试。
"""

from __future__ import annotations

import json
import random
import time
import urllib.error
import urllib.request
from typing import Any

from ..core.config import BROWSER_UA, Config
from ..core.errors import AuthError, ConfigError, ProviderError, RateLimitError
from ..core.models import QuestionSpec, QuestionSpecMap

# 官方定价（2026-10）：$0.042 / 1M input token，output 免费
PRICE_PER_MTOK_INPUT = 0.042
FREE_MODELS = frozenset({"jev-1.13-free"})


class JevProvider:
    """jev-1.13 的 HTTP 客户端。线程不安全（每线程一个实例）。"""

    def __init__(self, cfg: Config) -> None:
        if not cfg.api_key:
            raise ConfigError(
                "api_key 为空。先设置 $env:JEV_API_KEY 或登录 opencode。"
            )
        self._cfg = cfg
        self.calls = 0
        self.input_tokens = 0
        self.output_tokens = 0
        self._last_call = 0.0

    # ------------------------------------------------------------------ 统计
    @property
    def cost_usd(self) -> float:
        """按官方定价估算累计成本。免费模型恒为 0。"""
        if self._cfg.model in FREE_MODELS:
            return 0.0
        return round(self.input_tokens / 1_000_000 * PRICE_PER_MTOK_INPUT, 6)

    def stats(self) -> dict[str, Any]:
        return {
            "model": self._cfg.model,
            "calls": self.calls,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "cost_usd": self.cost_usd,
        }

    # ------------------------------------------------------------------ 限流
    def _throttle(self) -> None:
        """保证请求间隔不小于 ``min_interval``，且不超过 ``qps`` 上限。"""
        gap = self._cfg.min_interval
        if self._cfg.qps > 0:
            gap = max(gap, 1.0 / self._cfg.qps)
        elapsed = time.monotonic() - self._last_call
        if self._last_call and elapsed < gap:
            time.sleep(gap - elapsed)
        self._last_call = time.monotonic()

    # ------------------------------------------------------------------ 调用
    def ask(self, state: str, questions: QuestionSpecMap) -> dict[str, Any]:
        """问一组问题，返回 jev 原始响应（含 ``answers``）。"""
        state = state[: self._cfg.text_max_chars]
        payload = {
            "model": self._cfg.model,
            "state": state,
            "questions": {qid: q.to_payload()
                          for qid, q in questions.items()},
        }
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")

        last: Exception | None = None
        for attempt in range(self._cfg.max_retries):
            self._throttle()
            req = urllib.request.Request(
                self._cfg.endpoint,
                data=body,
                headers={
                    "Authorization": f"Bearer {self._cfg.api_key}",
                    "Content-Type": "application/json",
                    "User-Agent": BROWSER_UA,      # 缺这个会 403/1010
                    "Accept": "application/json",
                },
                method="POST",
            )
            try:
                with urllib.request.urlopen(req, timeout=self._cfg.timeout) as r:
                    raw = json.loads(r.read().decode("utf-8"))
                self.calls += 1
                self._accumulate_usage(raw)
                return raw
            except urllib.error.HTTPError as e:
                detail = e.read().decode("utf-8", "replace")[:400]
                last = self._classify(e.code, detail)
                if isinstance(last, (AuthError, RateLimitError)):
                    raise last
                if e.code == 403 and "1010" in detail:
                    raise ProviderError(
                        "HTTP 403 code 1010 = Cloudflare 拦 UA。"
                        "请确认 BROWSER_UA 未被覆盖。"
                    ) from e
                if 400 <= e.code < 500:
                    raise ProviderError(f"HTTP {e.code}: {detail}") from e
            except (urllib.error.URLError, TimeoutError, OSError) as e:
                last = ProviderError(f"{type(e).__name__}: {e}")

            if attempt < self._cfg.max_retries - 1:
                back = self._cfg.retry_backoff * (2 ** attempt)
                time.sleep(back + random.uniform(0, 0.3))   # 抖动，避免同步重试

        raise last or ProviderError("调用失败，未知原因")

    @staticmethod
    def _classify(code: int, detail: str) -> Exception:
        if code == 429:
            ra = None
            try:
                j = json.loads(detail)
                ra = j.get("retry_after") or j.get("error", {}).get("retry_after")
            except (json.JSONDecodeError, AttributeError):
                pass
            return RateLimitError(f"触发限流: {detail[:200]}", retry_after=ra)
        if code in (401, 403):
            return AuthError(f"凭据无效或无权限 (HTTP {code}): {detail[:200]}")
        return ProviderError(f"HTTP {code}: {detail}")

    def _accumulate_usage(self, raw: dict[str, Any]) -> None:
        usage = raw.get("usage") or {}
        self.input_tokens += int(usage.get("input_tokens") or 0)
        self.output_tokens += int(usage.get("output_tokens") or 0)


def health_check(cfg: Config) -> dict[str, Any]:
    """连通性自检。不抛异常，返回可读的状态字典。

    用于 ``jev-guard doctor``，也用于 CI 里快速判断环境是否就绪。
    """
    out: dict[str, Any] = {
        "endpoint": cfg.endpoint,
        "model": cfg.model,
        "api_key": (cfg.api_key[:4] + "..." + cfg.api_key[-4:])
        if len(cfg.api_key) > 10 else "***",
    }
    try:
        p = JevProvider(cfg)
        r = p.ask("This cream caused a rash after I used it.",
                  _probe_spec())
        out["status"] = "ok"
        out["sample"] = r.get("answers") or r
        out["usage"] = r.get("usage")
        out["stats"] = p.stats()
    except Exception as e:  # noqa: BLE001
        out["status"] = "fail"
        out["error"] = f"{type(e).__name__}: {e}"
    return out


def _probe_spec() -> dict[str, QuestionSpec]:
    """最小探测问题集 —— 只验证连通性，不消耗额度做批量任务。"""
    return {"is_risk": QuestionSpec(
        name="is_risk",
        qtype="noul",
        instructions="Does this text make risky health claims?",
        label="风险宣称",
    )}
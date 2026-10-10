"""jev-1.13（OpenCode Zen ``systemone``）的 HTTP 客户端。

**从 legacy-jev 原样移植** —— 下面每条都是实测踩出来的坑，
不是可选优化，改动前先读：

====================================  =====================================
坑                                     后果
====================================  =====================================
必须用浏览器 UA                        Cloudflare 拦 Python 默认 UA，
                                      返回 ``HTTP 403 error code: 1010``
                                      （browser signature banned）。
                                      同一个 key、同一端点，**只换 UA
                                      就从 403 变 200**，连 ``/models``
                                      都拿不到。
按 ``qps`` / ``min_interval`` 节流    超了返回 429。
指数退避 + 抖动                        同步重试会撞在一起。
一次调用问多题（questions map）        省 tokens。定价 $0.042/1M input。
凭据永不落明文                          日志/产物里只有掩码形式。
====================================  =====================================

协议
----
``POST {endpoint}`` body::

    {"model": "jev-1.13", "state": "<文本>", "questions": {...}}

响应里的 ``answers`` 是 ``{qid: {...}}``，字段随题型不同（见 questions.py）。
"""

from __future__ import annotations

import json
import random
import time
import urllib.error
import urllib.request
from typing import Any

from ..config.schema import SemanticConfig
from ..core.errors import (AuthError, ConfigError, ProviderError,
                           RateLimitError)

#: Cloudflare 必需。缺这个直接 403/1010（实测）。
BROWSER_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)

#: 输入 token 单价（美元 / 百万）。
#: 来自 OpenCode Zen 公开定价。输出 token 未单独计价。
PRICE_PER_MTOK_INPUT = 0.042

#: 免费模型的 id —— 成本恒为 0（但有 429 限额）。
FREE_MODELS = frozenset({"jev-1.13-free"})


class JevProvider:
    """jev-1.13 客户端。

    **线程不安全**（``_last_call`` 是实例状态）。要并发就每个线程
    一个实例；不过本项目是串行批处理，单实例足够。
    """

    def __init__(self, cfg: SemanticConfig, *, api_key: str) -> None:
        if not api_key:
            raise ConfigError(
                "api_key 为空。两条路：\n"
                "  1. 设置 $env:JEV2_API_KEY\n"
                "  2. 登录 opencode（凭据在 ~/.local/share/opencode/auth.json）"
            )
        self._cfg = cfg
        self._key = api_key
        self.calls = 0
        self.input_tokens = 0
        self.output_tokens = 0
        self._last_call = 0.0

    # ------------------------------------------------------------------ 统计

    @property
    def cost_usd(self) -> float:
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
        """保证两次请求间隔不小于 ``min_interval``，且不超过 ``qps`` 上限。"""
        gap = self._cfg.min_interval
        if self._cfg.qps > 0:
            gap = max(gap, 1.0 / self._cfg.qps)
        elapsed = time.monotonic() - self._last_call
        if self._last_call and elapsed < gap:
            time.sleep(gap - elapsed)
        self._last_call = time.monotonic()

    # ------------------------------------------------------------------ 调用

    def ask(self, state: str, questions: dict[str, dict[str, Any]]) -> dict[str, Any]:
        """问一组问题，返回 jev 原始响应（含 ``answers``）。

        ``questions`` 已是 API 格式（由 :func:`questions.to_payload` 产出）。
        """
        state = state[: self._cfg.text_max_chars]
        body = json.dumps(
            {"model": self._cfg.model, "state": state, "questions": questions},
            ensure_ascii=False,
        ).encode("utf-8")

        last: Exception | None = None
        for attempt in range(max(1, self._cfg.max_retries)):
            self._throttle()
            req = urllib.request.Request(
                self._cfg.endpoint,
                data=body,
                headers={
                    "Authorization": f"Bearer {self._key}",
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
                # 凭据/限流错误重试无意义，直接抛
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
                time.sleep(back + random.uniform(0, 0.3))   # 抖动避免同步重试

        raise last or ProviderError("调用失败，未知原因")

    @staticmethod
    def _classify(code: int, detail: str) -> Exception:
        if code == 429:
            ra = None
            try:
                j = json.loads(detail)
                ra = (j.get("retry_after")
                      or j.get("error", {}).get("retry_after"))
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


def health_check(cfg: SemanticConfig, *, api_key: str) -> dict[str, Any]:
    """连通性自检。**不抛异常** —— 返回可读状态，供 CLI ``doctor`` 用。"""
    out: dict[str, Any] = {
        "endpoint": cfg.endpoint,
        "model": cfg.model,
        "api_key": "已配置" if api_key else "缺失",
        "ok": False,
        "detail": "",
    }
    if not api_key:
        out["detail"] = "没有 API key，无法探测"
        return out
    try:
        p = JevProvider(cfg, api_key=api_key)
        raw = p.ask("test", {"ping": {"type": "noul",
                                      "instructions": "Is this a test?"}})
        out["ok"] = "answers" in raw or bool(raw)
        out["detail"] = f"响应键: {sorted(raw)[:6]}"
        out["stats"] = p.stats()
    except Exception as exc:  # noqa: BLE001
        out["detail"] = f"{type(exc).__name__}: {exc}"
    return out


__all__ = ["JevProvider", "health_check", "BROWSER_UA",
           "PRICE_PER_MTOK_INPUT", "FREE_MODELS"]

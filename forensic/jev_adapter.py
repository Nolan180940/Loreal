# -*- coding: utf-8 -*-
"""Jev（TypeSafe System One）接入适配器 —— 语义侧可选信号。

定位（务必不要误解）：
- Jev 是**纯文本**决策模型（官方规格明确不支持图像），永远进不了取证层。
  它在本项目里只作为「语义侧原子信号」的来源，即第 7 维特征 x7。
- 它给的是 0~1 的 noul 概率，不是布尔；布尔只在 gating 层出现。
- 它是**可选**的：任何失败（无 key、无网络、限流、超时）都必须返回 None，
  由 fusion 自动降级为 6 维主模型，链路不中断。

接口依据：OpenCode Zen 网关（https://opencode.ai/docs/zh-cn/zen/）
    POST https://opencode.ai/zen/v1/systemone
    Authorization: Bearer $OPENCODE_API_KEY
    {"model": "jev-1.13-free", "state": "...", "questions": {...}}

只用标准库 urllib，避免为可选功能引入新依赖。
"""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request

ENDPOINT = "https://opencode.ai/zen/v1/systemone"
DEFAULT_MODEL = os.environ.get("JEV_MODEL", "jev-1.13-free")
TIMEOUT_S = float(os.environ.get("JEV_TIMEOUT_S", "20"))


def api_key() -> str | None:
    return os.environ.get("OPENCODE_API_KEY") or os.environ.get("TYPESAFE_API_KEY")


def ask(state: str, questions: dict, model: str | None = None,
        timeout: float = TIMEOUT_S) -> dict | None:
    """一次请求问多个原子问题；任何异常都返回 None（上层据此降级）。"""
    key = api_key()
    if not key:
        return None
    payload = {"model": model or DEFAULT_MODEL, "state": state,
               "questions": questions}
    req = urllib.request.Request(
        ENDPOINT,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Authorization": f"Bearer {key}",
                 "Content-Type": "application/json"},
        method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = json.loads(resp.read().decode("utf-8"))
        return body
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError,
            json.JSONDecodeError, OSError):
        return None
    except Exception:  # noqa: BLE001  作为可选依赖，绝不因它中断主链路
        return None


def noul(state: str, instructions: str, model: str | None = None) -> float | None:
    """单个是/否问题，返回概率或 None。"""
    r = ask(state, {"q": {"type": "noul", "instructions": instructions}}, model=model)
    if not r:
        return None
    try:
        a = r["answers"]["q"]
        val = a.get("noul")
        return float(val) if val is not None else None
    except (KeyError, TypeError, ValueError):
        return None


# ---------- 三个原子信号（遵守「问题尽量原子，组合逻辑写在自己代码里」） ----------

SEMANTIC_QUESTIONS = {
    "price_conflict": {
        "type": "noul",
        "instructions": ("图中的价格/色号/规格数字与帖子正文所述是否互相矛盾"
                         "（数值不同、色号不同、容量不同）"),
    },
    "template_boilerplate": {
        "type": "noul",
        "instructions": ("这段文案是否使用了高度模板化的营销种草话术"
                         "（固定钩子、夸张承诺、统一句式），而非个人真实分享语气"),
    },
    "strong_efficacy_claim": {
        "type": "noul",
        "instructions": ("这段文案是否包含需要证据支撑的绝对化功效承诺"
                         "（如数天见效、彻底根治、百分百有效）"),
    },
}


def semantic_signals(post_text: str, ocr_numbers: str | None = None,
                     model: str | None = None) -> dict | None:
    """返回三个语义原子概率；不可用时返回 None。

    ocr_numbers 为空时 price_conflict 问题自动跳过（不在无证据时硬问）。
    """
    if not post_text or not post_text.strip():
        return None
    state = post_text.strip()
    if ocr_numbers:
        state = f"【图内识别到的数字/文字】{ocr_numbers}\n【帖子文本】{state}"
    qs = dict(SEMANTIC_QUESTIONS)
    if not ocr_numbers:
        qs.pop("price_conflict", None)
    r = ask(state, qs, model=model)
    if not r:
        return None
    out: dict[str, float] = {}
    answers = r.get("answers", {})
    for k in qs:
        try:
            v = answers[k].get("noul")
        except (KeyError, TypeError):
            continue
        if v is not None:
            out[k] = float(v)
    return out or None


def combine_signal(sig: dict) -> float | None:
    """把多个原子概率合成一个 x7 概率。

    先取最大（任一条原子信号强烈成立即值得上报），再做一个「软化」避免直接
    饱和到 0/1。注意这里**不使用**加权平均：语义信号之间不是独立证据的加和，
    而是「是否存在某一类语义异常」的并集语义。
    """
    vals = [v for v in sig.values() if v is not None]
    if not vals:
        return None
    m = float(max(vals))
    return float(min(0.999, max(0.001, m)))


# ---------- 冒烟测试（P3 前置门） ----------

def smoke_test(n: int = 10) -> bool:
    """实测通道可用性：延迟、限流、中文方向性。

    通过标准（方案 8.1）：零 429、p95 < 2s、方向性全对。
    注意：需要环境变量 OPENCODE_API_KEY；没有 key 时直接报告不可用，
    不要把它当作「模型不行」。
    """
    if not api_key():
        print("[jev-smoke] 未检测到 OPENCODE_API_KEY，通道不可用。")
        print("            → P3 记为『未接通』，主线 LR 不受影响。")
        return False

    print(f"[jev-smoke] model={DEFAULT_MODEL} endpoint={ENDPOINT}")
    lat: list[float] = []
    fails = 0
    for i in range(n):
        t0 = time.time()
        r = noul("这是一条普通的商品使用感受分享。", "这条内容是否属于广告推广")
        dt = time.time() - t0
        if r is None:
            fails += 1
        else:
            lat.append(dt)
    if lat:
        lat.sort()
        p50 = lat[len(lat) // 2]
        p95 = lat[min(len(lat) - 1, int(len(lat) * 0.95))]
        print(f"[jev-smoke] 成功 {len(lat)}/{n}  失败 {fails}  "
              f"延迟 p50={p50:.2f}s p95={p95:.2f}s")
    else:
        print(f"[jev-smoke] 全部失败（{fails}/{n}）")

    # 中文方向性抽检
    cases = [("我今天用了这支唇釉，颜色比想象中淡很多，有点干。", "这段内容是否为虚假或夸大的广告文案"),
             ("三天祛斑百分百见效，无效退款，链接拍下立减，全网最低价冲！", "这段内容是否为虚假或夸大的广告文案")]
    ok = 0
    for text, q in cases:
        v = noul(text, q)
        print(f"[jev-smoke] {'假' if '百分百' in text else '真'} 样本 noul={v}")
        if v is not None:
            ok += 1 if (v > 0.5) == ("百分百" in text) else 0
    passed = bool(lat and p95 < 2.0 and fails == 0 and ok == len(cases))
    print(f"[jev-smoke] 结论：{'通过' if passed else '未通过（P3 降级为可选，不阻塞主线）'}")
    return passed


if __name__ == "__main__":
    raise SystemExit(0 if smoke_test() else 1)

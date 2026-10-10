"""融合层的**求值引擎** —— 写一次就不动。

职责
----
1. 把 context 喂给规则集
2. 先跑 veto：命中就出结果，不再往下
3. 再跑 contribute：加权累加
4. 把 total 映射成档位
5. 全过程留痕（每条规则算出了什么、有没有跳过、贡献多少）

**引擎不含任何决策逻辑** —— 它只执行 ``rules.py`` 声明的规则。
换决策 = 换规则集，引擎不动。

留痕为什么重要
--------------
没有 trace 的话，「这篇为什么判高风险」只能靠猜。
有了 trace，报告能直接说「ad_gate 命中（is_ad=0.91 ≥ 0.85），
其余规则未参与」。这在调阈值时是刚需 ——
否则改一个数字要看半天才知道影响面。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ..core.types import (DimScore, Level, RuleTrace, SignalResult,
                          Verdict)
from . import formulas as F
from .rules import Rule, get_rules


@dataclass
class EngineConfig:
    """引擎的运行参数。

    与 ``config.schema.FuseConfig`` 对应，但引擎不直接依赖 config ——
    这样它能被单独测试（给个 dataclass 就行）。
    """

    high: float = 0.70
    low: float = 0.30
    rule_set: str = "default"
    #: 覆盖规则里的权重：``{规则名或输入名: 权重}``
    weights: dict[str, float] = field(default_factory=dict)
    #: 覆盖 veto 阈值：``{输入名: 阈值}``
    veto: dict[str, float] = field(default_factory=dict)
    #: 规则集里 contribution 的输入若出现在 weights 里，就自动从
    #: flag 提升为 contribute。这让「加一个键就启用 L2」成为可能。
    auto_promote: bool = True


class FuseEngine:
    """规则求值引擎。"""

    def __init__(self, cfg: EngineConfig | None = None) -> None:
        self.cfg = cfg or EngineConfig()
        self._rules = get_rules(self.cfg.rule_set)

    # ------------------------------------------------------------------ 公开

    def evaluate(self, note_id: str, context: dict[str, float], *,
                 dims: tuple[DimScore, ...] = (),
                 signals: tuple[SignalResult, ...] = ()) -> Verdict:
        """求值。

        Parameters
        ----------
        context
            ``{键: 0..1 的值}``。语义维度由 :meth:`SemanticResult.as_context`
            提供；统计信号聚合后会加一个 ``l2_mean`` 键进来。
            缺失的键 = 该维度没数据，相关规则会被跳过（不是当 0 用）。
        """
        trace: list[RuleTrace] = []
        vetoed_by = ""

        # ---- 1. veto：命中即出结果 ----
        for rule in self._rules:
            if rule.action != "veto":
                continue
            v, missing = self._value_of(rule, context)
            if missing:
                trace.append(RuleTrace(
                    rule=rule.name, action="veto", skipped=True,
                    reason=f"输入 {'/'.join(rule.inputs)} 缺失"))
                continue
            threshold = self._veto_threshold(rule)
            hit = v >= threshold
            trace.append(RuleTrace(
                rule=rule.name, action="veto", value=v,
                reason=f"{'/'.join(rule.inputs)}={v:.3f} "
                       f"{'≥' if hit else '<'} {threshold}"))
            if hit:
                vetoed_by = rule.name
                break

        # ---- 2. contribute：加权累加 ----
        pairs: dict[str, float] = {}
        weights: dict[str, float] = {}
        for rule in self._rules:
            action = self._resolve_action(rule)
            if action != "contribute":
                continue
            v, missing = self._value_of(rule, context)
            key = rule.inputs[0] if rule.inputs else rule.name
            w = self.cfg.weights.get(key, self.cfg.weights.get(rule.name,
                                                               rule.weight))
            if missing:
                trace.append(RuleTrace(
                    rule=rule.name, action="contribute", weight=w,
                    skipped=True, reason=f"输入 {key} 缺失"))
                continue
            pairs[key] = v
            weights[key] = w
            trace.append(RuleTrace(
                rule=rule.name, action="contribute", value=v,
                weight=w, contribution=v * w))

        # ---- 3. flag：只记录 ----
        for rule in self._rules:
            if self._resolve_action(rule) != "flag":
                continue
            v, missing = self._value_of(rule, context)
            key = rule.inputs[0] if rule.inputs else rule.name
            trace.append(RuleTrace(
                rule=rule.name, action="flag",
                value=None if missing else v,
                skipped=missing,
                reason=(f"{key} 缺失" if missing
                        else f"{key}={v:.3f}（仅记录，不计分）")))

        total = F.weighted(pairs, weights)
        if vetoed_by:
            total = 1.0

        level = self.level_of(total)

        notes: list[str] = []
        if vetoed_by:
            r = next(r for r in self._rules if r.name == vetoed_by)
            notes.append(f"一票否决命中：{vetoed_by}（{r.note}）"
                         if r.note else f"一票否决命中：{vetoed_by}")
        missing_inputs = [t.rule for t in trace if t.skipped]
        if missing_inputs:
            notes.append(f"跳过的规则（输入缺失）：{', '.join(missing_inputs)}")

        return Verdict(
            note_id=note_id,
            total=round(total, 4),
            level=level,
            dimensions=dims,
            signals=signals,
            trace=tuple(trace),
            vetoed_by=vetoed_by,
            notes=tuple(notes),
        )

    def level_of(self, total: float) -> Level:
        """分数 → 档位。

        二值化只需把 config 的 ``low`` 设成与 ``high`` 相同
        （那样永远不会落到 MEDIUM）。
        """
        if total >= self.cfg.high:
            return Level.HIGH
        if total <= self.cfg.low:
            return Level.LOW
        return Level.MEDIUM

    # ------------------------------------------------------------------ 内部

    def _resolve_action(self, rule: Rule) -> str:
        """决定规则的**实际**动作。

        这是「加一个权重键就启用 L2」的实现点：
        ``l2_stats`` 声明为 flag，但一旦 ``config.fuse.weights`` 里
        出现 ``l2_mean``，它就被提升为 contribute。
        """
        if not self.cfg.auto_promote:
            return rule.action
        if rule.action != "flag":
            return rule.action
        key = rule.inputs[0] if rule.inputs else rule.name
        if key in self.cfg.weights or rule.name in self.cfg.weights:
            return "contribute"
        return "flag"

    def _value_of(self, rule: Rule, context: dict[str, float]) -> tuple[float, bool]:
        """取规则输入并套公式。

        Returns
        -------
        (值, 是否缺失)

        多输入（如 ``inputs=("is_ad","exaggeration")`` + ``formula=AND``）
        会把所有输入按顺序传给公式 —— 这样逻辑门组合不用改引擎。
        """
        vals: list[float] = []
        for key in rule.inputs:
            if key not in context:
                return 0.0, True
            vals.append(float(context[key]))
        if not vals:
            return 0.0, True

        fn = rule.formula or F.identity
        try:
            if len(vals) == 1:
                return float(fn(vals[0], **rule.args)), False
            return float(fn(*vals, **rule.args)), False
        except (TypeError, ValueError):
            # 公式参数不匹配写成 missing 而不是崩 —— 规则是数据，
            # 写错了不该让整批挂掉，但必须在 trace 里能看出来。
            return 0.0, True

    def _veto_threshold(self, rule: Rule) -> float:
        """veto 阈值：config 覆盖 > 规则自带的 args.t。"""
        key = rule.inputs[0] if rule.inputs else rule.name
        return float(self.cfg.veto.get(key,
                                       rule.args.get("t", 0.85)))

    # ------------------------------------------------------------------ 内省

    def rules(self) -> tuple[Rule, ...]:
        return self._rules

    def describe(self) -> list[dict[str, Any]]:
        """当前生效的规则（含被自动提升的动作）。

        ``weight`` 对 veto / flag **恒为 0** —— 它们不计分。
        曾经在这里做 ``weights.get(输入名)`` 查表，结果 veto 规则
        显示成 ``w=0.25``（那是 is_ad 的**贡献**权重），看的人会
        以为否决也有权重。现在按动作给值。
        """
        out: list[dict[str, Any]] = []
        for r in self._rules:
            effective = self._resolve_action(r)
            key = r.inputs[0] if r.inputs else r.name
            if effective == "contribute":
                w = self.cfg.weights.get(key, self.cfg.weights.get(r.name,
                                                                  r.weight))
            else:
                w = 0.0
            out.append({
                "name": r.name,
                "declared": r.action,
                "effective": effective,
                "inputs": list(r.inputs),
                "formula": (getattr(r.formula, "__name__", "identity")
                            if r.formula else "identity"),
                "args": r.args,
                "weight": w,
                "threshold": (self._veto_threshold(r)
                              if effective == "veto" else None),
                "note": r.note,
            })
        return out


__all__ = ["EngineConfig", "FuseEngine"]

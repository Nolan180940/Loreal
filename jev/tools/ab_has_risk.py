"""A/B 测试 has_risk 提问措辞。

背景
----
首轮准确度检查发现：`has_risk` 对**真实测评**系统性高估。

误判案例：
  「目前没发现任何更好的面霜」  has_risk=0.77  人工=low
     → 内容："皮肤状态不好时抹完第二天就好很多了"
  「修丽可AGE面霜，你真的是黑绷带平替吗？」has_risk=0.68  人工=low
     → 内容："换了之后脸总是干痒""脸颊有轻微刺痛感"

根因假设
--------
「描述产品导致的不良反应」被误判成「医疗/疗效宣称」。
这两件事在语义上相反：
  宣称= 我保证能治好你  → 违规
  描述= 我用完过敏了  → 消费者权益披露，应当鼓励

做法
----
对同一批笔记跑两套措辞，比较误判案例是否修复、真阳性是否保住。
真阳性（2 篇绝对化宣称）不能因为改措辞而漏掉 —— 那是核心能力。
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
# 控制台默认 GBK 编不了对勾 emoji，print 会UnicodeEncodeError。
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

from jev_guard.core.config import load_config
from jev_guard.core.models import QuestionSpec
from jev_guard.extractors.reader import load_note
from jev_guard.providers.jev import JevProvider

DATA = Path(r"d:\LOreal-ai\data")
OUT = Path(r"d:\LOreal-ai\jev\out")

# 旧措辞（当前线上）
OLD = QuestionSpec(
    name="has_risk", qtype="noul", label="风险用语",
    instructions=(
        "Does the text contain any of the following that could mislead a "
        "consumer: medical or therapeutic claims, absolute terms such as "
        "100% / best / only / guaranteed, or promises of guaranteed "
        "results? Ignore ordinary descriptive language."
    ),
)

# 新措辞：显式区分「宣称」与「自述副作用」
NEW = QuestionSpec(
    name="has_risk", qtype="noul", label="风险用语",
    instructions=(
        "Does the AUTHOR make a risky PROMISE about the product? Judge only "
        "what the author claims the product will DO.\n"
        "Answer TRUE for: promises to cure, treat, heal, or repair damaged "
        "skin; absolute terms (100%, best, only, guaranteed, permanent); "
        "guaranteed results; claims that override individual differences.\n"
        "Answer FALSE for: the author describing their OWN negative experience "
        "(irritation, redness, breakouts, dryness they experienced); "
        "quoting someone else's claim in order to criticize it; listing "
        "ingredients and their concentration; reporting clinical numbers "
        "with proper context; ordinary subjective opinion."
    ),
)

# 真阳性：必须维持高分
TRUE_POSITIVE = {
    "6a957d1f000000002003a171": "标题『杀伤力为100000%』绝对化",
    "6a7ebdfe00000000080122b8": "『效果直接翻倍』『比水煮蛋还亮』夸大",
}
# 真阴性：误判案例，期望修复
TRUE_NEGATIVE = {
    "6aa67551000000001401ce8c": "真实测评，主动说缺点",
    "69f7fd1f0000000035027b12": "真实差评（味道/质地/不会回购）",
    "6a9fdee6000000002802974c": "成分党硬核拆解",
    "6ab8e804000000000200d3cd": "研发视角客观分析",
    "69f962b3000000002301eb64": "『不吹不黑』有明确缺点",
    "6a0453a100000000060321c4": "劝退贴『智商税』",
    "69ef4c520000000036003631": "过敏避雷贴",
    "6a29550f0000000022026616": "脂溢性皮炎repo，有吐槽",
    "6a703362000000002701ec7e": "有真实对比+承认缺点",
}


def run(p: JevProvider, note_id: str, spec: QuestionSpec) -> float | None:
    subj = load_note(DATA, note_id)
    if subj is None:
        return None
    try:
        r = p.ask(subj.text_for_model, {"has_risk": spec})
        v = (r.get("answers", {}).get("has_risk") or {}).get("noul")
        return None if v is None else float(v)
    except Exception as e:  # noqa: BLE001
        print(f"  [ERR] {note_id[:8]} {type(e).__name__}: {str(e)[:80]}")
        return None


def main() -> int:
    cfg = load_config({"model": "jev-1.13"})
    p = JevProvider(cfg)
    L: list[str] = []
    L.append("=" * 76)
    L.append("has_risk 提问措辞 A/B 测试")
    L.append("=" * 76)
    L.append("")
    L.append("判定标准：")
    L.append("  真阳性 TRUE_POSITIVE 应 >=0.6（绝对化宣称必须抓到）")
    L.append("  真阴性 TRUE_NEGATIVE 应 <0.6（真实测评不该被误判）")
    L.append("")

    tp_ids = list(TRUE_POSITIVE)
    tn_ids = list(TRUE_NEGATIVE)

    L.append("--- 真阳性（改了不能漏） ---")
    L.append(f"{'note_id':<10}{'OLD':>8}{'NEW':>8}{'Δ':>8}  说明")
    tp_old, tp_new = [], []
    for nid in tp_ids:
        o = run(p, nid, OLD)
        n = run(p, nid, NEW)
        time.sleep(0.3)
        if o is not None:
            tp_old.append(o)
        if n is not None:
            tp_new.append(n)
        d = (n - o) if (o is not None and n is not None) else None
        L.append(f"{nid[:8]:<10}{(f'{o:.2f}' if o is not None else '-'):>8}"
                 f"{(f'{n:.2f}' if n is not None else '-'):>8}"
                 f"{(f'{d:+.2f}' if d is not None else '-'):>8}  "
                 f"{TRUE_POSITIVE[nid]}")
    L.append("")
    L.append("--- 真阴性（改了应修复） ---")
    L.append(f"{'note_id':<10}{'OLD':>8}{'NEW':>8}{'Δ':>8}  说明")
    tn_old, tn_new = [], []
    for nid in tn_ids:
        o = run(p, nid, OLD)
        n = run(p, nid, NEW)
        time.sleep(0.3)
        if o is not None:
            tn_old.append(o)
        if n is not None:
            tn_new.append(n)
        d = (n - o) if (o is not None and n is not None) else None
        L.append(f"{nid[:8]:<10}{(f'{o:.2f}' if o is not None else '-'):>8}"
                 f"{(f'{n:.2f}' if n is not None else '-'):>8}"
                 f"{(f'{d:+.2f}' if d is not None else '-'):>8}  "
                 f"{TRUE_NEGATIVE[nid]}")
    L.append("")

    def stat(vals: list[float]) -> str:
        return f"n={len(vals)}均值={sum(vals)/len(vals):.2f}" if vals else "n=0"

    L.append("=" * 76)
    L.append("汇总")
    L.append("=" * 76)
    if tp_old and tp_new:
        o = sum(tp_old) / len(tp_old)
        n = sum(tp_new) / len(tp_new)
        L.append(f"真阳性均值  OLD {o:.3f} → NEW {n:.3f}  ({n - o:+.3f})")
        if o >= 0.6 and n < 0.6:
            L.append("  ⚠️ **新措辞漏掉了绝对化宣称，不可接受**")
        elif n >= 0.6:
            L.append("  ✅ 真阳性保住")
    if tn_old and tn_new:
        o = sum(tn_old) / len(tn_old)
        n = sum(tn_new) / len(tn_new)
        L.append(f"真阴性均值  OLD {o:.3f} → NEW {n:.3f}  ({n - o:+.3f})")
        fixed = sum(1 for a, b in zip(tn_old, tn_new) if a >= 0.6 > b)
        broke = sum(1 for a, b in zip(tn_old, tn_new) if a < 0.6 <= b)
        L.append(f"  修复 {fixed} 条，新引入误判 {broke} 条")

    L.append(f"\n成本: {p.stats()}")
    (OUT / "ab_has_risk.txt").write_text("\n".join(L), encoding="utf-8")
    print("\n".join(L))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
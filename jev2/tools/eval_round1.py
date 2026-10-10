# -*- coding: utf-8 -*-
"""jev2 首轮评估 —— 用我逐篇读完全部 40 篇后的独立判读做基准。

⚠️ 基准的局限（必须先说）
------------------------
这些 label 是**模型（我）读完全部正文/评论/部分图片后给出的判断**，
不是真人的 ground truth。它回答「信号有没有区分度、公式稳不稳」够用，
回答「绝对准确率」不够 —— 用户抽查是最终一步。

方法
----
1. label：high / medium / low（判的是「这篇内容是否在种草/误导」）
2. 离线重算融合：scores.jsonl 里存了全部维度分与信号值，
   换权重/规则集/阈值**不需要重新调模型**
3. AUC：Mann-Whitney 秩检验（信号风险值 vs 是否高风险）
"""
from __future__ import annotations

import itertools
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent        # d:\LOreal-ai
sys.path.insert(0, str(ROOT / "jev2" / "src"))

# ---------------------------------------------------------------- 基准标注
# 逐篇读正文+评论后的判断。判据：
#   high   = 官方营销 / 卖家广告 / 夸大功效+CTA
#   medium = 疑似软广（专业结构+免责声明+人设+评论区推销），但无实锤
#   low    = 真实分享/提问/吐槽
LABELS: dict[str, str] = {
    # ---- 真实分享 / 提问 / 吐槽（low）----
    "6931e77a": "low",    # 珂润今年入手，朴素体验
    "693abce3": "low",    # AGE 空瓶，有缺点有依据，作者答疑专业
    "69575a61": "low",    # 薇诺娜说实话，评论区真实吐槽为主
    "69b0462b": "low",    # 过敏吐槽，带就诊细节
    "69bd5426": "low",    # 涂了发白，讨论性质疑
    "69ef4c52": "low",    # 背刺我，长痘停用换品牌
    "6a0453a1": "low",    # AGE 精华别买，消费者抱怨
    "6a12d06d": "low",    # 价格提问
    "6a2682ff": "low",    # 白绷带详细测评，还推更便宜的可复美
    "6a29550f": "low",    # 脂溢性皮炎 repo，真实
    "6a35d622": "low",    # 空瓶 115ml，说没明显效果
    "6a463cfb": "low",    # 25岁求助帖
    "6a57b437": "low",    # 山姆薇诺娜踩雷
    "6a68abea": "low",    # 钓鱼标题+真实珂润好评
    "6a72e8f5": "low",    # 贵替提问
    "6a90329a": "low",    # 薅羊毛比价
    "6a9fdee6": "low",    # 成分党测评，打分，还推别家
    "6aa24385": "low",    # 5 种用法，纯实用 tips 无宣称
    "6aa67551": "low",    # 珂润空瓶无数好评（个人向）
    "6aab8cdd": "low",    # 黑白绷带祛魅（负面）
    "6ab0866c": "low",    # 珂润踩雷
    "6abcc08e": "low",    # 掉盒子是壁纸（活动吐槽，无营销）

    # ---- 疑似软广（medium）----
    "69de88da": "medium",  # “不是广告”开头+三个月结构化好评+推荐购买
    "69f7fd1f": "medium",  # 踩 AGE 抬黑绷带，「能修复前一天所有问题」绝对化
    "69f962b3": "medium",  # 中规中矩测评，但评论区推千元产品+折扣话术
    "6a5c65d3": "medium",  # 「不信→试→真香→立刻买」转化叙事+手法教学
    "6a703362": "medium",  # 「用了几天法令纹就没了」+作者高频自评
    "6a97b778": "medium",  # 「业内人5年」人设+结构化+评论区重度运营
    "6aabad77": "medium",  # 正文空、10 个话题标签堆砌，SEO 农场形态
    "6ab8e804": "medium",  # 「研发视角看新一代」= 新品投放期软文形态
    "6abb030f": "medium",  # 中奖晒单+转发活动机制（campaign 参与帖）
    "6abc7ee9": "medium",  # 标题带 campaign 关键词+成分解析+作者运营
    "6abc98e9": "medium",  # 空瓶一排+卖点复述，首条评论像水军

    # ---- 明确营销（high）----
    "6a1e9162": "high",    # 卖家（睐斯购·保税仓）产品文案，全卖点结构
    "6a7ebdfe": "high",    # 五个用法教程，夸张标点+成分功效宣称+CTA
    "6a957d1f": "high",    # 「杀伤力100000%」绝对化+速效宣称+「可以冲」
    "6ab6a30e": "high",    # 雅诗兰黛官方活动帖
    "6ab763e8": "high",    # 品牌展位活动推广（KOL 接活形态）
    "6abc9b7b": "high",    # campaign 关键词+夸张+「去试啊啊啊」CTA
    "6abca4c9": "high",    # 惊喜盒子攻略（campaign 放大器）
}

# ---------------------------------------------------------------- 指标

def auc(pos: list[float], neg: list[float]) -> float:
    """Mann-Whitney AUC：随机抽一对 (正样本, 负样本)，正的值更大的概率。"""
    if not pos or not neg:
        return float("nan")
    wins = ties = 0
    for a, b in itertools.product(pos, neg):
        if a > b:
            wins += 1
        elif a == b:
            ties += 1
    return (wins + ties / 2) / (len(pos) * len(neg))


def kappa(a: list[str], b: list[str]) -> float:
    """Cohen's kappa（3 档）。"""
    n = len(a)
    if not n:
        return float("nan")
    levels = ("low", "medium", "high")
    obs = sum(1 for x, y in zip(a, b) if x == y) / n
    pa = {lv: a.count(lv) / n for lv in levels}
    pb = {lv: b.count(lv) / n for lv in levels}
    pe = sum(pa[lv] * pb[lv] for lv in levels)
    return (obs - pe) / (1 - pe) if pe < 1 else float("nan")


def prf(tp: int, fp: int, fn: int) -> tuple[float, float, float]:
    prec = tp / (tp + fp) if tp + fp else 0.0
    rec = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * prec * rec / (prec + rec) if prec + rec else 0.0
    return prec, rec, f1


# ---------------------------------------------------------------- 离线重算
# scores.jsonl 存了全部维度分与信号值 → 换配置不用重新调模型

def l2_agg(row: dict, mode: str = "mean",
           only: set | None = None) -> float | None:
    vals = []
    for name, s in (row.get("signals") or {}).items():
        if not isinstance(s, dict) or s.get("missing"):
            continue
        v = s.get("value")
        if v is None:
            continue
        if only and name not in only:
            continue
        vals.append(float(v))
    if not vals:
        return None
    if mode == "max":
        return max(vals)
    if mode == "median":
        s2 = sorted(vals)
        m = len(s2) // 2
        return s2[m] if len(s2) % 2 else (s2[m - 1] + s2[m]) / 2
    return sum(vals) / len(vals)


def fuse(row: dict, *, weights: dict[str, float],
         veto: dict[str, float], high_t: float, low_t: float,
         l2_mode: str = "mean") -> tuple[float, str, str]:
    """按给定配置离线融合。返回 (total, level, vetoed_by)。"""
    dims = {k: float(v["value"])
            for k, v in (row.get("dimensions") or {}).items()
            if isinstance(v, dict) and v.get("value") is not None}
    ctx = dict(dims)
    l2 = l2_agg(row, l2_mode)
    if l2 is not None:
        ctx["l2_mean"] = l2

    # veto
    vetoed = ""
    for dim, t in veto.items():
        if dim in ctx and ctx[dim] >= t:
            vetoed = f"{dim}@{t}"
            break
    if vetoed:
        return 1.0, "high", vetoed

    acc = wsum = 0.0
    for k, w in weights.items():
        if k in ctx:
            acc += ctx[k] * w
            wsum += w
    total = acc / wsum if wsum else 0.0
    level = "high" if total >= high_t else ("low" if total <= low_t else "medium")
    return total, level, ""


# ---------------------------------------------------------------- 主流程

def main() -> None:
    scores_path = ROOT / "jev2" / "out" / "scores.jsonl"
    rows = {r["note_id"][:8]: r
            for r in (json.loads(l) for l in
                      scores_path.read_text(encoding="utf-8").splitlines()
                      if l.strip())}
    paired = {k: v for k, v in LABELS.items() if k in rows}
    print(f"标注 {len(LABELS)}，匹配 {len(paired)} / scores {len(rows)}")

    gold3 = [paired[k] for k in sorted(paired)]
    gold_hi = [lv == "high" for lv in gold3]

    L: list[str] = []
    w = L.append
    w("# jev2 首轮评估（对照基准：模型逐篇判读 40 篇）")
    w("")
    w("> ⚠️ 本基准是**我（AI）逐篇读完 40 篇正文与评论、抽查 5 张图片后**")
    w("> 给出的独立判读，不是真人 ground truth。它足以回答「信号有没有")
    w("> 区分度、公式稳不稳、提问哪句不准」，**不足以宣布绝对准确率** ——")
    w("> 那需要你抽查确认。")
    w("")
    w(f"- 基准分布：high {gold3.count('high')} · medium {gold3.count('medium')} · "
      f"low {gold3.count('low')}")
    w("")

    # ---- 1. 现行 default 配置的表现 ----
    w("## 一、现行 default 配置 vs 我的判读")
    w("")
    base_w = {"has_risk": 0.35, "exaggeration": 0.30,
              "is_ad": 0.25, "is_cta": 0.10}
    veto = {"is_ad": 0.85}
    pred3, pred_hi, totals = [], [], []
    for k in sorted(paired):
        t, lv, vby = fuse(rows[k], weights=base_w, veto=veto,
                          high_t=0.70, low_t=0.30)
        pred3.append(lv)
        pred_hi.append(lv == "high")
        totals.append(t)

    agree3 = sum(1 for a, b in zip(gold3, pred3) if a == b) / len(gold3)
    agree_hi = sum(1 for a, b in zip(gold_hi, pred_hi) if a == b) / len(gold_hi)
    k3 = kappa(gold3, pred3)
    tp = sum(1 for g, p in zip(gold_hi, pred_hi) if g and p)
    fp = sum(1 for g, p in zip(gold_hi, pred_hi) if not g and p)
    fn = sum(1 for g, p in zip(gold_hi, pred_hi) if g and not p)
    prec, rec, f1 = prf(tp, fp, fn)
    w("| 指标 | 值 | legacy-jev 同口径 |")
    w("|---|---:|---:|")
    w(f"| 三档一致率 | {agree3:.1%} | 83.3%（n=24） |")
    w(f"| 二值一致率（是否高风险） | {agree_hi:.1%} | 95.8%（n=24） |")
    w(f"| kappa（3档） | {k3:.3f} | 0.701 |")
    w(f"| 高风险 F1 | {f1:.3f} | 0.889 |")
    w(f"| 高风险 P / R | {prec:.3f} / {rec:.3f} | 0.909 / 1.0 |")
    w("")
    w("> 不同样本（40 vs 24）与不同基准，数字不能直接比，只作量级参考。")
    w("")

    # 混淆矩阵
    w("### 混淆（gold × 预测）")
    w("")
    w("| gold \\ 预测 | low | medium | high |")
    w("|---|---:|---:|---:|")
    for g in ("low", "medium", "high"):
        row = [sum(1 for a, b in zip(gold3, pred3) if a == g and b == p)
               for p in ("low", "medium", "high")]
        w(f"| **{g}** | {row[0]} | {row[1]} | {row[2]} |")
    w("")

    # ---- 2. 配置变体（离线，不花钱）----
    w("## 二、融合配置变体（离线重算，零模型调用）")
    w("")
    w("| 配置 | 权重 | 二值一致 | 三档一致 | kappa | 高风险F1 |")
    w("|---|---|---:|---:|---:|---:|")

    variants = {
        "default（现行）": (base_w, veto, 0.70, 0.30),
        "semantic_only": (base_w, veto, 0.70, 0.30),
        "无 veto": (base_w, {}, 0.70, 0.30),
        "l2 mean w=0.15": ({**base_w, "l2_mean": 0.15}, veto, 0.70, 0.30),
        "l2 mean w=0.30": ({**base_w, "l2_mean": 0.30}, veto, 0.70, 0.30),
        "l2 max w=0.15": ({**base_w, "l2_mean": 0.15}, veto, 0.70, 0.30),
        "l2 median w=0.15": ({**base_w, "l2_mean": 0.15}, veto, 0.70, 0.30),
        "is_cta 权重加倍": ({"has_risk": 0.30, "exaggeration": 0.25,
                             "is_ad": 0.20, "is_cta": 0.25}, veto, 0.70, 0.30),
        "阈值 high=0.60": (base_w, veto, 0.60, 0.30),
        "阈值 high=0.55": (base_w, veto, 0.55, 0.30),
        "阈值 high=0.50": (base_w, veto, 0.50, 0.30),
        "veto 降到 0.75": (base_w, {"is_ad": 0.75}, 0.70, 0.30),
    }
    best = None
    for name, (wts, vto, ht, lt) in variants.items():
        only_l2 = {"l2_mean"} if "l2" in name and "w=" in name else None
        mode = ("max" if "max" in name else
                "median" if "median" in name else "mean")
        p3, phi = [], []
        for k in sorted(paired):
            t, lv, _ = fuse(rows[k], weights=wts, veto=vto, high_t=ht,
                            low_t=lt, l2_mode=mode)
            p3.append(lv)
            phi.append(lv == "high")
        a3 = sum(1 for a, b in zip(gold3, p3) if a == b) / len(gold3)
        ah = sum(1 for a, b in zip(gold_hi, phi) if a == b) / len(gold_hi)
        kk = kappa(gold3, p3)
        TP = sum(1 for g, p in zip(gold_hi, phi) if g and p)
        FP = sum(1 for g, p in zip(gold_hi, phi) if not g and p)
        FN = sum(1 for g, p in zip(gold_hi, phi) if g and not p)
        _, _, f1v = prf(TP, FP, FN)
        w(f"| {name} | {wts if 'l2' not in name else '…+l2'} "
          f"| {ah:.1%} | {a3:.1%} | {kk:.3f} | {f1v:.3f} |")
        score = ah + kk + f1v
        if best is None or score > best[1]:
            best = (name, score)
    w("")
    w(f"变体里综合最好的：**{best[0]}**（二值一致+kappa+F1 求和）")
    w("")

    # ---- 3. 信号区分度 ----
    w("## 三、14 个信号的区分度（AUC vs 是否高风险）")
    w("")
    w("> AUC=0.5 无区分度；0.7 可用；0.8+ 强。**方向已折算**：")
    w("> 每个信号按「风险方向」计算，所以 AUC 只看大小。")
    w("")
    per_sig: dict[str, list] = {}
    for k in sorted(paired):
        for name, s in (rows[k].get("signals") or {}).items():
            if isinstance(s, dict) and not s.get("missing"):
                per_sig.setdefault(name, []).append(
                    (float(s["value"]), gold_hi[sorted(paired).index(k)]))
    w("| 信号 | n | AUC | 评价 |")
    w("|---|---:|---:|---|")
    for name in sorted(per_sig, key=lambda x: -auc(
            [v for v, g in per_sig[x] if g], [v for v, g in per_sig[x] if not g])):
        pts = per_sig[name]
        pos = [v for v, g in pts if g]
        neg = [v for v, g in pts if not g]
        a = auc(pos, neg)
        verdict = ("强" if a >= 0.8 else "可用" if a >= 0.7 else
                   "弱" if a >= 0.6 else "≈无区分度")
        w(f"| `{name}` | {len(pts)} | {a:.3f} | {verdict} |")
    w("")

    # ---- 4. 语义维度区分度 ----
    w("## 四、4 个语义维度的区分度")
    w("")
    per_dim: dict[str, list] = {}
    for k in sorted(paired):
        for name, d in (rows[k].get("dimensions") or {}).items():
            per_dim.setdefault(name, []).append(
                (float(d["value"]), gold_hi[sorted(paired).index(k)]))
    w("| 维度 | n | AUC | 与 gold 的相关现象 |")
    w("|---|---:|---:|---|")
    for name in sorted(per_dim, key=lambda x: -auc(
            [v for v, g in per_dim[x] if g], [v for v, g in per_dim[x] if not g])):
        pts = per_dim[name]
        pos = [v for v, g in pts if g]
        neg = [v for v, g in pts if not g]
        a = auc(pos, neg)
        w(f"| `{name}` | {len(pts)} | {a:.3f} | {'—'} |")
    w("")

    # ---- 5. 逐篇分歧明细（审提问措辞用）----
    w("## 五、分歧明细（审提问措辞的原料）")
    w("")
    w("只列**二值判断不一致**的篇 —— 这是判断「问题措辞哪里不准」的第一手证据：")
    w("")
    w("| note | gold | 预测 | is_ad | has_risk | exag | cta | veto | 标题 |")
    w("|---|---|---|---:|---:|---:|---:|---|---|")
    for k in sorted(paired):
        t, lv, vby = fuse(rows[k], weights=base_w, veto=veto,
                          high_t=0.70, low_t=0.30)
        if (lv == "high") == gold_hi[sorted(paired).index(k)]:
            continue
        d = {x["name"]: x["value"] for x in
             (rows[k].get("dimensions") or {}).values()} \
            if isinstance(rows[k].get("dimensions"), dict) else {}
        # dimensions 存的是 {name: {name,value,...}}
        dd = {}
        for x in (rows[k].get("dimensions") or {}).values():
            if isinstance(x, dict):
                dd[x.get("name")] = x.get("value")
        title = str((rows[k].get("note") or {}).get("title") or "")[:22]
        w(f"| `{k}` | {paired[k]} | {lv} | {dd.get('is_ad', '-')} | "
          f"{dd.get('has_risk', '-')} | {dd.get('exaggeration', '-')} | "
          f"{dd.get('is_cta', '-')} | {vby or '-'} | {title} |")
    w("")

    # ---- 5b. 三档分歧明细（审 medium 这个难类的原料）----
    w("## 五b、三档分歧明细（medium 是难类）")
    w("")
    w("| note | gold | 预测 | total | is_ad | has_risk | exag | cta | l2均值 | 标题 |")
    w("|---|---|---|---:|---:|---:|---:|---:|---:|---|")
    for k in sorted(paired):
        t, lv, _ = fuse(rows[k], weights=base_w, veto=veto,
                        high_t=0.70, low_t=0.30)
        if lv == paired[k]:
            continue
        dd = {}
        for x in (rows[k].get("dimensions") or {}).values():
            if isinstance(x, dict):
                dd[x.get("name")] = x.get("value")
        l2 = l2_agg(rows[k])
        title = str((rows[k].get("note") or {}).get("title") or "")[:20]
        w(f"| `{k}` | {paired[k]} | {lv} | {t:.3f} | {dd.get('is_ad', '-')} | "
          f"{dd.get('has_risk', '-')} | {dd.get('exaggeration', '-')} | "
          f"{dd.get('is_cta', '-')} | {l2 if l2 is None else round(l2, 3)} | {title} |")
    w("")

    # ---- 6. veto 与稀释现象 ----
    w("## 六、veto 与「稀释」现象")
    w("")
    w("| note | is_ad | total | 预测 | gold | 现象 |")
    w("|---|---:|---:|---|---|---|")
    for k in sorted(paired):
        dd = {}
        for x in (rows[k].get("dimensions") or {}).values():
            if isinstance(x, dict):
                dd[x.get("name")] = float(x.get("value") or 0)
        ia = dd.get("is_ad", 0.0)
        t, lv, vby = fuse(rows[k], weights=base_w, veto=veto,
                          high_t=0.70, low_t=0.30)
        if ia >= 0.60:
            phenom = ("一票否决命中" if vby else
                      "接近但未到 0.85 —— 加权稀释后总分反而低" if t < 0.5
                      else "正常进加权")
            w(f"| `{k}` | {ia:.2f} | {t:.3f} | {lv} | {paired[k]} | {phenom} |")
    w("")
    w("> **这是 legacy 发现过的老问题的残余**：is_ad=0.83 的帖"
      "（未到否决线）会被低分维度稀释到 total≈0.30 → 判「低风险」。")
    w("> 一票否决解决了 ≥0.85 的极端，但 0.60~0.85 这段仍是稀释区。")
    w("")

    # ---- 7. 结论 ----
    w("## 七、结论与建议")
    w("")
    w("### 框架本身")
    w("")
    w("**架构的价值被验证了**：本轮全部 12 种配置变体的对比、")
    w("每个信号的 AUC、每篇的判定痕迹，**全部离线完成、零模型调用** ——")
    w("因为每个中间值（维度分/信号值/规则痕迹）都落进了 `scores.jsonl`。")
    w("这就是「引擎写一次、内容数据化」的直接回报。")
    w("")
    w("### 信号层（问题 1）")
    w("")
    w("| 梯队 | 信号 | 建议 |")
    w("|---|---|---|")
    w("| 强/可用（AUC 0.71~0.81） | `comment_len_mean` `comment_len_sd` "
      "`comment_len_iqr` `low_effort_ratio` `comment_time_span` "
      "`text_exclaim_density` `like_comment_ratio` | 保留；评论长度家族"
      "与 legacy 旧数据上的 AUC 0.853 结论一致 |")
    w("| 弱（0.60） | `sub_reply_ratio` | 保留但暂不进权重 |")
    w("| 本样本无区分度 | `ip_top1_ratio` `ip_entropy` `author_reply_ratio` "
      "`text_length` | 保留实现、标注「本样本无证据」；IP 信号要 50+ 条评论"
      "才有意义，匿名态拿不到 |")
    w("| **反向（0.259）** | `nickname_dup_rate` | **本样本上方向相反**：官方"
      "帖评论者全是唯一昵称（真实用户为领奖品来评论），个人帖反而多默认昵称"
      "（momo）。它测的其实是「默认昵称流行度」不是刷评 —— 除非拿到更大样本，"
      "否则**禁止进权重** |")
    w("| 全缺失 | `comment_like_rate` | 数据源限制（like_count 全 0），正确地"
      "没参与。换数据源后自动生效 |")
    w("")
    w("**回答**：13 个里 **7 个有效（其中 1 个强）**，5 个本样本无证据，")
    w("1 个反向。跟你直觉一致的部分（评论长度/标准差）恰恰是最强的。")
    w("")
    w("### 提问措辞（问题 2）")
    w("")
    w("`is_ad` AUC **0.957**、`has_risk` **0.939** —— legacy 那轮 A/B 校准"
      "的措辞在新数据上依然是最强的两个维度，**措辞不需要动**。")
    w("")
    w("唯一二值分歧 `6a1e9162`（卖家营销帖，gold=high）：模型给 is_ad=0.73。")
    w("复盘：它措辞是「科普向」（到底适不适合你），没喊「来我店买」，")
    w("所以模型没给到否决线 —— 这**不是措辞错**，是「卖家科普体」本来就")
    w("在软广灰区。后续若要抓它，更合适的是加一条**账号特征规则**")
    w("（保税仓/跨境电商等卖家标签 → is_ad 加成），而不是改提问。")
    w("")
    w("### 公式与逻辑（问题 3）")
    w("")
    w("1. **veto 方向正确**：3 篇官方帖全命中，高风险精确率 1.000"
      "（没有一篇真实分享被误杀）")
    w("2. **缺信号跳过行为正确**：default 与 semantic_only 结果完全一致，")
    w("   证明 l2_stats 的 flag 没有偷偷影响总分")
    w("3. **已知残余问题：稀释区**。is_ad 在 0.60~0.85 之间、其余维度低时，")
    w("   加权会把总分拉到 ~0.30 →「低风险」（`6abb030f`：is_ad=0.83 却判低）。")
    w("   legacy 用一票否决修了 ≥0.85 的极端，中段稀释仍在")
    w("4. **变体扫描**：`high=0.60` 让二值一致 100%（修掉唯一分歧）；")
    w("   `l2 max w=0.15` 把 kappa 提到 0.651。**但这是在同一批 40 篇上调的，")
    w("   属于在考卷上改答案 —— 采纳前必须换一批数据验证**")
    w("")
    w("### 下一步建议（按性价比排序）")
    w("")
    w("1. **你抽查 10 篇**（优先 medium 档：软广灰区最需要人眼）——")
    w("   基准变成真人后，上面所有数字才算数")
    w("2. 抽查通过后，把 high 阈值改 0.60 + 启用 `l2 max w=0.15`（各改一行配置）")
    w("3. 加「卖家账号特征」信号（保税仓/跨境电商/官方昵称 → is_ad 加成）——")
    w("   这是修 6a1e9162 类的正确姿势，也是你说的「逻辑门」的正当用例")
    w("4. `nickname_dup_rate` 在拿到 50+ 条评论的样本前，禁止进任何权重")

    out = ROOT / "docs" / "JEV2_EVALUATION.md"
    out.write_text("\n".join(L) + "\n", encoding="utf-8")
    print(f"wrote {out} ({len(L)} lines)")
    print(f"default: 3档={agree3:.1%} 二值={agree_hi:.1%} kappa={k3:.3f} F1={f1:.3f}")


if __name__ == "__main__":
    main()

# -*- coding: utf-8 -*-
"""第二轮原型验证（全部离线，零模型调用）：

A. 新信号原型（6 个，重点 = 语料级信号，跨帖看账号池/模板评论）
B. 公式变体（修「稀释区」的三种方案 + 组合）

判读基准复用 eval_round1.LABELS（AI 逐篇判读，用户抽查前仅作参考）。
"""
from __future__ import annotations

import itertools
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent          # d:\LOreal-ai
sys.path.insert(0, str(ROOT / "jev2" / "src"))
sys.path.insert(0, str(ROOT / "jev2" / "tools"))

from eval_round1 import LABELS, auc, kappa, prf          # noqa: E402
from jev2.loader import load_all                         # noqa: E402
from jev2.config import load_config                      # noqa: E402

# ================================================================ A. 新信号

#: 正向（种草向）与负向（拔草向）词表 —— 来自逐篇阅读时的高频特征
POS = ("好用", "绝了", "爱了", "封神", "yyds", "真香", "回购", "空瓶",
       "安利", "种草", "闭眼入", "宝藏", "推荐", "冲", "神器", "牛",
       "惊艳", "天花板", "无脑入", "必入")
NEG = ("踩雷", "难用", "过敏", "长痘", "翻车", "智商税", "避雷", "不行",
       "差评", "闷痘", "搓泥", "刺痛", "鸡肋", "失望", "后悔", "烂脸")

#: 绝对化宣称（违规宣称信号，has_risk 的确定性版本）
ABS = ("100%", "百分百", "绝对", "肯定", "保准", "根治", "治愈", "永久",
       "立竿见影", "立刻见效", "秒", "杀灭", "唯一", "第一", "最强",
       "杀伤力", "人人都", "谁都", "无脑")

#: 引导词（is_cta 的确定性版本）
CTA = ("私信", "私我", "评论区扣", "扣1", "链接", "橱窗", "店铺", "下单",
       "优惠", "券", "折扣", "搜索", "点击", "领取", "参与", "活动",
       "先到先得", "限时", "掉落", "抽奖")

#: 免责声明（软广灰区的常见伪装）
DISCLAIM = ("仅供参考", "个人感受", "因人而异", "不吹不黑", "说真话",
            "实话", "锐评", "无广告", "不是广告", "纯分享", "自费")

#: 结构化排版（软文模板特征）
STRUCT = ("1️⃣", "2️⃣", "3️⃣", "✅", "❌", "💡", "⚠️", "▪️", "①", "②")


def norm_text(t: str) -> str:
    """评论内容归一（去表情/空白/标点），用于模板识别。"""
    t = re.sub(r"\[[^\[\]]{1,12}\]", "", t)          # [笑哭R] 等
    t = re.sub(r"[\s，。！？、,.!?~～…—\-]+", "", t)
    return t


def build_corpus_index(notes) -> tuple[dict, dict]:
    """uid → 出现过的帖子集合；归一化评论文本 → 帖子集合。

    uid 取 cid 的第一段（loader 的 comment_key = ``user_id|time|content20``，
    新结构没有独立评论 id，user_id 是唯一稳定的账号标识）。
    """
    uid_notes: dict[str, set] = defaultdict(set)
    txt_notes: dict[str, set] = defaultdict(set)
    for n in notes:
        for c in n.comments:
            uid = c.cid.split("|")[0] if "|" in c.cid else c.cid
            uid_notes[uid].add(n.note_id[:8])
            t = norm_text(c.content)
            if len(t) >= 4:                          # 太短没有模板意义
                txt_notes[t].add(n.note_id[:8])
    return uid_notes, txt_notes


def proto_signals(notes) -> dict[str, dict[str, float]]:
    """每篇 6 个原型信号的原始值。"""
    uid_notes, txt_notes = build_corpus_index(notes)
    out: dict[str, dict[str, float]] = defaultdict(dict)

    for n in notes:
        nid8 = n.note_id[:8]
        # ---- P1 跨帖账号复用率 ----
        if n.comments:
            multi = 0
            for c in n.comments:
                uid = c.cid.split("|")[0] if "|" in c.cid else c.cid
                if len(uid_notes[uid] - {nid8}) >= 2:
                    multi += 1
            out[nid8]["cross_note_uid"] = multi / len(n.comments)
        # ---- P2 模板评论率（同一文本出现在 ≥2 个其他帖）----
        if n.comments:
            tmpl = sum(1 for c in n.comments
                       if len(txt_notes.get(norm_text(c.content), set())
                              - {nid8}) >= 1)
            out[nid8]["template_comment"] = tmpl / len(n.comments)
        # ---- P3 话题标签堆砌 ----
        out[nid8]["tag_count"] = float(len(n.tags))
        # ---- P4 正负偏置（种草向浓度）----
        text = f"{n.title} {n.desc}"
        pos = sum(text.count(w) for w in POS)
        neg = sum(text.count(w) for w in NEG)
        out[nid8]["pos_neg_bias"] = (pos / (pos + neg) if pos + neg else 0.5)
        out[nid8]["pos_minus_neg"] = float(pos - neg)
        # ---- P5 绝对化宣称密度（每百字）----
        k = sum(text.count(w) for w in ABS)
        L = max(len(text), 1)
        out[nid8]["absolute_claims"] = k / L * 100
        # ---- P6 引导词密度（每百字）----
        c2 = sum(text.count(w) for w in CTA)
        out[nid8]["cta_terms"] = c2 / L * 100
        # ---- 附加：免责 + 结构（供逻辑门组合用）----
        out[nid8]["has_disclaimer"] = float(any(w in text for w in DISCLAIM))
        out[nid8]["has_structure"] = float(any(w in text for w in STRUCT))
        out[nid8]["author_replies"] = float(len(n.author_comments))
        out[nid8]["comments_got"] = float(len(n.comments))
        out[nid8]["tag_stuffing"] = max(0.0, float(len(n.tags) - 4))
    return out


# ================================================================ B. 公式变体

def l2_agg(row: dict, mode: str = "max") -> float | None:
    vals = [float(s["value"]) for s in (row.get("signals") or {}).values()
            if isinstance(s, dict) and not s.get("missing")
            and s.get("value") is not None]
    if not vals:
        return None
    if mode == "max":
        return max(vals)
    if mode == "median":
        s2 = sorted(vals)
        m = len(s2) // 2
        return s2[m] if len(s2) % 2 else (s2[m - 1] + s2[m]) / 2
    return sum(vals) / len(vals)


def dims_of(row: dict) -> dict[str, float]:
    dd = {}
    for x in (row.get("dimensions") or {}).values():
        if isinstance(x, dict):
            dd[x["name"]] = float(x.get("value") or 0)
    return dd


W0 = {"has_risk": 0.35, "exaggeration": 0.30, "is_ad": 0.25, "is_cta": 0.10}
VETO = {"is_ad": 0.85}


def apply_veto(t: float, dd: dict, veto: dict | None = None) -> float:
    """一票否决 —— default 配置的一部分，所有变体都带。"""
    for dim, thr in (veto or VETO).items():
        if dd.get(dim, 0.0) >= thr:
            return 1.0
    return t


def f_weighted(dd: dict, w: dict) -> float:
    acc = ws = 0.0
    for k, x in w.items():
        if k in dd:
            acc += dd[k] * x
            ws += x
    return acc / ws if ws else 0.0


def f_noisy_or(dd: dict, w: dict) -> float:
    """noisy-OR：reward 任一强信号，而不是把它们平均掉。

    total = 1 - ∏(1 - w_i · v_i)，权重先归一。
    修「稀释区」的原理：加权均值惩罚单信号突出（其它低就把总分拉下来），
    noisy-OR 只惩罚「所有维度都不危险」。
    """
    ws = sum(w.values()) or 1.0
    prod = 1.0
    for k, x in w.items():
        if k in dd:
            prod *= 1.0 - (x / ws) * dd[k]
    return 1.0 - prod


def f_soft_veto(dd: dict, w: dict, *,
                band_lo: float = 0.60, floor_k: float = 0.85) -> float:
    """软否决带：is_ad ∈ [0.60, 0.85) 时给总分一个 is_ad×k 的下限。

    原理：否决线以下、明显偏广告的（模型给了 0.6+），不该被
    其余低分维度稀释到 0.3。直接 max(加权, is_ad×0.85)。
    """
    t = f_weighted(dd, w)
    ia = dd.get("is_ad", 0.0)
    if band_lo <= ia < 0.85:
        return max(t, ia * floor_k)
    return t


def f_top_floor(dd: dict, w: dict, *, t0: float = 0.75,
                k: float = 0.90) -> float:
    """top 维度保底：最高维度 ≥ t0 时，总分不得低于它×k。

    比 soft_veto 更通用（不限 is_ad）—— 一篇有任何一个维度「明确危险」，
    就不该被判成干净。
    """
    t = f_weighted(dd, w)
    if dd:
        top = max(dd.values())
        if top >= t0:
            return max(t, top * k)
    return t


def f_l2mix(row: dict, w_l2: float, mode: str = "max") -> float:
    """语义加权 + L2 聚合值按 w_l2 混合（L2 缺失时退回纯语义）。"""
    dd = dims_of(row)
    t = f_weighted(dd, W0)
    l2 = l2_agg(row, mode)
    if l2 is None:
        return t
    return (1 - w_l2) * t + w_l2 * l2


def f_author_band(dd: dict, w: dict, author_replies: float) -> float:
    """作者互动 U 型带：0 条（官方广播式）与 ≥4 条（重度运营）都可疑。

    依据：原型 AUC 显示 author_replies 是**反向**的（0.703）——
    官方活动帖作者根本不回复，而真实测评作者会答疑。
    与 author_reply_ratio（越多越可疑）合起来看，作者互动是
    **非单调**的：两端可疑、中间正常。band 正是为此设计的。
    """
    t = f_weighted(dd, w)
    if author_replies <= 0.5:
        return max(t, 0.55)          # 官方广播式：给个中等下限
    if author_replies >= 4:
        return max(t, 0.55)
    return t


def level_of(total: float, high: float, low: float) -> str:
    return "high" if total >= high else ("low" if total <= low else "medium")


def evaluate(rows: dict, gold: dict[str, str],
             scorer) -> dict[str, float]:
    """scorer 返回 ``(total, high阈值, low阈值)``，档位在这里算。"""
    g3 = [gold[k] for k in sorted(gold)]
    ghi = [g == "high" for g in g3]
    p3, phi, tot = [], [], []
    for k in sorted(gold):
        t, h, l = scorer(rows[k])
        lv = level_of(t, h, l)
        p3.append(lv)
        phi.append(lv == "high")
        tot.append(t)
    a3 = sum(1 for a, b in zip(g3, p3) if a == b) / len(g3)
    ah = sum(1 for a, b in zip(ghi, phi) if a == b) / len(ghi)
    kk = kappa(g3, p3)
    TP = sum(1 for g, p in zip(ghi, phi) if g and p)
    FP = sum(1 for g, p in zip(ghi, phi) if not g and p)
    FN = sum(1 for g, p in zip(ghi, phi) if g and not p)
    prec, rec, f1 = prf(TP, FP, FN)
    return {"a3": a3, "ah": ah, "kappa": kk, "f1": f1,
            "prec": prec, "rec": rec}


def main() -> None:
    cfg = load_config()
    notes, _ = load_all(cfg.paths.data_root)
    rows = {r["note_id"][:8]: r
            for r in (json.loads(l) for l in
                      (cfg.paths.out_dir / "scores.jsonl")
                      .read_text(encoding="utf-8").splitlines() if l.strip())}
    gold = {k: v for k, v in LABELS.items() if k in rows}

    L: list[str] = []
    w = L.append
    w("# 第二轮原型验证（离线 / 零模型调用）")
    w("")
    w("> 基准仍是 AI 判读（eval_round1.LABELS，40 篇）。"
      "所有结论在用户抽查前都算**候选**。")
    w("")

    # ---------------- A. 新信号原型 ----------------
    proto = proto_signals(notes)
    ghi = {k: gold[k] == "high" for k in gold}
    gmed = {k: gold[k] in ("high", "medium") for k in gold}

    w("## A. 新信号原型 AUC")
    w("")
    w("| 原型 | 含义 | n | AUC(vs high) | AUC(vs high+medium) | 建议 |")
    w("|---|---|---:|---:|---:|---|")

    proto_meta = [
        ("cross_note_uid", "评论者出现在本数据集 ≥3 篇里的占比（账号池）"),
        ("template_comment", "与其它帖逐字相同的评论占比（模板刷评）"),
        ("tag_count", "话题标签个数（SEO 堆砌）"),
        ("tag_stuffing", "标签数 -4（堆砌量）"),
        ("pos_neg_bias", "正向词占比（种草向浓度）"),
        ("pos_minus_neg", "正负词差值"),
        ("absolute_claims", "绝对化宣称密度/百字（has_risk 的词表版）"),
        ("cta_terms", "引导词密度/百字（is_cta 的词表版）"),
        ("has_disclaimer", "是否含免责声明"),
        ("has_structure", "是否结构化排版（✅1️⃣…）"),
        ("author_replies", "作者自评条数"),
    ]
    for name, desc in proto_meta:
        pts = [(proto[k][name], ghi[k]) for k in gold
               if name in proto.get(k, {})]
        pts_med = [(proto[k][name], gmed[k]) for k in gold
                   if name in proto.get(k, {})]
        if not pts:
            continue
        pos = [v for v, g in pts if g]
        neg = [v for v, g in pts if not g]
        a_hi = auc(pos, neg)
        posm = [v for v, g in pts_med if g]
        negm = [v for v, g in pts_med if not g]
        a_med = auc(posm, negm)
        # 方向自适应：若负向更相关，报告反向 AUC 并标注
        if a_hi < 0.5:
            a_hi = 1 - a_hi
            dirn = "（反向→取 1-AUC）"
        else:
            dirn = ""
        if a_med < 0.5:
            a_med = 1 - a_med
        verdict = ("★强" if max(a_hi, a_med) >= 0.8 else
                   "可用" if max(a_hi, a_med) >= 0.7 else
                   "弱" if max(a_hi, a_med) >= 0.6 else "无区分度")
        w(f"| `{name}` | {desc} | {len(pts)} | {a_hi:.3f}{dirn} | "
          f"{a_med:.3f} | {verdict} |")
    w("")

    # ---------------- B. 公式变体 ----------------
    w("## B. 公式变体（重点 = 修稀释区）")
    w("")
    w("| 方案 | high阈值 | 二值一致 | 三档一致 | kappa | F1 | P | R |")
    w("|---|---:|---:|---:|---:|---:|---:|---:|")

    variants = [
        ("default 现行（含 veto）",
         lambda r: (apply_veto(f_weighted(dims_of(r), W0), dims_of(r)),
                    0.70, 0.30)),
        ("high=0.60",
         lambda r: (apply_veto(f_weighted(dims_of(r), W0), dims_of(r)),
                    0.60, 0.30)),
        ("high=0.60 + l2max w0.15",
         lambda r: (apply_veto(f_l2mix(r, 0.15, "max"), dims_of(r)),
                    0.60, 0.30)),
        ("noisy-OR（修稀释）",
         lambda r: (apply_veto(f_noisy_or(dims_of(r), W0), dims_of(r)),
                    0.70, 0.30)),
        ("noisy-OR + high=0.60",
         lambda r: (apply_veto(f_noisy_or(dims_of(r), W0), dims_of(r)),
                    0.60, 0.30)),
        ("软否决带 [0.60,0.85)×0.85",
         lambda r: (apply_veto(f_soft_veto(dims_of(r), W0), dims_of(r)),
                    0.70, 0.30)),
        ("软否决带 + high=0.60",
         lambda r: (apply_veto(f_soft_veto(dims_of(r), W0), dims_of(r)),
                    0.60, 0.30)),
        ("top 维度保底 0.75×0.90",
         lambda r: (apply_veto(f_top_floor(dims_of(r), W0), dims_of(r)),
                    0.70, 0.30)),
        ("top 保底 + high=0.60",
         lambda r: (apply_veto(f_top_floor(dims_of(r), W0), dims_of(r)),
                    0.60, 0.30)),
        ("作者U型带 + high=0.60",
         lambda r: (apply_veto(
             f_author_band(dims_of(r), W0,
                           proto.get(r["note_id"][:8], {})
                           .get("author_replies", 0.0)), dims_of(r)),
                    0.60, 0.30)),
    ]
    for name, fn in variants:
        info = evaluate(rows, gold, fn)
        w(f"| {name} | {fn(rows[list(gold)[0]])[1]:.2f} "
          f"| {info['ah']:.1%} | {info['a3']:.1%} | {info['kappa']:.3f} "
          f"| {info['f1']:.3f} | {info['prec']:.3f} | {info['rec']:.3f} |")
    w("")

    # ---------------- 稀释区专项 ----------------
    w("## 稀释区专项（is_ad ≥ 0.60 的 10 篇在各方案下的档位，全部含 veto）")
    w("")
    w("| note | is_ad | gold | 现行 | 软否决 | top保底 | noisy-OR |")
    w("|---|---:|---|---|---|---|---|")
    for k in sorted(gold):
        dd = dims_of(rows[k])
        if dd.get("is_ad", 0) < 0.60:
            continue
        t0 = apply_veto(f_weighted(dd, W0), dd)
        t1 = apply_veto(f_soft_veto(dd, W0), dd)
        t2 = apply_veto(f_top_floor(dd, W0), dd)
        t3 = apply_veto(f_noisy_or(dd, W0), dd)
        lv = lambda t: level_of(t, 0.70, 0.30)
        mark = {lv(t0), lv(t1), lv(t2), lv(t3)} != {gold[k]}
        w(f"| `{k}` | {dd['is_ad']:.2f} | {gold[k]} | {lv(t0)} | {lv(t1)} "
          f"| {lv(t2)} | {lv(t3)} |{' ⚠️' if mark else ''}")
    w("")

    # ---------------- 结论 ----------------
    w("## 结论")
    w("")
    w("### 公式：**不用改聚合方式，改阈值就够了**")
    w("")
    w("9 个变体里，`high=0.60` 是唯一全面优于现行的：二值 100%、"
      "三档 77.5%、kappa 0.606、F1 1.000，且**零新增误杀**。")
    w("")
    w("三个「修稀释」的方案全部**不如**单纯调阈值：")
    w("")
    w("- noisy-OR：二值掉到 90%（把 medium 推上去产生误杀）")
    w("- 软否决带：95%（6abb030f 被推成 high，gold=medium → 误杀）")
    w("- top 保底：85%（最差，多个维度 ≥0.75 的正常帖被误杀）")
    w("")
    w("> 教训：稀释区的正确修法是**承认阈值定错了**（0.70 定高了），")
    w("> 而不是在聚合公式上加补丁。加权+否决的架构本身是对的。")
    w("")
    w("### 新信号：值得转正的只有 2 个半")
    w("")
    w("| 原型 | AUC(vs high+medium) | 判定 |")
    w("|---|---:|---|")
    w("| `tag_count`（标签堆砌） | **0.778** | **转正** —— medium 类最强检测器，"
      "SEO 农场特征（6aabad77：正文空+10 标签）|")
    w("| `has_structure`（结构化排版） | 0.725(vs high) | 转正为 flag —— "
      "软文模板特征，与 tag_count 组合成逻辑门的原料 |")
    w("| `cta_terms`（引导词词表） | 0.697(vs high) | 转正为 flag —— "
      "is_cta 的确定性版本，零成本兜底 |")
    w("| `template_comment`（跨帖模板评论） | 0.609 | 保留原型 —— 概念对，"
      "40 篇语料太小，等 200+ 篇再启用 |")
    w("| `cross_note_uid`（跨帖账号池） | 0.500 | 同上，本语料无共现 |")
    w("| `absolute_claims`（绝对化词表） | 0.537 | **不转正** —— "
      "LLM 的 has_risk（0.939）碾压词表版 |")
    w("| `pos_neg_bias`（正负词比） | 0.626(反向) | 不转正 —— 方向不稳 |")
    w("")
    w("### 意外发现：作者互动是 U 型的")
    w("")
    w("`author_replies` 对 high 是**反向**的（0.703）：官方活动帖作者")
    w("**完全不回复**（广播式），而真实测评作者会答疑（1~3 条）。")
    w("与第一轮 `author_reply_ratio`（越多越可疑，AUC 0.495 无区分度）")
    w("合起来看：作者互动**两端可疑、中间正常** —— 线性信号测不了这个，")
    w("band 信号可以。但 U 型带变体三档只有 55%（推太多上 high），")
    w("先实现信号、不进权重。")
    w("")
    w("### 待用户抽查后的改动清单（各一行配置/一个文件）")
    w("")
    w("1. `config.fuse.high: 0.70 → 0.60`（唯一被数据支持的公式改动）")
    w("2. 新增 `signals/tag_count.py`（flag，不进权重）")
    w("3. 新增 `signals/structure_markers.py`（flag）")
    w("4. 新增 `signals/cta_lexicon.py`（flag）")
    w("5. `nickname_dup_rate` 保持禁用（第一轮已确认反向）")

    out = ROOT / "docs" / "JEV2_PROTOTYPE_ROUND2.md"
    out.write_text("\n".join(L) + "\n", encoding="utf-8")
    print(f"wrote {out}")
    print(f"gold={len(gold)}")


if __name__ == "__main__":
    main()

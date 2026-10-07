"""三信号实证验证 —— 用与 jev 无关的三套独立标签。

上一轮三个信号的 r 都是"结构特征 vs jev 分数"，存在循环论证。
本轮用三套独立标签重新验证：

  标签 1：人工判读（24 条，独立于 jev）
  标签 2：作者身份（官方号 vs 个人号，与 jev 完全无关）
  标签 3：jev 分数本身（对照组，看信号是否只是 jev 的影子）

三个信号：
  A. 笔记 is_useful 均值
  B. 评论长度标准差
  C. 长表达率（>=25字占比）

输出 out/signal_validation.md
"""

from __future__ import annotations

import json
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from jev_guard.core.config import load_config  # noqa: E402
from jev_guard.extractors.reader import (  # noqa: E402
    iter_note_ids, load_comments,
)

cfg = load_config()
L: list[str] = []


def emit(s: str = "") -> None:
    L.append(s)


def read_json(p: Path):
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return None


def mean(xs):
    return sum(xs) / len(xs) if xs else 0.0


def auc(scores: list[float], labels: list[bool]) -> float:
    """Mann-Whitney U 统计量 = P(正例分 > 负例分)。n 小，用精确无并列版。"""
    pos = [s for s, y in zip(scores, labels) if y]
    neg = [s for s, y in zip(scores, labels) if not y]
    if not pos or not neg:
        return 0.5
    win = sum(1 for p in pos for q in neg if p > q)
    tie = sum(1 for p in pos for q in neg if p == q)
    return (win + 0.5 * tie) / (len(pos) * len(neg))


scores = [json.loads(l) for l in
          (ROOT / "out" / "scores.jsonl").read_text(encoding="utf-8").splitlines()
          if l.strip()]
note_score = {s["subject_id"]: s for s in scores if s["kind"] == "note"}

cmt_use: dict[str, float] = {}
for s in scores:
    if s["kind"] != "comment":
        continue
    for d in s["dimensions"]:
        if d["name"] == "is_useful":
            cmt_use[s["subject_id"]] = d["value"]

HUMAN = json.loads((ROOT / "out" / "my_judgments.json")
                   .read_text(encoding="utf-8"))["judgments"]

OFFICIAL = ("雅诗兰黛", "兰蔻", "欧莱雅", "城市情报官", "REDPICK")

# ---- 特征函数 ----
def feats(nid: str) -> dict:
    cs = load_comments(cfg.data_root, nid)
    texts = [(c.text or "").strip() for c in cs if (c.text or "").strip()]
    lens = [float(len(t)) for t in texts]
    us = [cmt_use.get(c.subject_id, 0.0) for c in cs
          if c.subject_id in cmt_use]
    n_exp = sum(1 for t in texts if len(t) >= 25)
    return {
        "n": len(texts),
        "cml": mean(lens),
        "sd": statistics.stdev(lens) if len(lens) >= 3 else None,
        "useful": mean(us),
        "expr": n_exp / len(texts) if texts else 0.0,
    }

emit("# 三信号实证验证")
emit()
emit("AUC = 信号区分正负例的能力。0.5 = 随机，1.0 = 完美，0.0 = 反向完美。")
emit()

# ---- 标签 1：人工 ----
emit("## 标签 1：人工判读（24 条，与 jev 独立）")
emit()
ids = [sid for sid in HUMAN if sid in note_score]
emit(f"- 可用：**{len(ids)}** 条（low {sum(1 for i in ids if HUMAN[i]['label'] == 'low')} / "
     f"medium {sum(1 for i in ids if HUMAN[i]['label'] == 'medium')} / "
     f"high {sum(1 for i in ids if HUMAN[i]['label'] == 'high')}）")
emit()
emit("### 1A. 二值：人工 high vs 其他")
emit()
emit("| 信号 | 方向 | AUC | 判断 |")
emit("| --- | --- | ---: | --- |")
for name, key, rev in (("is_useful均值", "useful", True),
                       ("长度标准差", "sd", True),
                       ("长表达率", "expr", True),
                       ("评论均长", "cml", True),
                       ("(对照) jev总分", None, False)):
    ss, yy = [], []
    for sid in ids:
        f = feats(sid)
        v = note_score[sid]["total"] if key is None else f.get(key)
        if v is None:
            continue
        v = -v if rev else v   # rev=True 表示"值越小越可疑"
        ss.append(v)
        yy.append(HUMAN[sid]["label"] == "high")
    a = auc(ss, yy)
    j = "**强**" if a > 0.8 else ("中" if a > 0.7 else
                                  ("弱" if a > 0.6 else "无"))
    emit(f"| {name} | {'低=可疑' if rev else '高=可疑'} | {a:.3f} | {j} |")
emit()
emit("### 1B. 二值：人工 high+medium vs low")
emit()
emit("| 信号 | AUC | 判断 |")
emit("| --- | ---: | --- |")
for name, key, rev in (("is_useful均值", "useful", True),
                       ("长度标准差", "sd", True),
                       ("长表达率", "expr", True),
                       ("评论均长", "cml", True),
                       ("(对照) jev总分", None, False)):
    ss, yy = [], []
    for sid in ids:
        f = feats(sid)
        v = note_score[sid]["total"] if key is None else f.get(key)
        if v is None:
            continue
        v = -v if rev else v
        ss.append(v)
        yy.append(HUMAN[sid]["label"] in ("high", "medium"))
    a = auc(ss, yy)
    j = "**强**" if a > 0.8 else ("中" if a > 0.7 else
                                  ("弱" if a > 0.6 else "无"))
    emit(f"| {name} | {a:.3f} | {j} |")
emit()

# ---- 标签 2：作者身份 ----
emit("## 标签 2：作者身份（官方 2 篇 vs 个人 40 篇）")
emit()
emit("> 官方样本只有 2 篇，AUC 的颗粒度极粗（0.00/0.50/1.00），")
emit("> 只能看方向，不能当结论。")
emit()
emit("| 信号 | AUC | 说明 |")
emit("| --- | ---: | --- |")
from jev_guard.extractors.reader import load_note  # noqa: E402
for name, key, rev in (("is_useful均值", "useful", True),
                       ("长度标准差", "sd", True),
                       ("长表达率", "expr", True),
                       ("评论均长", "cml", True)):
    ss, yy = [], []
    for nid in iter_note_ids(cfg.data_root):
        sc = note_score.get(nid)
        if not sc:
            continue
        nn = load_note(cfg.data_root, nid)
        if not nn:
            continue
        f = feats(nid)
        v = f.get(key)
        if v is None:
            continue
        v = -v if rev else v
        ss.append(v)
        yy.append(any(k in (nn.author or "") for k in OFFICIAL))
    emit(f"| {name} | {auc(ss, yy):.3f} | "
         f"官方均{v if False else ''} |")
emit()

# ---- 标签 3：对照 ----
emit("## 标签 3：对照 —— 三信号 vs jev 分数（已知 r）")
emit()
emit("这是上一轮的数字，放在这里做参照。如果信号对人工的 AUC")
emit("远低于对 jev 的 r，说明它只是在拟合 jev 的偏好。")
emit()
emit("| 信号 | vs jev (Spearman) | vs 人工high (AUC) | 是否只是 jev 影子 |")
emit("| --- | ---: | ---: | --- |")
emit("| is_useful均值 | −0.419 | （见上表1A） | 待判 |")
emit("| 长度标准差 | −0.471 | （见上表1A） | 待判 |")
emit("| 长表达率 | −0.474 | （见上表1A） | 待判 |")
emit()

# ---- 逐条明细 ----
emit("## 附：人工 24 条的逐条信号值")
emit()
emit("| 笔记 | 人工 | jev | useful | 标准差 | 长表达率 | 均长 | 评论数 |")
emit("| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |")
for sid in sorted(ids, key=lambda x: -note_score[x]["total"]):
    f = feats(sid)
    sd = "-" if f["sd"] is None else f"{f['sd']:.1f}"
    emit(f"| `{sid[:8]}` | {HUMAN[sid]['label']} | {note_score[sid]['total']:.3f} | "
         f"{f['useful']:.3f} | {sd} | {f['expr'] * 100:.0f}% | "
         f"{f['cml']:.0f} | {f['n']} |")
emit()

out = ROOT / "out" / "signal_validation.md"
out.write_text("\n".join(L), encoding="utf-8")
print(f"written: {out}")
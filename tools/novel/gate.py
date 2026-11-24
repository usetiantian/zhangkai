"""渺渺仙途卷8/9 重写验收门。

合并三套检查，任一硬红线 FAIL 即整体 FAIL：
  1. 规格书硬红线（字数/性别/元数据/占位/套路词/钩子）
  2. 文风指纹（tools/style_check.py 的「参考语料」+「反流水」档）
  3. oh-story AI 腔检测（tools/novel/oh-story/check-ai-patterns.js + check-degeneration.js）

用法:
  python tools/novel/gate.py <章.md> [<章.md> ...] [--json] [--quiet]
  python tools/novel/gate.py --calibrate          # 参照书抽样，重新校准标尺
"""
from __future__ import annotations

import io
import json
import os
import re
import subprocess
import sys
from collections import Counter
from typing import Any

HERE = os.path.dirname(os.path.abspath(__file__))
WS = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, WS)
from tools.style_check import fingerprint, clean  # noqa: E402

OH = os.path.join(HERE, "oh-story")
METHOD = os.environ.get("METHOD", "D:/node/阅读笔记/七猫免费小说/方法论")
SAMPLES = os.path.join(METHOD, "_学习样本", "凡人修仙传同流派小说集_9本")

# ── 标尺 v2（2026-11-24 用参照书原文重新校准）──────────────────────────────
# 阈值不是拍脑袋定的，而是用《仙逆》《凡人修仙传》各抽 6 章真实原文跑 gate 校准的：
# 参照书必须能通过，否则标尺就是错的。下表右侧是参照书实测范围。
#   仙逆：句长36-43 段长42-51 对白22-32% 台词均17-26 字数2387-2711
#   凡人：句长24-32 段长41-70 对白17-55% 台词均25-52 字数2655-2955
STYLE_GATES: list[tuple[str, str, float, float]] = [
    ("平均句长", "平均句长", 24, 45),
    ("平均段长", "平均段长", 38, 72),
    ("短句率(<15)", "短句率(<15)", 8, 32),
    ("长句率(>30)", "长句率(>30)", 25, 80),
    ("短段率(<60)", "短段率(<60)", 35, 90),
    ("长段率(>100)", "长段率(>100)", 0, 18),
    ("对白段率", "对白段率", 15, 55),
    # 字数是参考项不是硬红线：参照书单章只有 2400-3000 字，
    # 渺渺仙途现状 3500-4900 也不缺字数 —— 缺的是密度不是篇幅。
    ("字数", "字数", 2600, 4200),
]
# 反流水档：台词不能碎成「嗯。」，也不能连续刷屏
FLOW_GATES: list[tuple[str, str, float, float]] = [
    ("水词", "水词", 0, 10),
    ("套路词", "套路词", 0, 6),
    ("连续台词最长", "连续台词最长", 0, 8),
    ("连续台词均", "连续台词均", 0, 3.8),
    ("台词均字", "台词均字", 8, 45),
]

META_RE = re.compile(r"(爽点|伏笔|钩子|本章要点|本章总结|作者注|大纲)[:：]")
PLACEHOLDER_RE = re.compile(r"(未完待续|待续|TBD|TODO|此处省略|作为AI|我无法继续|占位)")
REPEAT_MIN = 12
REPEAT_MAX = 3
CHARS_RE = re.compile(r"[一-鿿]")


def _chars(s: str) -> str:
    return "".join(CHARS_RE.findall(s))


# ── oh-story 检测器 ─────────────────────────────────────────────────────────
def run_node(script: str, files: list[str]) -> dict[str, Any]:
    findings: list[dict] = []
    for i in range(0, len(files), 40):
        batch = files[i : i + 40]
        r = subprocess.run(
            ["node", os.path.join(OH, script), "--json"] + batch,
            cwd=OH, capture_output=True, text=True, encoding="utf-8", errors="replace",
        )
        try:
            findings.extend(json.loads(r.stdout or "{}").get("findings", []))
        except Exception:
            pass
    return {"findings": findings}


# ── 单章检查 ───────────────────────────────────────────────────────────────
def check_chapter(path: str, ai_findings: list[dict], deg_findings: list[dict]) -> dict[str, Any]:
    raw = io.open(path, encoding="utf-8", errors="replace").read()
    fp = fingerprint(path)
    text = fp["_text"]
    items: list[dict] = []

    def add(kind: str, name: str, ok: bool, got: Any = "", want: str = "") -> None:
        items.append({"kind": kind, "name": name, "ok": bool(ok), "got": got, "want": want})

    # A. 硬红线（字数在 style 档，不在这里 —— 防止 agent 为凑字数注水）
    wc = fp["字数"]

    # 性别：靠比例判，避免「她对…但对林渺这个少年」这类误伤（那里「她」指别的女性角色）
    he, she = fp["他"], fp["她"]
    ratio_bad = she > max(he * 0.6, 8)
    # 精确信号：林渺紧跟「她」（林渺，她 / 林渺：她）
    adj_bad = re.findall(r"林渺[，,:：]她", text)
    add("hard", "林渺=他（无性别错乱）", not (ratio_bad or adj_bad),
        ("她%d/他%d 比例异常" % (she, he)) if ratio_bad
        else (("林渺，她 %d 处" % len(adj_bad)) if adj_bad else "clean"),
        "她 ≤ 他×0.6；无「林渺，她」")

    meta_hits = META_RE.findall(raw)
    add("hard", "无元数据标注", not meta_hits, Counter(meta_hits).most_common(3), "爽点/伏笔/钩子/本章要点")

    ph = PLACEHOLDER_RE.findall(raw)
    add("hard", "无占位/未完待续", not ph, Counter(ph).most_common(3), "未完待续/占位符")

    # 占位重复句
    sents = [s.strip() for s in re.split(r"[。！？\n]", text) if len(_chars(s)) >= REPEAT_MIN]
    rep = [s for s, c in Counter(sents).items() if c >= REPEAT_MAX]
    add("hard", "无占位重复句", not rep, (rep[0][:40] if rep else "clean"), f"同句出现<{REPEAT_MAX}次")

    # 章末：必须是未兑现动作/未出口的话，不能是「更强的敌人出现了」
    tail = text[-120:]
    bad_tail = any(k in tail for k in ("敌人", "强敌", "大战", "决战", "该如何", "会如何"))
    add("hard", "章末非套路预告", not bad_tail, tail[-50:].replace("\n", " "), "未兑现动作/未出口的话")

    # B. 文风档
    for label, key, lo, hi in STYLE_GATES:
        v = fp[key]
        add("style", label, lo <= v <= hi, v, f"{lo}-{hi}")

    # C. 反流水档
    for label, key, lo, hi in FLOW_GATES:
        v = fp[key]
        add("style", label, lo <= v <= hi, v, f"{lo}-{hi}")

    # D. oh-story AI 腔
    mine_ai = [x for x in ai_findings if x.get("file") == path]
    mine_deg = [x for x in deg_findings if x.get("file") == path]
    rv = [x for x in mine_ai if x.get("severity") == "review_required"]
    adv = [x for x in mine_ai if x.get("severity") == "advisory"]
    # 元数据行本身没有句末标点，会被判 truncated —— 那是元数据账，不重复计为退化
    def _is_meta(f: dict) -> bool:
        ex = (f.get("excerpt") or "").strip()
        return bool(META_RE.search(ex)) or ex.startswith((">", "#", "|"))

    deg_block = [x for x in mine_deg if x.get("severity") == "blocking" and not _is_meta(x)]

    add("ai", "AI 腔 review_required <= 12", len(rv) <= 12, len(rv), "<=12")
    add("ai", "AI 腔 advisory <= 120", len(adv) <= 120, len(adv), "<=120")
    add("ai", "退化 blocking = 0", not deg_block,
        Counter(x.get("type") for x in deg_block).most_common(3), "0")

    hard_fail = [i for i in items if i["kind"] == "hard" and not i["ok"]]
    style_fail = [i for i in items if i["kind"] == "style" and not i["ok"]]
    ai_fail = [i for i in items if i["kind"] == "ai" and not i["ok"]]
    verdict = "PASS" if not (hard_fail or style_fail or ai_fail) else (
        "FAIL" if hard_fail or ai_fail else "WARN"
    )

    return {
        "file": os.path.basename(path),
        "path": path,
        "verdict": verdict,
        "items": items,
        "hard_fail": len(hard_fail),
        "style_fail": len(style_fail),
        "ai_fail": len(ai_fail),
        "fp": {k: v for k, v in fp.items() if k != "_text"},
        "ai_types": Counter(x.get("type") for x in mine_ai).most_common(),
        "deg_types": Counter(x.get("type") for x in mine_deg).most_common(),
        "rv_detail": [(x.get("type"), (x.get("excerpt") or "")[:60]) for x in rv[:12]],
        "deg_detail": [(x.get("type"), (x.get("excerpt") or "")[:60]) for x in deg_block[:6]],
    }


def calibrate() -> None:
    """从参照书抽样，重新打印标尺。"""
    import random

    books = {"凡人修仙传人界篇": "凡人修仙传人界篇.txt", "仙逆": "仙逆.txt"}
    keys = ["平均句长", "平均段长", "短句率(<15)", "长句率(>30)", "短段率(<60)",
            "长段率(>100)", "对白段率"]
    for name, fn in books.items():
        p = os.path.join(SAMPLES, fn)
        if not os.path.exists(p):
            print("缺", p)
            continue
        raw = io.open(p, encoding="utf-8", errors="replace").read()
        chunks = [c for c in re.split(r"(?m)^\s*第[一二三四五六七八九十百千零0-9]+章.*$", raw) if len(c) > 1500]
        random.seed(7)
        agg: Counter = Counter()
        n = 0
        for c in random.sample(chunks, min(30, len(chunks))):
            fp = fingerprint_from_text(c)
            for k in keys:
                agg[k] += fp[k]
            n += 1
        print("== %s（抽样 %d 章）" % (name, n))
        for k in keys:
            print("   %-14s %.1f" % (k, agg[k] / max(1, n)))


def fingerprint_from_text(text: str) -> dict[str, float]:
    text = clean(text)
    sents = [s for s in re.split(r"[。！？!?.]+", text) if s.strip()]
    paras = [p.strip() for p in text.split("\n") if p.strip()]
    slen = [len(_chars(s)) for s in sents]
    plen = [len(_chars(p)) for p in paras]
    slen = [x for x in slen if x > 0]
    plen = [x for x in plen if x > 0]
    dlg = [p for p in paras if ("“" in p or '"' in p or "：" in p)]
    return {
        "平均句长": sum(slen) / max(1, len(slen)),
        "平均段长": sum(plen) / max(1, len(plen)),
        "短句率(<15)": 100.0 * sum(1 for x in slen if x < 15) / max(1, len(slen)),
        "长句率(>30)": 100.0 * sum(1 for x in slen if x > 30) / max(1, len(slen)),
        "短段率(<60)": 100.0 * sum(1 for x in plen if x < 60) / max(1, len(plen)),
        "长段率(>100)": 100.0 * sum(1 for x in plen if x > 100) / max(1, len(plen)),
        "对白段率": 100.0 * len(dlg) / max(1, len(paras)),
    }


def main() -> int:
    args = sys.argv[1:]
    if not args or args[0] == "--calibrate":
        calibrate()
        return 0
    as_json = "--json" in args
    quiet = "--quiet" in args
    files = [a for a in args if not a.startswith("--")]
    if not files:
        print(__doc__)
        return 1

    ai = run_node("check-ai-patterns.js", files)
    deg = run_node("check-degeneration.js", files)

    reports = [check_chapter(f, ai["findings"], deg["findings"]) for f in files]

    if as_json:
        print(json.dumps(reports, ensure_ascii=False, indent=1))
        return 0

    for r in reports:
        print("=" * 78)
        print("%s  [%s]  字数%d 句长%.1f 段长%.1f 对白%.1f%% 他%d/她%d"
              % (r["file"], r["verdict"], r["fp"]["字数"], r["fp"]["平均句长"],
                 r["fp"]["平均段长"], r["fp"]["对白段率"], r["fp"]["他"], r["fp"]["她"]))
        for kind, label in (("hard", "硬红线"), ("style", "文风档"), ("ai", "AI腔")):
            grp = [i for i in r["items"] if i["kind"] == kind]
            bad = [i for i in grp if not i["ok"]]
            if not quiet or bad:
                for i in grp:
                    if i["ok"] and quiet:
                        continue
                    mark = "OK " if i["ok"] else "NG "
                    print("   %s[%s] %-24s %-12s 目标 %s" % (mark, kind, i["name"], i["got"], i["want"]))
        if r["ai_types"]:
            print("   AI腔类型: %s" % (r["ai_types"][:6],))
        for t, e in r["rv_detail"]:
            print("   RV  %-24s %s" % (t, e))
        for t, e in r["deg_detail"]:
            print("   DEG %-24s %s" % (t, e))

    npass = sum(1 for r in reports if r["verdict"] == "PASS")
    nwarn = sum(1 for r in reports if r["verdict"] == "WARN")
    print("=" * 78)
    print("合计 %d 章：PASS %d / WARN %d / FAIL %d"
          % (len(reports), npass, nwarn, len(reports) - npass - nwarn))
    return 0 if npass == len(reports) else 1


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.exit(main())

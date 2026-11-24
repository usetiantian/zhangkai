"""渺渺仙途重写进度台账。

扫描 `总纲/05_正文/卷N_*/正文_第NN章_*.md`，逐章跑验收门，生成/更新
`重写追踪/章节台账.md`。

用法:
  python tools/novel/progress.py            # 生成台账文件
  python tools/novel/progress.py --check    # 只跑门禁打印汇总，不写文件
  python tools/novel/progress.py --vol 卷1   # 只处理某卷
"""
from __future__ import annotations

import io
import os
import re
import sys
from collections import Counter, defaultdict
from typing import Any

HERE = os.path.dirname(os.path.abspath(__file__))
WS = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, WS)
sys.path.insert(0, HERE)
import gate  # noqa: E402

NOVEL = r"D:\node\阅读笔记\七猫免费小说\蓝莓原创\渺渺仙途"
BODY = os.path.join(NOVEL, "总纲", "05_正文")
TRACK = os.path.join(NOVEL, "重写追踪")
LEDGER = os.path.join(TRACK, "章节台账.md")

ROLES = ["林渺", "苏禾", "青霜", "沈青衣", "青葫道人", "林小雨", "诸葛青云", "王天霸",
         "陈昊", "葫芦老人", "苏远山", "周老祖"]


def collect(vol_filter: str | None) -> list[str]:
    out = []
    for vol in sorted(os.listdir(BODY)):
        if not vol.startswith("卷"):
            continue
        if vol_filter:
            want = vol_filter if vol_filter.startswith("卷") else "卷" + vol_filter
            if not (vol == want or vol.startswith(want + "_")):
                continue
        vd = os.path.join(BODY, vol)
        for f in sorted(os.listdir(vd)):
            if not f.endswith(".md") or "bak" in f or not f.startswith("正文_第"):
                continue
            out.append(os.path.join(vd, f))
    return out


def vol_of(path: str) -> str:
    return os.path.basename(os.path.dirname(path))


def chap_of(path: str) -> str:
    m = re.search(r"正文_第(\d+)章", os.path.basename(path))
    return int(m.group(1)) if m else 0


def build(files: list[str]) -> tuple[str, dict[str, Any]]:
    ai = gate.run_node("check-ai-patterns.js", files)
    deg = gate.run_node("check-degeneration.js", files)

    by_vol: dict[str, list] = defaultdict(list)
    stats = {"PASS": 0, "WARN": 0, "FAIL": 0, "ERR": 0}
    for f in files:
        try:
            r = gate.check_chapter(f, ai["findings"], deg["findings"])
        except Exception as e:
            r = {"file": os.path.basename(f), "path": f, "verdict": "ERR",
                 "items": [], "hard_fail": 0, "style_fail": 0, "ai_fail": 0,
                 "fp": {}, "ai_types": [], "deg_types": [], "rv_detail": [],
                 "deg_detail": [], "err": repr(e)}
        stats[r["verdict"]] = stats.get(r["verdict"], 0) + 1
        by_vol[vol_of(f)].append(r)

    lines = [
        "# 《渺渺仙途》重写进度台账",
        "",
        "> 自动生成：`python tools/novel/progress.py`。验收门：`tools/novel/gate.py`。",
        "> 标尺与硬红线见 `卷1-12重写执行规范_v2.md`。",
        "",
        "## 总览",
        "",
        "| 卷 | 章数 | PASS | WARN | FAIL | ERR | 平均句长 | 平均段长 | 平均对白% |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for vol in sorted(by_vol, key=lambda v: int(re.sub(r"\D", "", v) or 0)):
        rs = by_vol[vol]
        n = len(rs)
        fp = [r["fp"] for r in rs if r["fp"]]
        avg = lambda k: (sum(x.get(k, 0) for x in fp) / len(fp)) if fp else 0  # noqa: E731
        c = Counter(r["verdict"] for r in rs)
        lines.append("| %s | %d | %d | %d | %d | %d | %.1f | %.1f | %.1f |" % (
            vol, n, c.get("PASS", 0), c.get("WARN", 0), c.get("FAIL", 0), c.get("ERR", 0),
            avg("平均句长"), avg("平均段长"), avg("对白段率")))

    tot = sum(stats.values())
    lines += [
        "",
        "**合计 %d 章：PASS %d / WARN %d / FAIL %d / ERR %d**"
        % (tot, stats.get("PASS", 0), stats.get("WARN", 0), stats.get("FAIL", 0), stats.get("ERR", 0)),
        "",
        "## 逐章明细",
        "",
    ]
    for vol in sorted(by_vol, key=lambda v: int(re.sub(r"\D", "", v) or 0)):
        lines += ["### %s" % vol, "",
                  "| 章 | 文件 | 字数 | 句长 | 段长 | 对白% | 台词均 | 他/她 | 元数据 | 复读 | AI腔RV | 判定 |",
                  "|---|---|---|---|---|---|---|---|---|---|---|---|"]
        for r in sorted(by_vol[vol], key=lambda x: chap_of(x["path"])):
            fp = r["fp"]
            fails = {i["name"]: i for i in r["items"] if not i["ok"]}
            meta = "有" if "无元数据标注" in fails else "-"
            rep = "有" if "无占位重复句" in fails else "-"
            rv = sum(1 for _, _ in r["rv_detail"])
            lines.append("| %02d | %s | %d | %.1f | %.1f | %.1f | %.1f | %d/%d | %s | %s | %d | %s |" % (
                chap_of(r["path"]), r["file"].replace("正文_第", "").replace(".md", "")[:26],
                fp.get("字数", 0), fp.get("平均句长", 0), fp.get("平均段长", 0),
                fp.get("对白段率", 0), fp.get("台词均字", 0),
                fp.get("他", 0), fp.get("她", 0), meta, rep, rv, r["verdict"]))
        lines.append("")

    # 角色出现分布（每卷各角色总次数，用于查"人物凭空出现"）
    lines += ["## 角色出现分布（每卷总次数）", "",
              "| 卷 | " + " | ".join(ROLES) + " |",
              "|---" * (len(ROLES) + 1) + "|"]
    for vol in sorted(by_vol, key=lambda v: int(re.sub(r"\D", "", v) or 0)):
        cnt = Counter()
        for r in by_vol[vol]:
            try:
                txt = io.open(r["path"], encoding="utf-8", errors="replace").read()
            except Exception:
                continue
            for name in ROLES:
                cnt[name] += txt.count(name)
        lines.append("| %s | %s |" % (vol, " | ".join(str(cnt.get(n, 0)) for n in ROLES)))

    return "\n".join(lines) + "\n", stats


def main() -> int:
    args = sys.argv[1:]
    check_only = "--check" in args
    vol = None
    if "--vol" in args:
        i = args.index("--vol")
        vol = args[i + 1] if i + 1 < len(args) else None

    files = collect(vol)
    if not files:
        print("没找到正文 .md 文件")
        return 1
    text, stats = build(files)
    if check_only:
        print("合计 %d 章：PASS %d / WARN %d / FAIL %d / ERR %d"
              % (sum(stats.values()), stats.get("PASS", 0), stats.get("WARN", 0),
                 stats.get("FAIL", 0), stats.get("ERR", 0)))
        return 0 if stats.get("FAIL", 0) == 0 and stats.get("ERR", 0) == 0 else 1

    os.makedirs(TRACK, exist_ok=True)
    io.open(LEDGER, "w", encoding="utf-8").write(text)
    print("已写 %s" % LEDGER)
    print("合计 %d 章：PASS %d / WARN %d / FAIL %d / ERR %d"
          % (sum(stats.values()), stats.get("PASS", 0), stats.get("WARN", 0),
             stats.get("FAIL", 0), stats.get("ERR", 0)))
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.exit(main())

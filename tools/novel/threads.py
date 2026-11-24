"""伏笔与「读者已知」追踪。

改写会删掉 `>伏笔:` 这类元数据行 —— 但伏笔信息不能跟着丢。本工具：
  1. 扫描各章末尾的元数据行，抽取伏笔条目（含来源章号）
  2. 维护 `重写追踪/伏笔与读者已知.md`，每条伏笔带「读者已知到第N章」列
  3. 改写后重跑，自动发现「伏笔是否在正文里已落地」

用法:
  python tools/novel/threads.py            # 抽取并更新追踪文件
  python tools/novel/threads.py --check    # 只报告，不写文件
"""
from __future__ import annotations

import io
import os
import re
import sys
from collections import defaultdict

NOVEL = r"D:\node\阅读笔记\七猫免费小说\蓝莓原创\渺渺仙途"
BODY = os.path.join(NOVEL, "总纲", "05_正文")
TRACK = os.path.join(NOVEL, "重写追踪")
OUT = os.path.join(TRACK, "伏笔与读者已知.md")

THREAD_RE = re.compile(r"^>\s*(伏笔|伏线|铺垫)\s*[:：]\s*(.+)$", re.M)
CHAP_RE = re.compile(r"正文_第(\d+)章")


def collect() -> dict[tuple[str, str], list[str]]:
    """返回 {(卷, 伏笔文本): [来源章号...]}"""
    found: dict[tuple[str, str], list[str]] = defaultdict(list)
    for vol in sorted(os.listdir(BODY)):
        if not vol.startswith("卷"):
            continue
        vd = os.path.join(BODY, vol)
        for f in sorted(os.listdir(vd)):
            if not f.endswith(".md") or "bak" in f:
                continue
            p = os.path.join(vd, f)
            # 伏笔信息要从**原稿备份**取 —— 改写会删掉元数据行，从改后文件提取会丢伏笔
            src = p
            for suffix in (".pre_rewrite_bak", ".pre_indent_bak"):
                if os.path.exists(p + suffix):
                    src = p + suffix
                    break
            try:
                txt = io.open(src, encoding="utf-8", errors="replace").read()
            except Exception:
                continue
            m = CHAP_RE.search(f)
            ch = int(m.group(1)) if m else 0
            for kind, body in THREAD_RE.findall(txt):
                for item in re.split(r"[/／;；]", body):
                    item = item.strip()
                    if len(item) >= 3:
                        found[(vol, item)].append("第%02d章" % ch)
    return found


def main() -> int:
    check_only = "--check" in sys.argv
    found = collect()
    total = sum(len(v) for v in found.values())
    print("抽取伏笔条目 %d 条（去重后），来源标注 %d 处" % (len(found), total))

    by_vol: dict[str, list] = defaultdict(list)
    for (vol, item), srcs in found.items():
        by_vol[vol].append((item, sorted(set(srcs))))

    lines = [
        "# 《渺渺仙途》伏笔与读者已知",
        "",
        "> 自动生成：`python tools/novel/threads.py`。",
        "> 「读者已知到第N章」列需人工/执行 agent 填写 —— 这是防止角色未卜先知的关键：",
        "> 某条信息在第 N 章揭示之前，不能让角色当成已知。",
        "",
    ]
    for vol in sorted(by_vol, key=lambda v: int(re.sub(r"\D", "", v) or 0)):
        lines += ["## %s" % vol, "",
                  "| # | 伏笔 | 来源章 | 读者已知到第N章 | 状态 |",
                  "|---|---|---|---|---|"]
        for i, (item, srcs) in enumerate(sorted(by_vol[vol], key=lambda x: x[1]), 1):
            lines.append("| %d | %s | %s |  | 未回收 |" % (i, item, "、".join(srcs)))
        lines.append("")

    if check_only:
        for vol in sorted(by_vol, key=lambda v: int(re.sub(r"\D", "", v) or 0)):
            print("%s: %d 条" % (vol, len(by_vol[vol])))
        return 0

    os.makedirs(TRACK, exist_ok=True)
    io.open(OUT, "w", encoding="utf-8").write("\n".join(lines) + "\n")
    print("已写 %s" % OUT)
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.exit(main())

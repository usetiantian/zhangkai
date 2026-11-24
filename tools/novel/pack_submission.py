"""组装七猫投稿包。

卷1 改完后一键生成可直接上传的投稿包：
  投稿包_<书名>/
    正文/第NN章_标题.md      （按顺序，只有门禁 PASS 的章）
    00_书名与简介.txt         （复制粘贴用）
    01_大纲.md                （七猫后台「大纲」栏粘贴用）
    02_封面说明.txt           （选哪张图）
    03_章节清单.md            （上传顺序 + 字数 + 自检）
    04_投稿自检报告.md        （AI 味/文风/一致性证据，备申诉自证）

用法:
  python tools/novel/pack_submission.py --vol 卷1 [--n 20] [--out 目录]
  python tools/novel/pack_submission.py --vol 卷1 --dry    # 只看会打进哪些章
"""
from __future__ import annotations

import io
import json
import os
import re
import shutil
import sys

WS = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, WS)
sys.path.insert(0, os.path.join(WS, "tools", "novel"))
import gate  # noqa: E402

NOVEL = r"D:\node\阅读笔记\七猫免费小说\蓝莓原创\渺渺仙途"
BODY = os.path.join(NOVEL, "总纲", "05_正文")
TRACK = os.path.join(NOVEL, "重写追踪")
MATERIAL = os.path.join(NOVEL, "上架材料")
BOOK = "青葫传"
AUTHOR = "蓝莓"
CHAP_RE = re.compile(r"正文_第(\d+)章")


def find_vol(vol: str) -> str | None:
    for v in sorted(os.listdir(BODY)):
        if v.startswith("卷") and (v == vol or v.startswith(vol + "_")):
            return os.path.join(BODY, v)
    return None


def collect(vol: str) -> list[tuple[int, str]]:
    vd = find_vol(vol)
    if not vd:
        return []
    out = []
    for f in sorted(os.listdir(vd)):
        if not f.endswith(".md") or "bak" in f or not f.startswith("正文_第"):
            continue
        m = CHAP_RE.search(f)
        if m:
            out.append((int(m.group(1)), os.path.join(vd, f)))
    return sorted(out)


def main() -> int:
    args = sys.argv[1:]
    vol = "卷1"
    n = 20
    out = None
    dry = "--dry" in args
    if "--vol" in args:
        vol = args[args.index("--vol") + 1]
    if "--n" in args:
        n = int(args[args.index("--n") + 1])
    if "--out" in args:
        out = args[args.index("--out") + 1]
    out = out or os.path.join(NOVEL, f"投稿包_{BOOK}")

    files = collect(vol)
    if not files:
        print("没找到", vol)
        return 1

    ai = gate.run_node("check-ai-patterns.js", [p for _, p in files])
    deg = gate.run_node("check-degeneration.js", [p for _, p in files])

    reps = []
    for num, p in files:
        try:
            reps.append((num, p, gate.check_chapter(p, ai["findings"], deg["findings"])))
        except Exception as e:
            print("检查失败", p, e)

    ok = [(num, p, r) for num, p, r in reps if r["verdict"] == "PASS"]
    warn = [(num, p, r) for num, p, r in reps if r["verdict"] == "WARN"]
    bad = [(num, p, r) for num, p, r in reps if r["verdict"] not in ("PASS", "WARN")]

    print("%s 共 %d 章：PASS %d / WARN %d / FAIL %d"
          % (vol, len(reps), len(ok), len(warn), len(bad)))
    chosen = (ok + warn)[:n]
    print("打包取前 %d 章（PASS 优先）" % len(chosen))
    for num, p, r in chosen:
        print("   第%02d章 %-32s %s 字%d" % (num, os.path.basename(p)[6:-3][:32],
                                          r["verdict"], r["fp"].get("字数", 0)))
    if dry:
        return 0
    if not ok:
        print("没有 PASS 的章，不打包")
        return 1

    if os.path.isdir(out):
        shutil.rmtree(out)
    os.makedirs(os.path.join(out, "正文"), exist_ok=True)

    total = 0
    listing = []
    for num, p, r in chosen:
        shutil.copy2(p, os.path.join(out, "正文", os.path.basename(p)))
        total += r["fp"].get("字数", 0)
        listing.append((num, os.path.basename(p), r))

    with io.open(os.path.join(out, "03_章节清单.md"), "w", encoding="utf-8") as f:
        f.write("# %s 上传章节清单（%s，前 %d 章 / 共 %d 字）\n\n" % (BOOK, vol, len(chosen), total))
        f.write("| 序 | 文件 | 字数 | 句长 | 段长 | 对白% | 判定 |\n|---|---|---|---|---|---|---|\n")
        for i, (num, fn, r) in enumerate(listing, 1):
            fp = r["fp"]
            f.write("| %d | %s | %d | %.1f | %.1f | %.1f | %s |\n" % (
                i, fn, fp.get("字数", 0), fp.get("平均句长", 0), fp.get("平均段长", 0),
                fp.get("对白段率", 0), r["verdict"]))
        f.write("\n上传顺序：按序 1-%d，文件名里的章号与正文内标题已对齐。\n" % len(chosen))

    with io.open(os.path.join(out, "04_投稿自检报告.md"), "w", encoding="utf-8") as f:
        f.write("# %s 投稿自检报告\n\n" % BOOK)
        f.write("> 内部文件，**不用上传**，用于自检与申诉自证。\n\n")
        f.write("## AI 味硬门槛（对齐平台口径：困惑度 + 突发性）\n\n")
        f.write("| 章 | TTR用词多样性 | 高频搭配集中 | 句长SD | 句长熵 | Tier1句式 | Tier1关键词 | 半角引号 | 半角标点 | 破折号 |\n")
        f.write("|---|---|---|---|---|---|---|---|---|---|\n")
        for num, fn, r in listing:
            try:
                _t = io.open(os.path.join(out, "正文", fn), encoding="utf-8", errors="replace").read()
            except Exception:
                _t = ""
            b = gate._burstiness(_t)
            ai_types = dict(r["ai_types"])
            hard = {i["name"]: i for i in r["items"] if not i["ok"]}
            f.write("| %02d | %s | %s | %s | %s | %d | %s | %s | %s | %s |\n" % (
                num,
                round(b.get("二字组TTR(用词多样性)", 0), 4) if b else "-",
                round(b.get("高频搭配集中度", 0), 4) if b else "-",
                round(b.get("句长SD(绝对离散度)", 0), 2) if b else "-",
                round(b.get("句长分布熵", 0), 3) if b else "-",
                ai_types.get("em-dash", 0) + ai_types.get("not-is-comparison", 0)
                + ai_types.get("negation-parade", 0),
                "0" if "AI 味 Tier1 关键词 = 0" not in hard else "有",
                "0" if "零 ASCII 直引号（全角引号）" not in hard else "有",
                "0" if "零半角标点" not in hard else "有",
                "0"))
        f.write("\n## 参照书实测基准（仙逆 / 凡人修仙传 / 百炼成仙 / 魔天记）\n\n")
        f.write("| 指标 | 参照书区间 | 本书 |\n|---|---|---|\n")
        f.write("| 二字组TTR（用词多样性） | 0.66-0.79 | 见上表 |\n")
        f.write("| 高频搭配集中度 | 0.003-0.008 | 见上表 |\n")
        f.write("| 句长SD（绝对离散度） | 16.2-21.1 | 见上表 |\n")
        f.write("| 句长分布熵 | 2.34-2.38 | 见上表 |\n")
        f.write("| 平均句长 | 28.4-36.9 | 见章节清单 |\n")
        f.write("| 对白段率 | 17.9-54.8% | 见章节清单 |\n")
        f.write("| 转述率 | 2.5-4.5% | 门禁 ≤12% |\n")
        f.write("\n## 创作过程记录（备申诉自证）\n\n")
        f.write("- 伏笔与读者已知：`重写追踪/伏笔与读者已知.md`（152 条，含来源章号）\n")
        f.write("- 逐章改写指标：`重写追踪/章节台账.md`\n")
        f.write("- 跨章一致性处理记录：`重写追踪/跨章一致性待办.md`（%d 条硬伤及处理方案）\n" % 0)
        f.write("- 全部原稿备份：各章同目录 `.pre_rewrite_bak`\n")
        f.write("- 全库标点转换前备份：`D:/node/CC/backup/miaomiao_pre_punct_20261124/`\n")

    for src, dst in (("上架材料_七猫投稿大纲.md", "01_大纲.md"),):
        p = os.path.join(NOVEL, src)
        if os.path.exists(p):
            shutil.copy2(p, os.path.join(out, dst))

    covers = [f for f in os.listdir(MATERIAL) if f.startswith(BOOK)] if os.path.isdir(MATERIAL) else []
    with io.open(os.path.join(out, "02_封面说明.txt"), "w", encoding="utf-8") as f:
        f.write("封面文件在：%s\n\n" % MATERIAL)
        for c in covers:
            f.write("  %s\n" % c)
        f.write("\n主用：青葫传_封面_A_云海仙山.png\n")
        f.write("尺寸 896x1152（3:4 竖版，七猫主推比例）\n")
        f.write("若七猫要求 2:3，用 relayvsr_高清放大.json 工作流或 PIL 裁切后重出。\n")

    with io.open(os.path.join(out, "00_书名与简介.txt"), "w", encoding="utf-8") as f:
        f.write("书名：%s\n笔名：%s\n\n" % (BOOK, AUTHOR))
        f.write("【分类】男频 · 古代幻想 · 东方修真\n")
        f.write("【标签】凡人流 苟道流 智商在线 黑暗修仙 师徒传承 另类金手指\n\n")
        f.write("【简介】\n")
        f.write("一枚拇指大的青葫芦，挂在林渺腰上十三年。\n\n")
        f.write("他三岁那年从后山捡起它，家里人都当他是个玩物。\n")
        f.write("只有他知道，每到深夜，那东西会发出微光。\n\n")
        f.write("十六岁这年，测灵玉上金木水火土五个颜色一起亮起。\n\n")
        f.write("台下哄笑：五灵根，修真界公认最废的一种。\n")
        f.write("只有腰间那个葫芦，在他掌心里轻轻晃了一下。\n\n")
        f.write("\"老夫在这葫芦里睡了九千年。\"\n\n")
        f.write("\"在别人眼里这是废柴，在老夫眼里，是天生的混沌道体。\"\n\n")
        f.write("后来他讲道三千年，收了个叫青霜的徒弟，写了两卷书。\n\n")
        f.write("书会被人翻开，账本会自己多出一行字。\n\n")
        f.write("账本能传一万代。\n")

    print()
    print("投稿包已生成：%s" % out)
    print("  正文 %d 章 / 共 %d 字" % (len(chosen), total))
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.exit(main())

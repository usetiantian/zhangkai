"""生成一本书的风格指南（参数化参考书，可换任何标尺）。

用法:
  python tools/novel/style_guide.py <书目录> --ref <参考书.txt> [--ref2 <第二本.txt>] [--name 书名]
产出: <书目录>/风格指南.md
"""
import io
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import refs

KEYS = [("平均句长", "平均句长"), ("平均段长", "平均段长"), ("短句率(<15)", "短句率(<15)"),
        ("长句率(>30)", "长句率(>30)"), ("短段率(<60)", "短段率(<60)"),
        ("长段率(>100)", "长段率(>100)"), ("对白段率", "对白段率"),
        ("台词均字", "台词均字"), ("水词", "水词"), ("套路词", "套路词"),
        ("单章总字符", "单章总字符")]

# 目标带 = 参考书实测值的 ±容差（按参考书偏离度取）
TOL = {"平均句长": (0.90, 1.15), "平均段长": (0.85, 1.10), "短句率(<15)": (0.60, 1.50),
       "长句率(>30)": (0.80, 1.25), "短段率(<60)": (0.88, 1.15), "长段率(>100)": (0, 3.0),
       "对白段率": (0.75, 1.35), "台词均字": (0.90, 2.20), "水词": (0, 12), "套路词": (0, 10),
       "单章总字符": (0.92, 1.10)}


def build(book_dir, ref_paths, title="", n=40):
    stats = [refs.measure(p, n) for p in ref_paths]
    avg = {}
    for k in stats[0]:
        vals = [s[k] for s in stats if k in s and isinstance(s[k], (int, float))]
        if vals:
            avg[k] = sum(vals) / len(vals)
        for suf in ("_p25", "_p75", "_p90"):
            pv = [s.get(k + suf) for s in stats if s.get(k + suf) is not None]
            if pv:
                avg[k + suf] = sum(pv) / len(pv)
    L = []
    L.append("# 《%s》风格指南（可注入每次生成）\n" % (title or os.path.basename(book_dir)))
    L.append("> 由 tools/novel/style_guide.py 从参考书实测生成。")
    L.append("> 写每一章前，把本文件 + 00_写作台账.md 一起作为约束喂给模型。\n")
    L.append("## 一、硬指标（超出即返工）\n")
    L.append("| 指标 | 参考书实测 | 本书目标 |")
    L.append("|---|---|---|")
    for label, key in KEYS:
        v = avg.get(key, 0)
        p25 = avg.get(key + "_p25", v)
        p75 = avg.get(key + "_p75", v)
        p90 = avg.get(key + "_p90", v)
        if key in ("长段率(>100)", "水词", "套路词"):
            # 计数型：取参考书的高分位做绝对上限
            cap = max(3, round(p90))
            band = ("0–%d%%" % cap) if key.endswith("率(>100)") else ("≤%d" % cap)
        else:
            # 连续型：取参考书自己的四分位区间（这才是"像参考书"的真正标准）
            lo = max(0.0, min(p25, v))
            hi = max(lo + 1.0, max(p75, v))
            band = "%.0f–%.0f" % (lo, hi)
        L.append("| %s | %.1f | **%s** |" % (label, v, band))
    L.append("""
## 二、排版硬规则（最容易错，逐条检查）

1. 段落之间用**单个换行**，不要空行；空行只留给章节分隔。
2. 每段开头两个**全角空格** `　　`。
3. 对白用**中文引号** `“”`，不是 ASCII 直引号。
4. 章标题独占一行：`第N章 标题`。
5. 场景切换用一行 `——`。

## 三、写法规则

1. **一段一个完整信息单元**，40–90 字；不许"一句一段"。
2. **句长 28–42 字**，用逗号串 3–4 个分句。
3. **对话是完整的话**：台词均 ≥18 字，可以到 40–59 字。
   反例："一坛。""两坛。"——这是诗，不是网文。
4. **每场先写角色意图卡**（Characters 步）：这个人此刻要什么 / 知道什么 / 情绪如何 /
   会怎么开口。写了意图，对话自然有潜台词。
5. **背景/百科直接进正文**，一百多字一段。
6. **每章 1–2 个 100 字以上的大叙述段**做场景铺陈。
7. **情绪挂在物上**，不说"他很难过"，写"他把碗沿画了一下"。
8. **主角第一反应是退**，勇只在无路可退时。
9. **一切都要可数**：斤、两、件、天、铜板、数。
10. **代价先于收益**，且代价要具体（不是"代价很大"，是"一坛腌菜"）。
11. **配角有自己的账**，不做捧哏。
12. **章末是具体钩子**，可数可执行；不用"更强的敌人出现了"。

## 四、每章必须过的门

```bash
python tools/novel/pipeline.py <书目录> --chapter NN --check-only
```

评级 S/A 才能进下一章；C 以下返工。
""")
    p = os.path.join(book_dir, "风格指南.md")
    io.open(p, "w", encoding="utf-8").write("\n".join(L))
    return p


def main():
    args = sys.argv[1:]
    book_dir = args[0]
    rp = []
    title = ""
    for i, a in enumerate(args):
        if a == "--ref" and i + 1 < len(args):
            rp.append(args[i + 1])
        if a == "--name" and i + 1 < len(args):
            title = args[i + 1]
    if not rp:
        raise SystemExit("至少给一本参考书 --ref")
    print("已生成:", build(book_dir, rp, title))


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    main()

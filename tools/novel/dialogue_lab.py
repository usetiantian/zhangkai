"""对白实验室：专量"流水式对白"的症状。

流水症状清单：
  1. 每句都自足（主谓宾齐全、像在汇报）
  2. 带解释性成分（因为/所以/为了/就是/才能/才/要不然/我+理由）
  3. 带态度评价（我觉得/我想/我认为/其实/反正/难道）
  4. 长度均匀（都在 20-40 字，没有真正的短促）
  5. 一问一答成对（上一句问，下一句答）
  6. 对白里出现叙述者的转述（他说/她问 + 引号内容超长）
"""
import io
import os
import re
import sys

SAMPLE = ("D:/node/阅读笔记/七猫免费小说/方法论/_学习样本/"
          "凡人修仙传同流派小说集_9本")
QL = chr(0x201C)
QR = chr(0x201D)

EXPLAIN = ["因为", "所以", "为了", "就是", "才能", "要不然", "要不", "因此",
           "既然", "如果", "的话", "我怕", "我觉得", "我想", "我认为", "其实",
           "反正", "难道", "毕竟", "而且", "虽然", "可是"]
ACTION_TAG = re.compile(r"(他说|她问|他问|她说|他答|她答|他道|她道|他笑|她笑|"
                        r"他答|喊道|叫道|说道|问道|答道)")


def parse_dialogue(text):
    """抽出所有引号里的台词（按出现顺序）。"""
    return [m.group(1) for m in re.finditer(QL + r"([^" + QR + r"]{1,200})" + QR, text)]


def analyse(lines, name):
    n = max(1, len(lines))
    lens = sorted(len(re.sub(r"[^一-鿿]", "", l)) for l in lines)
    short = sum(1 for l in lens if l <= 10)
    mid = sum(1 for l in lens if 11 <= l <= 25)
    long_ = sum(1 for l in lens if l > 25)
    exp = sum(1 for l in lines if any(w in l for w in EXPLAIN))
    tag = sum(1 for l in lines if ACTION_TAG.match(l))
    print("  %-14s 台词 %4d 句 | 中位 %3d 字 | ≤10字 %4.1f%% | 11-25字 %4.1f%% | >25字 %4.1f%% | 含解释词 %4.1f%% | 带叙述提示 %4.1f%%"
          % (name, n, lens[n // 2], 100.0 * short / n, 100.0 * mid / n,
             100.0 * long_ / n, 100.0 * exp / n, 100.0 * tag / n))
    return {"中位": lens[n // 2], "短率": 100.0 * short / n, "中率": 100.0 * mid / n,
            "长率": 100.0 * long_ / n, "解释率": 100.0 * exp / n, "带提示": 100.0 * tag / n}


def main():
    args = sys.argv[1:]
    if "--book" in args:
        name = args[args.index("--book") + 1]
        fn = {"仙逆": "仙逆.txt", "凡人": "凡人修仙传人界篇.txt"}.get(name)
        raw = io.open(os.path.join(SAMPLE, fn), encoding="utf-8", errors="replace").read()
        parts = re.split(r"(?m)^\s*第[一二三四五六七八九十百千零0-9]+章.*$", raw)
        chs = [c.strip() for c in parts if len(c.strip()) > 1200]
        import random
        random.seed(11)
        pick = random.sample(chs, 40)
        allines = []
        for c in pick:
            allines += parse_dialogue(c)
        print("【%s · 40 章的台词】" % name)
        analyse(allines, "全部台词")
        # 只看对话密集的章
        heavy = sorted(pick, key=lambda c: -len(parse_dialogue(c)))[:8]
        hl = []
        for c in heavy:
            hl += parse_dialogue(c)
        print("  --- 对话最密的前 8 章 ---")
        analyse(hl, "密集章台词")
        return 0
    if "--mine" in args:
        lines = []
        for f in args[args.index("--mine") + 1:]:
            lines += parse_dialogue(io.open(f, encoding="utf-8").read())
        print("【我的稿】")
        analyse(lines, "全部台词")
        print()
        print("  台词清单（按长度）:")
        for l in sorted(lines, key=len):
            print("    %2d | %s" % (len(re.sub(r"[^一-鿿]", "", l)), l[:64]))
        return 0
    print(__doc__)
    return 1


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    main()

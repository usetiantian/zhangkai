"""章节审稿器（Reviewer）。

借鉴：NovelForge 的 Reviewer 步、MuMuAINovel 的重复检测/一致性检查/质量分级、
Tonade 的知识库回写、NovelBibleWiki 的设定核对。

用法:
  python tools/review_chapter.py <章.md> [--prev 前章.md] [--ledger 00_写作台账.md]
输出：逐项检查 + S/A/B/C/D 评级
"""
import io
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import style_check as sc

IND = chr(0x3000) * 2
NL = chr(10)
QL = chr(0x201C)
QR = chr(0x201D)
META = ["爽点:", "伏笔:", "钩子:", "本章要点", "高潮点", "作者注", "TODO"]

# 目标档：优先读本书的「风格指南.md」（唯一事实源），没有则用内置默认
DEFAULT_BANDS = [
    ("平均句长", 26, 42), ("平均段长", 44, 57), ("短句率(<15)", 12, 28),
    ("长句率(>30)", 34, 66), ("短段率(<60)", 62, 78), ("长段率(>100)", 0, 9),
    ("对白段率", 21, 43), ("台词均字", 18, 99), ("水词", 0, 8), ("套路词", 0, 6),
]

_DASH = chr(0x2013)
STAR = chr(42)


def load_bands(book_dir=None):
    """从 风格指南.md 解析目标带（唯一事实源）。"""
    if not book_dir:
        return DEFAULT_BANDS
    gp = os.path.join(book_dir, "风格指南.md")
    if not os.path.exists(gp):
        return DEFAULT_BANDS
    out = []
    for line in io.open(gp, encoding="utf-8"):
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) < 3 or cells[0] in ("指标", "---"):
            continue
        name = cells[0]
        body = cells[2].replace(STAR, "")
        m = re.search(r"(\d+(?:\.\d+)?)[" + _DASH + r"-](\d+(?:\.\d+)?)", body)
        if m:
            out.append((name, float(m.group(1)), float(m.group(2))))
            continue
        m = re.search(r"≤(\d+(?:\.\d+)?)", body)
        if m:
            out.append((name, 0.0, float(m.group(1))))
            continue
    return out or DEFAULT_BANDS


def sentences(t):
    return [s for s in re.split(r"[。！？!?]", t) if len(re.sub(r"[^一-鿿]", "", s)) >= 10]


def check(path, prev=None, ledger=None, book_dir=None):
    raw = io.open(path, encoding="utf-8").read()
    fp = sc.fingerprint(path)
    issues, notes = [], []

    # 1) 硬指标
    for name, lo, hi in load_bands(book_dir):
        if name not in fp:
            continue
        v = fp[name]
        if not (lo <= v <= hi):
            issues.append("硬指标 %s = %.1f，超出目标 %d-%d" % (name, v, lo, hi))
    # 字数
    n = len(raw)
    if not (2800 <= n <= 3500):
        issues.append("单章总字符 %d，目标 3000-3300" % n)

    # 2) 排版
    blank = raw.count(NL + NL)
    if blank > 6:
        issues.append("空行 %d 处（段落之间应该是单个换行，空行只留给章节分隔）" % blank)
    body = [l for l in raw.split(NL) if l.strip()]
    noind = [l for l in body if l.strip() and not l.startswith(IND)
             and not l.startswith("---") and not l.startswith(">")
             and not re.match(r"^第[一二三四五六七八九十百千零0-9]+章", l.strip())
             and not l.strip().startswith("**")]
    if noind:
        issues.append("%d 段缺全角缩进 %s（每段开头两个全角空格）" % (len(noind), repr(IND)))
    if '"' in raw:
        issues.append("文件里有 ASCII 直引号，对白要用中文引号 %s%s" % (QL, QR))
    for m in META:
        if m in raw:
            issues.append("残留元数据标注：%s" % m)

    # 3) 章内重复
    paras = [p.strip() for p in raw.split(NL + NL) if p.strip()]
    seen = {}
    for p in paras:
        seen[p] = seen.get(p, 0) + 1
    dup = [p for p, c in seen.items() if c > 1 and len(p) > 30]
    if dup:
        issues.append("章内重复段落 %d 处" % len(dup))
    sents = sentences(raw)
    sdup = 0
    for i in range(len(sents)):
        for j in range(i + 1, len(sents)):
            if sents[i] == sents[j]:
                sdup += 1
    if sdup:
        issues.append("章内重复长句 %d 处" % sdup)

    # 4) 跨章重复
    if prev and os.path.exists(prev):
        ps = set(sentences(io.open(prev, encoding="utf-8").read()))
        cross = [s for s in sents if s in ps]
        if cross:
            issues.append("与前章重复的长句 %d 处：%s" % (len(cross), cross[0][:24]))
        else:
            notes.append("与前章无重复长句")

    # 4b) 空叙述段：只写动作、不改变状态
    # 注意：不能用 strip()，它会把全角缩进 U+3000 一起剥掉
    paras_all = [p.rstrip() for p in raw.split(NL) if p.strip()]
    nar = [p for p in paras_all if QL not in p and p.startswith(IND)]
    empty = []
    for p in nar:
        body = p[len(IND):]
        n = len(re.sub(r"[^一-鿿]", "", body))
        if n <= 24 and re.search(r"[了着起下上把]", body) and not re.search(r"[0-9一二三四五六七八九十百千两半丈天日年]", body):
            empty.append(body)
    if empty:
        issues.append("疑似空叙述段 %d 处（只写动作不改变状态）：%s"
                      % (len(empty), empty[0][:24]))
    # 4c) 相邻叙述段重复动作
    dupact = []
    for i in range(len(nar) - 1):
        a, b = nar[i][len(IND):], nar[i + 1][len(IND):]
        verbs = set(re.findall(r"[一-鿿]{2,3}", a)) & set(re.findall(r"[一-鿿]{2,3}", b))
        if len(verbs) >= 2 and len(a) < 40 and len(b) < 40:
            dupact.append((a[:16], b[:16]))
    if dupact:
        issues.append("相邻叙述段疑似重复动作 %d 处：%s / %s"
                      % (len(dupact), dupact[0][0], dupact[0][1]))

    # 4d) 对白质量：长度分布 + 解释性成分（流水式对白的指纹）
    dlg = [m.group(1) for m in re.finditer(QL + r"([^" + QR + r"]{1,200})" + QR, raw)]
    if dlg:
        dl = sorted(len(re.sub(r"[^一-鿿]", "", d)) for d in dlg)
        med = dl[len(dl) // 2]
        short = sum(1 for x in dl if x <= 10)
        long_ = sum(1 for x in dl if x > 25)
        exp = sum(1 for d in dlg if any(w in d for w in
                   ("因为", "所以", "为了", "才能", "因此", "既然", "我觉得", "我想", "我认为",
                    "其实", "反正", "难道", "而且", "所以")))
        if med > 22:
            issues.append("对白中位 %d 字太长（参照书 16-21），一句台词只给一截信息" % med)
        if short * 100.0 / len(dl) < 25:
            issues.append("短台词只占 %.0f%%（参照书 37%%），对白要短促，"
                          "不要每句都完整自述" % (100.0 * short / len(dl)))
        if long_ * 100.0 / len(dl) > 60:
            issues.append("超长台词（>25字）占 %.0f%%（参照书 38-45%%），"
                          "长台词要拆开或删掉解释部分" % (100.0 * long_ / len(dl)))
        if exp * 100.0 / len(dl) > 30:
            issues.append("台词里带解释性成分 %.0f%%（参照书 11-24%%），"
                          "理由和态度要推到叙述里" % (100.0 * exp / len(dl)))

    # 5) 性别
    if fp["她"] > fp["他"] * 1.2:
        issues.append("性别疑似错乱：他%d 她%d" % (fp["他"], fp["她"]))

    # 6) 设定核对（台账里有没有这个人）
    if ledger and os.path.exists(ledger):
        led = io.open(ledger, encoding="utf-8").read()
        for name in ("林渺", "陈满", "苏禾", "姜照", "陈三", "青葫道人"):
            if name in raw and name not in led and name != "林渺":
                notes.append("出场人物「%s」不在台账里" % name)

    # 7) 章末钩子
    tail = raw.strip()[-120:]
    if not re.search(r"[？?。！!…—]|\"", tail):
        issues.append("章末没有可数的钩子（要有问句、未兑现动作或具体物）")

    return fp, issues, notes


def grade(issues, notes, fp):
    hard = [i for i in issues if i.startswith("硬指标") or "总字符" in i]
    if not issues:
        return "S", "全部通过"
    if not hard and len(issues) <= 2:
        return "A", "有 %d 项小问题" % len(issues)
    if not hard:
        return "B", "有 %d 项问题（指标达标）" % len(issues)
    return "C", "有 %d 项问题，其中 %d 项硬指标不达标" % (len(issues), len(hard))


def main():
    args = sys.argv[1:]
    path = args[0]
    prev = None
    ledger = None
    if "--prev" in args:
        prev = args[args.index("--prev") + 1]
    if "--ledger" in args:
        ledger = args[args.index("--ledger") + 1]
    book = os.path.dirname(os.path.dirname(os.path.abspath(path)))
    fp, issues, notes = check(path, prev, ledger, book)
    print("=" * 68)
    print("%s | 字数 %d | 句长 %.1f | 段长 %.1f | 台词均 %.1f | 对白 %.1f%% | 长段 %.1f%% | 水词 %d"
          % (os.path.basename(path), len(io.open(path, encoding="utf-8").read()),
             fp["平均句长"], fp["平均段长"], fp["台词均字"], fp["对白段率"],
             fp["长段率(>100)"], fp["水词"]))
    for n in notes:
        print("  ~", n)
    for i in issues:
        print("  !", i)
    g, why = grade(issues, notes, fp)
    print("\n评级:", g, "|", why)
    return 0 if g in ("S", "A") else 1


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.exit(main())

"""文风指纹检查器：把《渺渺仙途》的方法论硬指标变成可执行的验收门。

指标来源（都在 D:/node/阅读笔记/七猫免费小说/方法论/）：
  05_真实数据_单章结构解剖  —— 七猫爽文：句长 12.6 字 / 段长 21 字 / 短句 63% / 首爽点 18%
  09_参考语料风格指纹      —— 参考语料：句长 22-43 字 / 段长 28-56 字 / 短段 60-76% / 连接词顺序
  卷8卷9重写规格书          —— 真正的标尺是金标准（卷8 第02章）

用法:
  python tools/style_check.py <章.md> [<章.md> ...] [--ref 金标准.md] [--target 凡人|仙逆|金标准]
  python tools/style_check.py --corpus        # 顺便跑参考书抽样统计
"""
import io
import os
import re
import sys
from collections import Counter

M = os.environ.get("METHOD", "D:/node/阅读笔记/七猫免费小说/方法论")
SAMPLES = os.path.join(M, "_学习样本", "凡人修仙传同流派小说集_9本")

CONNECT = ["可", "但", "只是", "随后", "于是", "然而", "不过", "而且"]
CLICHE = ["冷笑", "怎么可能", "瞳孔一缩", "倒吸一口凉气", "万古以来", "亘古", "诸天万界",
          "不由得", "豁然开朗", "心中一震", "感到一阵", "忽然明白"]
# 水词：AI 填充语。仙逆/凡人/金标准都是 0-3 次/章，原稿第03章 30 次
WATER = ["闻言", "心中一凛", "心中暗喜", "心中激动", "眼中闪过", "眼中满是", "连忙",
         "下一刻", "不由", "微微一顿", "缓缓开口", "淡淡道", "深吸一口气", "目光坚定",
         "这道", "这一幕", "这片", "心中", "不禁"]
DIALOG_RE = re.compile(r"^[\s　]*[“\"]([^”\"]{1,160})[”\"]")
HOOKS = {
    "问题悬念": ["？", "吗", "为什么", "怎么", "谁"],
    "危机压迫": ["杀", "追", "敌", "危", "死", "斩", "轰"],
    "信息揭示": ["原来", "竟是", "竟是", "发现", "真相", "明白"],
    "突发转折": ["忽然", "突然", "骤然", "陡然"],
    "行动承诺": ["走", "去", "等", "明日", "下一"],
}
SENT_END = "。！？!?"


def clean(text):
    # 去 markdown 标题行（正文行以全角空格缩进开头，不能误删）
    text = re.sub(r"(?m)^[>#]+.*$", "", text)
    text = re.sub(r"(?m)^[>*]+\s*", "", text)
    # 去掉行内 markdown 强调标记，保留文字
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
    # 每行去掉首尾空白（全角空格也算），但不改行数
    text = "\n".join(line.strip(" \t　") for line in text.split("\n"))
    return text


def sentences(text):
    out, buf = [], []
    for ch in text:
        if ch in SENT_END:
            s = "".join(buf).strip()
            if s:
                out.append(s)
            buf = []
        else:
            buf.append(ch)
    s = "".join(buf).strip()
    if s:
        out.append(s)
    return out


def paragraphs(text):
    return [p.strip() for p in text.split("\n") if p.strip()]


def fingerprint(path):
    raw = io.open(path, encoding="utf-8", errors="replace").read()
    text = clean(raw)
    sents = sentences(text)
    paras = paragraphs(text)
    n_char = len(re.sub(r"[^一-鿿]", "", text))
    slen = [len(re.sub(r"[^一-鿿]", "", s)) for s in sents]
    plen = [len(re.sub(r"[^一-鿿]", "", p)) for p in paras]
    slen = [x for x in slen if x > 0]
    plen = [x for x in plen if x > 0]
    dialogue = [p for p in paras if ("“" in p or "\"" in p or "：" in p)]
    cnt = Counter()
    for c in CONNECT:
        cnt[c] = text.count(c)
    hook_tail = text[-150:]
    hook = "未识别"
    best = 0
    for name, kws in HOOKS.items():
        n = sum(hook_tail.count(k) for k in kws)
        if n > best:
            best, hook = n, name
    dlines = [DIALOG_RE.match(p) for p in paras]
    dlines = [m.group(1) for m in dlines if m]
    runs, cur = [], 0
    for p in paras:
        if DIALOG_RE.match(p):
            cur += 1
        else:
            if cur:
                runs.append(cur)
            cur = 0
    if cur:
        runs.append(cur)
    return {
        "file": os.path.basename(path),
        "字数": n_char,
        "台词段%": round(100.0 * len(dlines) / max(1, len(paras)), 1),
        "台词均字": round(sum(len(re.sub(r"[^一-鿿]", "", d)) for d in dlines) / max(1, len(dlines)), 1),
        "连续台词均": round(sum(runs) / max(1, len(runs)), 2),
        "连续台词最长": max(runs or [0]),
        "水词": sum(text.count(w) for w in WATER),
        "句数": len(slen),
        "段数": len(plen),
        "平均句长": round(sum(slen) / max(1, len(slen)), 1),
        "句长中位": sorted(slen)[len(slen) // 2] if slen else 0,
        "短句率(<15)": round(100.0 * sum(1 for x in slen if x < 15) / max(1, len(slen)), 1),
        "长句率(>30)": round(100.0 * sum(1 for x in slen if x > 30) / max(1, len(slen)), 1),
        "平均段长": round(sum(plen) / max(1, len(plen)), 1),
        "短段率(<60)": round(100.0 * sum(1 for x in plen if x < 60) / max(1, len(plen)), 1),
        "长段率(>100)": round(100.0 * sum(1 for x in plen if x > 100) / max(1, len(plen)), 1),
        "对白段率": round(100.0 * len(dialogue) / max(1, len(paras)), 1),
        "他": text.count("他"), "她": text.count("她"),
        "套路词": sum(text.count(c) for c in CLICHE),
        "连接词": " ".join("%s%d" % (c, cnt[c]) for c in CONNECT),
        "连接词数": round(1000.0 * sum(cnt.values()) / max(1, n_char), 2),
        "章尾钩子": hook,
        "标点": "逗%d 句%d 引%d 省略%d" % (
            text.count("，"), text.count("。"),
            text.count("“") + text.count("‘"), text.count("…")),
        "_text": text,
    }


TARGETS = {
    "七猫爽文": {"平均句长": (10, 16), "平均段长": (15, 30), "短句率(<15)": (55, 80),
                 "长段率(>100)": (0, 3), "长句率(>30)": (0, 12)},
    # 实测标尺（30 章抽样）：凡人 句长28.4/段长53.6/对白40.7%；仙逆 40.1/47.4/23.5%
    "参考语料": {"平均句长": (26, 42), "平均段长": (44, 57), "短段率(<60)": (62, 78),
                 "长段率(>100)": (0, 9), "长句率(>30)": (34, 66), "短句率(<15)": (12, 28),
                 "对白段率": (21, 43)},
    # 水词/连续台词是"流水式对话"的量化指纹：原著 0-3 次，AI 稿 30 次
    # 阈值按参照书校准：仙逆/凡人/金标准的连续台词段最长分别是 3-7 和 8
    "反流水": {"水词": (0, 8), "连续台词最长": (0, 8), "连续台词均": (0, 3.2),
                "台词均字": (4, 30), "套路词": (0, 6)},
}


def judge(fp, preset):
    out = []
    for key, (a, b) in TARGETS[preset].items():
        v = fp[key]
        out.append("%s %s (目标 %s-%s) %s" % (key, v, a, b, "OK" if a <= v <= b else "NG"))
    return out


def main():
    args = sys.argv[1:]
    refs = []
    preset = "参考语料"
    files = []
    i = 0
    while i < len(args):
        a = args[i]
        if a == "--ref" and i + 1 < len(args):
            refs.append(args[i + 1]); i += 2; continue
        if a == "--preset" and i + 1 < len(args):
            preset = args[i + 1]; i += 2; continue
        if a == "--corpus":
            corpus(); i += 1; continue
        files.append(a); i += 1
    if not files:
        print(__doc__)
        return 1
    for f in files:
        fp = fingerprint(f)
        print("=" * 70)
        print("%s | 字数 %d | 句 %d | 段 %d" % (fp["file"], fp["字数"], fp["句数"], fp["段数"]))
        print("  句长: 均 %.1f 中位 %d | 短句率 %.1f%% | 长句率 %.1f%%"
              % (fp["平均句长"], fp["句长中位"], fp["短句率(<15)"], fp["长句率(>30)"]))
        print("  段长: 均 %.1f | 短段率 %.1f%% | 长段率 %.1f%% | 对白段率 %.1f%%"
              % (fp["平均段长"], fp["短段率(<60)"], fp["长段率(>100)"], fp["对白段率"]))
        print("  台词: 占比 %.1f%% | 均 %.1f 字 | 连续段均 %.2f（最长 %d）"
              % (fp["台词段%"], fp["台词均字"], fp["连续台词均"], fp["连续台词最长"]))
        print("  他%d 她%d | 套路词%d | 水词%d | 标点 %s"
              % (fp["他"], fp["她"], fp["套路词"], fp["水词"], fp["标点"]))
        print("  连接词: %s" % fp["连接词"])
        print("  章尾钩子: %s" % fp["章尾钩子"])
        print("  —— 对 %s 档：" % preset)
        for line in judge(fp, preset):
            print("     " + line)
        if fp["她"] > fp["他"]:
            print("  !! 性别疑似错乱（她%d > 他%d）" % (fp["她"], fp["他"]))
        for ref in refs:
            rf = fingerprint(ref)
            print("  —— 对标 %s：" % rf["file"])
            for key in ("平均句长", "平均段长", "短句率(<15)", "短段率(<60)",
                        "长段率(>100)", "对白段率"):
                print("     %-14s 本章 %-8s 金标准 %-8s %s"
                      % (key, fp[key], rf[key],
                         "OK" if abs(fp[key] - rf[key]) <= max(2.0, abs(rf[key]) * 0.25) else "NG"))
    return 0


def corpus():
    """从参考书抽样，打印同口径指纹。"""
    import random
    books = {"凡人修仙传人界篇": "凡人修仙传人界篇.txt", "仙逆": "仙逆.txt"}
    for name, fn in books.items():
        p = os.path.join(SAMPLES, fn)
        if not os.path.exists(p):
            print("缺", p); continue
        raw = io.open(p, encoding="utf-8", errors="replace").read()
        chunks = re.split(r"(?m)^\s*第[一二三四五六七八九十百千零0-9]+章.*$", raw)
        chunks = [c for c in chunks if len(c) > 1500]
        random.seed(7)
        pick = random.sample(chunks, min(30, len(chunks)))
        agg = Counter()
        n = 0
        for c in pick:
            fp = fingerprint_from_text(c)
            for k, v in fp.items():
                agg[k] += v
            n += 1
        print("== %s（抽样 %d 章）" % (name, n))
        for k in ("平均句长", "句长中位", "短句率(<15)", "长句率(>30)",
                  "平均段长", "短段率(<60)", "长段率(>100)", "对白段率"):
            print("   %-14s %.1f" % (k, agg[k] / max(1, n)))


def fingerprint_from_text(text):
    text = clean(text)
    sents = sentences(text)
    paras = paragraphs(text)
    slen = [len(re.sub(r"[^一-鿿]", "", s)) for s in sents]
    plen = [len(re.sub(r"[^一-鿿]", "", p)) for p in paras]
    slen = [x for x in slen if x > 0]
    plen = [x for x in plen if x > 0]
    dialogue = [p for p in paras if ("“" in p or "\"" in p or "：" in p)]
    return {
        "平均句长": sum(slen) / max(1, len(slen)),
        "句长中位": sorted(slen)[len(slen) // 2] if slen else 0,
        "短句率(<15)": 100.0 * sum(1 for x in slen if x < 15) / max(1, len(slen)),
        "长句率(>30)": 100.0 * sum(1 for x in slen if x > 30) / max(1, len(slen)),
        "平均段长": sum(plen) / max(1, len(plen)),
        "短段率(<60)": 100.0 * sum(1 for x in plen if x < 60) / max(1, len(plen)),
        "长段率(>100)": 100.0 * sum(1 for x in plen if x > 100) / max(1, len(plen)),
        "对白段率": 100.0 * len(dialogue) / max(1, len(paras)),
    }


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.exit(main())

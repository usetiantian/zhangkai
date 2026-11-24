"""文体模型：把"像不像仙逆"拆成可测量的特征。

不只量句长段长，而是量**描述方式**和**叙事方式**：
感官/身体/心理/比喻/镜头距离/动作密度/数字密度/对白功能/章首章末起收法。

用法:
  python tools/novel/style_model.py --book 仙逆 --n 40
  python tools/novel/style_model.py --mine <我的稿1> <我的稿2> ...
"""
import io
import os
import re
import sys

SAMPLE = ("D:/node/阅读笔记/七猫免费小说/方法论/_学习样本/"
          "凡人修仙传同流派小说集_9本")

# 词表（都是可数的，靠它们密度看描述方式）
FEATURES = {
    "身体部位": "手 指 肩 喉 脸 眼 膝 脚 背 腰 胸 头 掌 指节 虎口",
    "生理反应": "疼 痛 麻 颤 抖 酸 软 僵 冷 热 烫 凉 涩 麻了 发白 发黑",
    "感官·听": "响 声 音 听 静 吵 静得 传不远 压过",
    "感官·触": "粗粝 光滑 干爽 发黏 冰 凉 温 糙 滑 黏 湿 潮",
    "感官·味嗅": "味 苦 腥 香 臭 气",
    "心理直述": "心里 心中 心头 觉得 想到 知道 明白 以为 记得 忘了 明白过来",
    "比喻": "像 如同 仿佛 好似 似的 像一",
    "镜头距离": "眼前 身后 远处 近处 远处 脚下 面前 背后 四周 边上",
    "动作动词": "走 跑 站 坐 蹲 拿 放 抓 握 抬 抬脚 蹲下 转身 回头 伸 递 推 拉",
    "时间标记": "次日 第二天 三天 半晌 一会 片刻 忽然 突然 骤然 天黑 天亮 傍晚 清晨 夜里",
    "数量": "斤 两 丈 步 息 口 个 只 枚 遍 下 天 年",
    "钱粮": "铜板 银子 粮 米 钱 釉 柴 泥",
    "连接词": "可 但 只是 于是 然而 所以 因为 不过 随后 接着 然后",
}
PSEUDO_NARRATIVE = ("像/如同/仿佛", "眼睛/心头", "一丝/涌上", "不禁/忍不住")


def chapter_texts(path, n=40, seed=11):
    raw = io.open(path, encoding="utf-8", errors="replace").read()
    parts = re.split(r"(?m)^\s*第[一二三四五六七八九十百千零0-9]+章.*$", raw)
    chs = [c.strip() for c in parts if len(c.strip()) > 1200]
    import random
    random.seed(seed)
    return random.sample(chs, min(n, len(chs)))


def analyze(text):
    NL = chr(10)
    QL = chr(0x201C)
    IND = chr(0x3000) * 2
    lines = [l.rstrip() for l in text.split(NL) if l.strip()]
    body = "".join(lines)
    n = max(1, len(re.sub(r"[^一-鿿]", "", body)))
    out = {}
    for name, words in FEATURES.items():
        cnt = 0
        for w in words.split():
            cnt += body.count(w)
        out[name] = round(1000.0 * cnt / n, 2)      # 每千字出现次数
    paras = [l for l in lines if l.startswith(IND)]
    dlg = [l for l in paras if QL in l]
    nar = [l for l in paras if QL not in l]
    out["叙述段%"] = round(100.0 * len(nar) / max(1, len(paras)), 1)
    out["对白段%"] = round(100.0 * len(dlg) / max(1, len(paras)), 1)
    out["段数"] = len(paras)
    out["每段字数"] = round(len(re.sub(r"[^一-鿿]", "", body)) / max(1, len(paras)), 1)
    # 对白后是否接叙述（交替率）
    seq = [1 if (QL in l) else 0 for l in paras]
    alt = sum(1 for i in range(len(seq) - 1) if seq[i] != seq[i + 1])
    out["对白叙述交替%"] = round(100.0 * alt / max(1, len(seq) - 1), 1)
    # 连续对白轮数
    runs, cur = [], 0
    for v in seq:
        if v:
            cur += 1
        else:
            if cur: runs.append(cur)
            cur = 0
    if cur: runs.append(cur)
    out["最长连对白段"] = max(runs or [0])
    out["对白轮均段"] = round(sum(runs) / max(1, len(runs)), 2)
    # 标点
    out["逗号/句号"] = round(body.count("，") / max(1, body.count("。")), 2)
    out["破折号"] = round(1000.0 * body.count("——") / n, 2)
    out["省略号"] = round(1000.0 * body.count("…") / n, 2)
    # 叙述段的"信息量"：一句里有多少具体名词
    concrete = 0
    words = "石 砖 灰 泥 柴 碗 瓶 风 光 影 绳 桶 铲 灯 火 雨 雪 铁 木 瓷 釉 罐 筐 担 刺 疤 绳结 油纸 瓦 墙 阶".split()
    for l in nar:
        concrete += sum(1 for w in words if w in l)
    out["叙述具体物/段"] = round(concrete / max(1, len(nar)), 2)
    # 章首/章末起收
    if paras:
        out["章首是场景"] = 1 if re.search(r"[时日晨昏夜]|前|后|里|上|下", paras[0][2:12]) else 0
        out["章末含动作"] = 1 if re.search(r"[走站坐停抬手伸转身回头看听]", paras[-1][2:]) else 0
        out["章末含对白"] = 1 if QL in paras[-1] else 0
    return out


def show(title, agg):
    print("=" * 72)
    print(title)
    keys = list(agg.keys())
    for k in keys:
        print("  %-14s %s" % (k, agg[k]))


def main():
    args = sys.argv[1:]
    if "--book" in args:
        name = args[args.index("--book") + 1]
        fn = {"仙逆": "仙逆.txt", "凡人": "凡人修仙传人界篇.txt"}.get(name, name + ".txt")
        n = int(args[args.index("--n") + 1]) if "--n" in args else 40
        chs = chapter_texts(os.path.join(SAMPLE, fn), n)
        rows = [analyze(c) for c in chs]
        agg = {}
        for k in rows[0]:
            vals = [r[k] for r in rows]
            agg[k] = round(sum(vals) / len(vals), 2)
        agg["样本章数"] = len(rows)
        show("【%s · 抽样 %d 章】" % (name, len(rows)), agg)
        return 0
    if "--mine" in args:
        files = args[args.index("--mine") + 1:]
        rows = [analyze(io.open(f, encoding="utf-8").read()) for f in files]
        agg = {}
        for k in rows[0]:
            agg[k] = round(sum(r[k] for r in rows) / len(rows), 2)
        agg["样本章数"] = len(rows)
        show("【我的稿 · %d 章】" % len(rows), agg)
        return 0
    print(__doc__)
    return 1


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    main()

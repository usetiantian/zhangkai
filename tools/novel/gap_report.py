"""达成率：我离参照书有多远。

对每项特征算"达成度"（在带内=100%，越界按距离衰减），
再和参照书逐项对照，给出总达成率——这就是"够不够 80%"的量化答案。
"""
import io
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import style_model as sm

# (名, 我的目标下限, 上限, 参照书)
BANDS = [
    ("动作动词/千字", 4, 10, 6.15),
    ("对白叙述交替%", 22, 40, 30.92),
    ("对白轮均段", 1.3, 2.6, 1.50),
    ("连接词/千字", 6, 14, 9.21),
    ("身体部位/千字", 8, 20, 12.61),
    ("比喻/千字", 0.8, 2.6, 1.56),
    ("叙述具体物/段", 0.2, 1.0, 0.38),
    ("感官·味嗅/千字", 2.0, 5.0, 3.33),
    ("心理直述/千字", 0.5, 2.0, 1.21),
    ("数量/千字", 20, 45, 30.61),
    ("叙述段%", 58, 80, 76.66),
    ("对白段%", 20, 42, 23.34),
    ("段数", 45, 70, 55.62),
    ("每段字数", 44, 58, 48.57),
    ("逗号/句号", 2.0, 7.0, 6.49),
    ("章末含对白", 0.2, 0.6, 0.33),
]


def score(v, lo, hi):
    if v is None:
        return 0.0
    if lo <= v <= hi:
        return 100.0
    d = (lo - v) if v < lo else (v - hi)
    span = max(1.0, hi - lo)
    return max(0.0, 100.0 - 100.0 * d / span)


def main():
    args = sys.argv[1:]
    mine = args[args.index("--mine") + 1:]
    rows = []
    for f in mine:
        rows.append(sm.analyze(io.open(f, encoding="utf-8").read()))
    agg = {}
    for k in rows[0]:
        vals = [r[k] for r in rows]
        agg[k] = sum(vals) / len(vals)
    print("=" * 78)
    print("《拙火》vs 仙逆 —— 逐项达成率（我的 %d 章均值）" % len(rows))
    print("-" * 78)
    print("%-16s %10s %10s %10s %8s" % ("特征", "我的", "仙逆", "目标带", "达成"))
    print("-" * 78)
    tot = 0.0
    for name, lo, hi, ref in BANDS:
        v = agg.get(name)
        if v is None and "/" in name:
            v = agg.get(name.split("/")[0])
        s = score(v, lo, hi)
        tot += s
        print("%-16s %10.2f %10.2f %10s %7.0f%%"
              % (name, v if v is not None else -1, ref,
                 "%g-%g" % (lo, hi), s))
    print("-" * 78)
    print("总达成率：%.1f%%  （门槛 80%%）" % (tot / len(BANDS)))
    print("\n未达 80% 的项（按差距排序）:")
    gaps = []
    for name, lo, hi, ref in BANDS:
        v = agg.get(name)
        if v is None and "/" in name:
            v = agg.get(name.split("/")[0])
        s = score(v, lo, hi)
        if s < 100:
            gaps.append((100 - s, name, v, ref))
    for g, name, v, ref in sorted(gaps, reverse=True):
        print("  %-16s 差 %5.0f 分（我的 %s / 仙逆 %s）" % (name, g, v, ref))


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    main()

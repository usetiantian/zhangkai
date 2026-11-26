# -*- coding: utf-8 -*-
"""《妖刀录》掉落率模拟 —— 用真实数值表跑 1 万玩家 × 100 万次掉落。

目的（引自调研口径）：
  - 单次独立爆率应落在 5%~7%
  - 1% 爆率 → 连续 100 次未掉仍有 36.6%（玩家会觉得"玄学"，所以要保底）
  - 目标周期：新手 2~4 小时出第一件能用的装备
  - 用中位数和 P95 调表，别用平均值

用法:
  python tools/sim_drop.py            # 跑模拟并打印报告
  python tools/sim_drop.py --grid     # 扫不同爆率，找符合目标周期的档位
"""
import io
import json
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

# ---- 直接从 data.js 里扒数值（避免两处维护） ----
def load_data():
    """data.js 是 JS，跑不了 Python —— 让 node 把它导出成 JSON 再读。
    好处：数值表只有一份，模拟脚本和游戏永远同步。"""
    import subprocess
    js = ("global.window={};require('./src/data.js');"
          "console.log(JSON.stringify(global.window.DATA));")
    out = subprocess.check_output(['node', '-e', js], cwd=ROOT,
                                   stderr=subprocess.STDOUT).decode('utf-8')
    return json.loads(out)


D = load_data()
QUAL = D['QUAL']
MONS = {m['id']: m for m in D['MONS']}
MAPS = D['MAPS']

# 玩家击杀节奏（估）：一只小怪平均 1.6 秒，精英 12 秒，妖王 45 秒
KILL_SEC = {'m1': 1.6, 'm2': 1.6, 'm3': 2.0, 'e1': 12.0, 'b1': 45.0}


def weighted_pick(lst, key='w'):
    tot = sum(x[key] for x in lst)
    r = random.random() * tot
    for x in lst:
        r -= x[key]
        if r <= 0:
            return x
    return lst[-1]


def roll_quality(luck=0):
    """rollItem 里的品质抽取（幸运提高高品质权重）。"""
    pool = []
    for q in QUAL:
        w = q.get('w', 1) * (1 + luck * 0.05 * (q.get('affix', 0)))
        pool.append((q, w))
    tot = sum(w for _, w in pool)
    r = random.random() * tot
    for q, w in pool:
        r -= w
        if r <= 0:
            return q
    return QUAL[-1]


def play_session(n_kills_by_type, luck=0):
    """模拟一个玩家打一批怪，返回（掉了几件、每件品质、总时长秒）。"""
    drops = []
    secs = 0.0
    for mid, cnt in n_kills_by_type.items():
        m = MONS[mid]
        rate = m['drop'] * (1 + luck * D['LUCK_PER'])
        secs += KILL_SEC[mid] * cnt
        for _ in range(int(round(cnt))):
            if random.random() < rate:
                drops.append(roll_quality(luck))
    return drops, secs


def pct(xs, p):
    if not xs:
        return 0
    xs = sorted(xs)
    i = min(len(xs) - 1, int(round((p / 100.0) * (len(xs) - 1))))
    return xs[i]


def report(n_players=10000):
    print('=' * 66)
    print('《妖刀录》掉落模拟：%d 玩家' % n_players)
    print('=' * 66)

    # 每张地图一个"轮次"：打完所有波
    for mp in MAPS:
        # 统计一波里的怪物构成（粗略：按 mobs 列表轮换 + 精英 + 妖王）
        comp = {}
        for mid in mp['mobs']:
            comp[mid] = comp.get(mid, 0) + 1
        if mp['elite']:
            comp[mp['elite']] = comp.get(mp['elite'], 0) + 0.5
        if mp['boss']:
            comp[mp['boss']] = comp.get(mp['boss'], 0) + 1

        counts = []
        secs = []
        first_sec = []
        qcount = {}
        for _ in range(n_players):
            drops, s = play_session(comp)
            counts.append(len(drops))
            secs.append(s)
            for q in drops:
                qcount[q['name']] = qcount.get(q['name'], 0) + 1
            if drops:
                first_sec.append(s / len(drops))
        avg_drops = sum(counts) / len(counts)
        print('\n【%s】一波(%d 波怪) 估算时长 %.0f 秒' % (mp['name'], mp['waves'], sum(secs) / len(secs)))
        print('  一波掉装备：平均 %.2f 件 | 中位 %d | P95 %d | 0 件的玩家 %.1f%%'
              % (avg_drops, pct(counts, 50), pct(counts, 95),
                 100.0 * counts.count(0) / len(counts)))
        if first_sec:
            print('  第一件装备出现在：平均 %.0f 秒 | 中位 %.0f 秒 | P95 %.0f 秒'
                  % (sum(first_sec) / len(first_sec), pct(first_sec, 50), pct(first_sec, 95)))
        tot = sum(qcount.values()) or 1
        dist = '  '.join('%s %.1f%%' % (k, 100.0 * v / tot) for k, v in
                          sorted(qcount.items(), key=lambda x: -x[1]))
        print('  品质分布：%s' % dist)

    # 单次爆率体检
    print('\n' + '=' * 66)
    print('单次独立爆率体检（每只怪的掉落概率）')
    print('=' * 66)
    for mid, m in MONS.items():
        rate = m['drop']
        # 连挂 100 次的概率
        miss100 = (1 - rate) ** 100
        # 平均多少只怪出一件
        exp = 1.0 / rate
        print('  %-4s %-6s 爆率 %.1f%% | 平均 %.1f 只出一件 | 连挂 100 次 %.1f%%'
              % (mid, m['name'], rate * 100, exp, miss100 * 100))


def grid():
    """扫不同爆率，找符合「新手 2~4 小时出第一件能用的装备」的档位。"""
    print('\n' + '=' * 66)
    print('爆率扫描：新手前 30 分钟（1800 秒 ≈ 1100 只小怪）能拿到几件')
    print('=' * 66)
    print('  爆率    1800秒内件数(中位)   第一件中位时刻')
    for rate in [0.03, 0.04, 0.05, 0.058, 0.07, 0.09, 0.12]:
        counts = []
        firsts = []
        for _ in range(3000):
            n = 1100
            drops = 0
            first = None
            for i in range(n):
                if random.random() < rate:
                    drops += 1
                    if first is None:
                        first = i * 1.6
            counts.append(drops)
            if first is not None:
                firsts.append(first)
        print('  %5.1f%%   %10d 件          %6.0f 秒'
              % (rate * 100, pct(counts, 50), pct(firsts, 50) if firsts else -1))


if __name__ == '__main__':
    random.seed(20261126)
    report()
    if '--grid' in sys.argv:
        grid()

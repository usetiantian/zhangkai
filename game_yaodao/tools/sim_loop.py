# -*- coding: utf-8 -*-
"""《妖刀录》完整循环模拟：2 小时游戏会变成什么样。

把已经做出来的系统全算进去：
  打怪 → 掉落（爆率 + 150 只怪史诗保底）→ 背包 60 上限 → 自动分解成精粹
       → 强化消耗金币+精粹 → 十连抽（每 8 次保底史诗 + 6% 宠物卡）
输出：战力曲线、每 10 分钟的装备数/金币/精粹、关键里程碑时间。

用法:
  python tools/sim_loop.py            # 跑 1000 个玩家取中位数
  python tools/sim_loop.py --verbose  # 顺便打���个玩家的详细日志
"""
import io
import json
import os
import random
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)


def load_data():
    js = ("global.window={};require('./src/data.js');"
          "console.log(JSON.stringify(global.window.DATA));")
    out = subprocess.check_output(['node', '-e', js], cwd=ROOT,
                                   stderr=subprocess.STDOUT).decode('utf-8')
    return json.loads(out)


D = load_data()
QUAL = D['QUAL']
RANK = D['QUAL_RANK']
MONS = {m['id']: m for m in D['MONS']}
MAPS = D['MAPS']
GEMS = D['GEMS']
SIGN = D['SIGN']
WEAPONS = D['WEAPONS']

KILL_SEC = {'m1': 1.6, 'm2': 1.6, 'm3': 2.0, 'e1': 12.0, 'b1': 45.0}
DROP = 0.058          # 小怪爆率
BAG_CAP = D['BAG_CAP']
PITY = D['PITY_EPIC']
ENH_MUL = D['ENH_MUL']
ENH_MAX = D['ENH_MAX']
GACHA_EVERY = 180     # 每 180 秒抽一次十连


def wpick(lst, key='w'):
    tot = sum(x[key] for x in lst)
    r = random.random() * tot
    for x in lst:
        r -= x[key]
        if r <= 0:
            return x
    return lst[-1]


def coin_cost(lv):
    return int(60 * (lv + 1) ** 1.45)


def ess_cost(lv):
    return 1 + lv


def affix_value(it):
    v = 0.0
    if it.get('atk'):
        v += it['atk']
    for k, val in it.get('aff', {}).items():
        v += val
    return v


def xp_need(lv):
    return int(50 * (lv ** 1.5))


def power_of(equip, lv=1):
    """简化战力：基础（受等级影响）+ 装备词条×8（和游戏里的公式量级一致）"""
    p = (10 + (lv - 1) * 6) * 2 + 120 * 0.6 + (lv - 1) * 30 * 0.6 + (lv - 1) * 2 * 1.5
    for slot, it in equip.items():
        if not it:
            continue
        lm = 1 + it.get('lv', 0) * ENH_MUL
        p += affix_value(it) * lm * 8
    return int(p)


def play(verbose=False, n_players=1000):
    timelines = []
    milestones = []
    for _ in range(n_players):
        equip = {'weapon': {'q': 'g', 'qn': '精良妖刀', 'col': '#5ec46a', 'slot': 'weapon',
                            'wtype': 'blade', 'atk': 7, 'range': 96, 'cd': 0.55, 'dmgMul': 1.05,
                            'aff': {'atk': 2}, 'lv': 0},
                  'head': None, 'body': None, 'neck': None}
        bag = []
        coins = 0
        essence = 0
        gems = {}
        dry = 0
        kills = 0
        t = 0.0
        pts = []
        ms = {'首件装备': None, '+1强化': None, '+5强化': None, '+10强化': None, '十连史诗': None}
        pulls = 0
        last_pull = 0
        lv = 1
        xp = 0

        while t < 7200:                       # 2 小时
            dt = 1.0                          # 每秒结算
            # —— 打怪：每秒期望击杀 1/1.6 只小怪
            nkill = random.random() < (1 / 1.6)
            if nkill:
                kills += 1
                coins += 3
                if kills % 25 == 0:          # 每 25 只出只精英
                    coins += MONS['e1']['coin']
                    xp += MONS['e1']['xp']
                    while xp >= xp_need(lv):
                        xp -= xp_need(lv)
                        lv += 1
                    if random.random() < 0.35:
                        g = wpick(GEMS)
                        gems[g['id']] = gems.get(g['id'], 0) + 1
                # 掉落
                if dry >= PITY:
                    q = wpick([x for x in QUAL if RANK[x['id']] >= 3])
                    dry = 0
                    got = True
                elif random.random() < DROP:
                    q = wpick(QUAL)
                    got = True
                else:
                    got = False
                if got:
                    # 怪的经验
                    xp += MONS['m1']['xp']
                    while xp >= xp_need(lv):
                        xp -= xp_need(lv)
                        lv += 1
                    it = {'q': q['id'], 'qn': q['name'], 'slot': random.choice(['weapon', 'head', 'body', 'neck']),
                          'aff': {}, 'lv': 0}
                    for k in range(q['affix']):
                        it['aff'][k] = random.randint(1, 8)
                    if it['slot'] == 'weapon':
                        it['atk'] = random.randint(5, 40)
                        it['wtype'] = 'blade'
                    bag.append(it)
                    if ms['首件装备'] is None:
                        ms['首件装备'] = t
                    if RANK[q['id']] >= 3:
                        dry = 0
                    else:
                        dry += 1
                    # 背包满了自动分解（史诗以上不分解）
                    if len(bag) > BAG_CAP:
                        worst = min(range(len(bag)), key=lambda i: RANK[bag[i]['q']])
                        if RANK[bag[worst]['q']] < 3:
                            essence += D['SALVAGE_VALUE'][bag[worst]['q']]
                            bag.pop(worst)
                    # 自动换上更好的
                    for slot in ['weapon', 'head', 'body', 'neck']:
                        cur = equip[slot]
                        cands = [x for x in bag if x['slot'] == slot]
                        if not cands:
                            continue
                        best = max(cands, key=lambda x: RANK[x['q']] * 100 + sum(x['aff'].values()))
                        curv = RANK[cur['q']] * 100 + affix_value(cur) if cur else -1
                        bestv = RANK[best['q']] * 100 + sum(best['aff'].values())
                        if bestv > curv:
                            bag.remove(best)
                            equip[slot] = best
            # —— 强化：有钱有精粹就升
            w = equip['weapon']
            if w and w['lv'] < ENH_MAX:
                lv = w['lv']
                if coins >= coin_cost(lv) and essence >= ess_cost(lv):
                    coins -= coin_cost(lv)
                    essence -= ess_cost(lv)
                    w['lv'] = lv + 1
                    for kk, vv in (('+1强化', 1), ('+5强化', 5), ('+10强化', 10)):
                        if ms[kk] is None and w['lv'] >= vv:
                            ms[kk] = t
            # —— 抽卡
            if t > 0 and int(t) % GACHA_EVERY == 0 and int(t) != last_pull:
                last_pull = int(t)
                for i in range(10):
                    pulls += 1
                    if pulls % 8 == 0:
                        q = wpick([x for x in QUAL if RANK[x['id']] >= 3])
                    else:
                        q = wpick([x for x in QUAL if x['id'] in ('w', 'g', 'b', 'p')])
                    it = {'q': q['id'], 'qn': q['name'], 'slot': random.choice(['weapon', 'head', 'body', 'neck']),
                          'aff': {}, 'lv': 0}
                    for k in range(q['affix']):
                        it['aff'][k] = random.randint(1, 8)
                    if it['slot'] == 'weapon':
                        it['atk'] = random.randint(5, 60)
                        it['wtype'] = 'blade'
                    bag.append(it)
                    if RANK[q['id']] >= 3 and ms['十连史诗'] is None:
                        ms['十连史诗'] = t
                    if len(bag) > BAG_CAP:
                        worst = min(range(len(bag)), key=lambda i: RANK[bag[i]['q']])
                        if RANK[bag[worst]['q']] < 3:
                            essence += D['SALVAGE_VALUE'][bag[worst]['q']]
                            bag.pop(worst)
            # 玩家每分钟按一次「一键分解」（把白/绿全分解成精粹）
            if int(t) % 60 == 0:
                for i in range(len(bag) - 1, -1, -1):
                    if bag[i]['q'] in ('w', 'g'):
                        essence += D['SALVAGE_VALUE'][bag[i]['q']]
                        bag.pop(i)
            if int(t) % 600 == 0:
                pts.append((t, power_of(equip, lv), len(bag), coins, essence))
            t += dt
        timelines.append(pts)
        milestones.append(ms)

    # —— 汇总
    print('=' * 72)
    print('《妖刀录》2 小时完整循环模拟（%d 个玩家）' % n_players)
    print('=' * 72)
    print('\n【战力曲线】每 10 分钟')
    marks = [600, 1200, 1800, 2400, 3600, 5400, 7200]
    for m in marks:
        idx = m // 600 - 1
        vals = sorted(p[idx][1] for p in timelines if len(p) > idx)
        if not vals:
            continue
        p50 = vals[len(vals) // 2]
        p95 = vals[min(len(vals) - 1, int(len(vals) * 0.95))]
        print('  %5d 分钟 → 战力 中位 %6d / P95 %6d' % (m // 60, p50, p95))

    print('\n【里程碑】（中位时间）')
    for k in ['首件装备', '十连史诗', '+1强化', '+5强化', '+10强化']:
        vals = sorted(ms[k] for ms in milestones if ms[k] is not None)
        if not vals:
            print('  %-8s 没人达成' % k)
            continue
        v = vals[len(vals) // 2]
        reached = 100.0 * len(vals) / n_players
        print('  %-8s 中位 %5.0f 秒（%4.1f 分钟）　达成率 %5.1f%%'
              % (k, v, v / 60, reached))

    print('\n【2 小时末的资源】')
    last = [p[-1] for p in timelines if p]
    for idx, label in ((2, '背包件数'), (3, '金币'), (4, '精粹')):
        vals = sorted(x[idx] for x in last)
        print('  %-8s 中位 %d' % (label, vals[len(vals) // 2]))


if __name__ == '__main__':
    random.seed(20261127)
    # last_pull 需要在循环外初始化
    src = io.open(__file__, encoding='utf-8').read()
    play(verbose='--verbose' in sys.argv)

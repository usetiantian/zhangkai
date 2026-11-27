# -*- coding: utf-8 -*-
"""推图节奏模拟器：验证指数曲线 + 等级压制下的玩家进度。

模型忠实于游戏数值：
  玩家：atk/hp 由等级 + 装备(蓝紫为主, 属性平) + 强化构成
  怪物：基础 ×2.1^图(血) / ×1.7^图(攻)，精英 ×8 血 ×2 攻
  压制：图等级 - 玩家等级 → 伤害 ×1/0.8/0.55/0.3/0.12
  判定：一波(4小怪)总血 / 玩家DPS < 玩家存活时间 → 能过图
输出：每小时能推到第几张图、卡在哪、为什么。
用法: python tools/tune_curve.py [hours]
"""
import sys

HOURS = float(sys.argv[1]) if len(sys.argv) > 1 else 6.0

# ---- 游戏常数（改这里对齐 data.js）----
TIER_HP, TIER_ATK, TIER_RW = 2.1, 1.7, 1.8
MOB_BASE = {'m1': (26, 5, 4), 'm2': (58, 10, 9), 'm4': (74, 12, 11), 'm6': (126, 19, 18), 'm7': (96, 16, 16)}
MAP_LV = [1, 4, 8, 12, 16, 20, 26]
MAP_MOB = ['m1', 'm2', 'm2', 'm4', 'm6', 'm6', 'm7']      # 每图主力小怪
MAP_WAVES = [5, 6, 7, 6, 7, 8, 9]
PW = [350, 750, 1550, 3250, 6800, 14300, 30000]
WAVE_MOBS = 4                 # 一波小怪数
HIT_IV = 0.55                 # 玩家受击无敌帧
SKILL_MUL = 1.5               # 技能把 DPS 放大的系数
ELITE_HP_MUL, ELITE_ATK_MUL = 8.0, 2.0


def suppress(diff):
    if diff <= 0: return 1.0
    if diff <= 2: return 0.8
    if diff <= 4: return 0.55
    if diff <= 7: return 0.3
    return 0.12


def hero_atk(lv, enh_avg, gear_flat):
    return 10 + (lv - 1) * 6 + gear_flat * (1 + enh_avg * 0.08)


def hero_hp(lv, gear_flat):
    return 120 + (lv - 1) * 30 + gear_flat * 2.0


def xp_need(lv):
    return 50 * lv ** 1.5


def mob_stats(tier, mid):
    hp, atk, xp = MOB_BASE[mid]
    return hp * TIER_HP ** tier, atk * TIER_ATK ** tier, xp * TIER_RW ** tier


def can_clear(tier, lv, enh_avg, gear_flat):
    """返回 (能过, 击杀一波耗时, 存活时间, 说明)"""
    mhp, matk, _ = mob_stats(tier, MAP_MOB[tier])
    atk = hero_atk(lv, enh_avg, gear_flat)
    hp = hero_hp(lv, gear_flat)
    sup = suppress(MAP_LV[tier] - lv)
    dps = atk / 0.62 * SKILL_MUL * sup
    incoming = matk * 1.8 / HIT_IV           # 同时贴脸 ~1.8 只（刷新有间隔+走位）
    survive = hp / incoming
    wave_hp = mhp * WAVE_MOBS
    ttk = wave_hp / dps
    return ttk < survive, ttk, survive, sup


def main():
    lv, xp = 1, 0.0
    gear_flat, enh_avg = 12.0, 0.0           # 起步装
    cur_map = 0
    t = 0.0
    dt = 1.0                                  # 1 秒步进
    marks = []
    walls = {}
    while t < HOURS * 3600:
        # 当前图的收益（能打就打最高能过的图）
        best = 0
        for tier in range(7):
            ok, _, _, _ = can_clear(tier, lv, enh_avg, gear_flat)
            if ok:
                best = tier
        if best > cur_map:
            marks.append((t / 3600, best + 1, lv, int(hero_atk(lv, enh_avg, gear_flat))))
            cur_map = best
        # 刷当前图：击杀节奏
        _, ttk, survive, sup = can_clear(cur_map, lv, enh_avg, gear_flat)
        _, _, mxp = mob_stats(cur_map, MAP_MOB[cur_map])
        kills_per_sec = WAVE_MOBS / max(ttk, 0.1)
        xp += mxp * kills_per_sec * dt
        while xp >= xp_need(lv):
            xp -= xp_need(lv)
            lv += 1
        # 养成：每 90 秒强一件、每 6 分钟换更好装备（gear_flat 慢慢涨）
        t += dt
        enh_avg = min(15.0, t / 90 * 0.35)
        gear_flat = min(45.0, 12 + t / 3600 * 8)
        if t % 3600 < dt:
            walls[int(t / 3600)] = (cur_map + 1, lv, can_clear(cur_map + 1, lv, enh_avg, gear_flat) if cur_map + 1 < 7 else None)
    print('时间(h)  推到图  等级  战力')
    for h, m, l, a in marks:
        print('%6.1f    图%d   Lv%-3d  %d' % (h, m, l, a))
    print()
    print('整点状态（当前图/等级）:', {h: v[:2] for h, v in walls.items()})
    # 卡关分析
    ok, ttk, surv, sup = can_clear(6, lv, enh_avg, gear_flat)
    print('终图检查 Lv%d: 能过=%s 击杀一波%.1fs 存活%.1fs 压制×%.2f' % (lv, ok, ttk, surv, sup))
    ok5, ttk5, surv5, _ = can_clear(4, lv, enh_avg, gear_flat)
    print('图5检查  Lv%d: 能过=%s 击杀%.1fs 存活%.1fs' % (lv, ok5, ttk5, surv5))


if __name__ == '__main__':
    main()

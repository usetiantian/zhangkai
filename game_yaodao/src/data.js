/* ============ 《妖刀录》数值表 ============
 * 数据来源：传奇爆率方法论（掉落/保底分层）+ 《寻道大千》（品质与层级反比）
 * 所有数值集中在这里，方便后面跑模拟脚本调表。
 */
window.DATA = (function () {
  /* ---------- 品质 ---------- */
  var QUAL = [
    { id: 'w', name: '普通', color: '#c8c2b4', affix: 0, mul: 1.00, w: 58 },  // 白
    { id: 'g', name: '精良', color: '#5ec46a', affix: 1, mul: 1.35, w: 27 },  // 绿
    { id: 'b', name: '稀有', color: '#4a9bff', affix: 2, mul: 1.80, w: 11 },  // 蓝
    { id: 'p', name: '史诗', color: '#b45cff', affix: 3, mul: 2.40, w: 3.2 }, // 紫
    { id: 'o', name: '传说', color: '#ff9a2e', affix: 4, mul: 3.20, w: 0.7 }, // 橙
    { id: 'r', name: '神话', color: '#ff3b4e', affix: 5, mul: 4.20, w: 0.1 }  // 红
  ];

  /* ---------- 部位 ---------- */
  var SLOTS = [
    { id: 'weapon', name: '武器', main: 'atk' },
    { id: 'head', name: '头冠', main: 'def' },
    { id: 'body', name: '衣甲', main: 'hp' },
    { id: 'neck', name: '灵佩', main: 'crit' }
  ];

  /* ---------- 武器（4 种，攻击方式不同）---------- */
  var WEAPONS = {
    blade: { id: 'blade', name: '长刀', atk: 10, range: 62, cd: 0.62, dmgMul: 1.00, desc: '挥砍' },
    sword: { id: 'sword', name: '灵剑', atk: 8, range: 96, cd: 0.50, dmgMul: 0.85, desc: '突刺' },
    staff: { id: 'staff', name: '桃木杖', atk: 13, range: 132, cd: 0.86, dmgMul: 1.15, desc: '远程' },
    fist: { id: 'fist', name: '铁拳', atk: 6, range: 48, cd: 0.34, dmgMul: 0.72, desc: '贴身' }
  };

  /* ---------- 词条池 ---------- */
  var AFFIX = {
    atk: { id: 'atk', name: '攻击', v: [2, 7], w: 18 },
    def: { id: 'def', name: '防御', v: [3, 9], w: 16 },
    hp: { id: 'hp', name: '生命', v: [12, 40], w: 15 },
    crit: { id: 'crit', name: '暴击率', v: [1, 4], w: 11 },
    critDmg: { id: 'critDmg', name: '暴击伤害', v: [4, 14], w: 9 },
    aspd: { id: 'aspd', name: '攻速', v: [2, 6], w: 9 },
    luck: { id: 'luck', name: '幸运', v: [1, 5], w: 9 },       // 影响爆率
    vamp: { id: 'vamp', name: '吸血', v: [1, 4], w: 6 },
    drop: { id: 'drop', name: '掉落率', v: [3, 10], w: 7 }
  };

  /* ---------- 怪物 ---------- */
  var MONS = [
    { id: 'm1', name: '山鼠', hp: 26, atk: 5, spd: 46, xp: 4, coin: 3, r: 15, drop: 0.055, col: '#8b7d63', boss: 0 },
    { id: 'm2', name: '野狼', hp: 58, atk: 10, spd: 62, xp: 9, coin: 7, r: 18, drop: 0.070, col: '#6d7a8c', boss: 0 },
    { id: 'm3', name: '妖藤', hp: 42, atk: 8, spd: 34, xp: 7, coin: 5, r: 17, drop: 0.060, col: '#4f8a52', boss: 0 },
    { id: 'e1', name: '铁背熊', hp: 420, atk: 22, spd: 40, xp: 60, coin: 46, r: 34, drop: 0.16, col: '#7a5230', boss: 1 },
    { id: 'b1', name: '妖王·黑煞', hp: 1500, atk: 38, spd: 34, xp: 240, coin: 190, r: 46, drop: 0.42, col: '#5a1f2e', boss: 2 }
  ];

  /* ---------- 技能（3 个主动 + 1 普攻）---------- */
  var SKILLS = [
    { id: 's1', name: '剑气', cd: 3.0, cost: 0, dmg: 1.6, range: 130, aoe: 0, col: '#8fe3ff' },
    { id: 's2', name: '旋风', cd: 6.0, cost: 0, dmg: 1.1, range: 105, aoe: 1, col: '#ffd06a' },
    { id: 's3', name: '妖火', cd: 10.0, cost: 0, dmg: 3.4, range: 175, aoe: 1, col: '#ff7a4a' }
  ];

  /* ---------- 宠物（3 位，词条轴）---------- */
  var PETS = [
    { id: 'beast', name: '灵兽', slot: 'beast', main: 'atk', base: 0.9 },
    { id: 'mount', name: '坐骑', slot: 'mount', main: 'aspd', base: 0.8 },
    { id: 'pal', name: '伙伴', slot: 'pal', main: 'drop', base: 0.8 }
  ];

  /* ---------- 地图 ---------- */
  var MAPS = [
    { id: 1, name: '青石村外', waves: 5, mobs: ['m1', 'm1', 'm2', 'm3', 'm1'], elite: 'e1', boss: null, lv: 1 },
    { id: 2, name: '乱葬岗', waves: 6, mobs: ['m2', 'm3', 'm1', 'e1'], elite: 'e1', boss: null, lv: 4 },
    { id: 3, name: '黑风寨', waves: 7, mobs: ['m2', 'm3', 'e1', 'm1'], elite: 'e1', boss: 'b1', lv: 8 }
  ];

  /* ---------- 武器皮肤（只换外观，不改数值）---------- */
  var WEAPON_SKIN = [
    { id: 'ws1', name: '素铁', w: 'blade', col: '#b9c2cc' },
    { id: 'ws2', name: '赤炎', w: 'blade', col: '#ff6b35' },
    { id: 'ws3', name: '青霜', w: 'sword', col: '#7fd7ff' },
    { id: 'ws4', name: '玄墨', w: 'staff', col: '#8a6ad6' }
  ];

  /* ---------- 人物皮肤（4 套 × 2 性别）---------- */
  var CHAR_SKIN = [
    { id: 'cs1', name: '素衣', sex: 'm', col: '#5b6b7a', hair: '#1d1b1a' },
    { id: 'cs2', name: '青竹', sex: 'm', col: '#2f6b57', hair: '#1d1b1a' },
    { id: 'cs3', name: '素衣', sex: 'f', col: '#7a6a86', hair: '#241b1c' },
    { id: 'cs4', name: '绛紫', sex: 'f', col: '#6d2740', hair: '#241b1c' }
  ];

  /* ---------- 妖刀录（新手村）---------- */
  var DAGGER = {
    id: 'dag1', name: '妖刀', atk: 7, range: 96, cd: 0.55, dmgMul: 1.05, col: '#d8dde6', hits: 1
  };

  return {
    QUAL: QUAL, SLOTS: SLOTS, WEAPONS: WEAPONS, AFFIX: AFFIX, MONS: MONS, SKILLS: SKILLS,
    PETS: PETS, MAPS: MAPS, WEAPON_SKIN: WEAPON_SKIN, CHAR_SKIN: CHAR_SKIN, DAGGER: DAGGER,
    PET_MAX_LV: 10, MOOD_MAX: 100, MOOD_DECAY_MS: 2 * 3600 * 1000, MOOD_FEED: 18,
    LUCK_PER: 0.05,          // 幸运 +N → 爆率 ×(1+0.05N)
    DROPRATE_BASE: 0.058     // 单次独立爆率先按 5.8% 测（调研口径 5%~7%）
  };
})();

/* ============ 《妖刀录》数值表 ============
 * 数据来源：传奇爆率方法论（掉落/保底分层）+ 《寻道大千》（品质与层级反比）
 * 所有数值集中在这里，方便后面跑模拟脚本调表。
 */
window.DATA = (function () {
  /* ---------- 品质 ---------- */
  /* 品质排名（用于「保底至少史诗」「分解时找最差的」）：白 0 → 红 5 */
  var QUAL_RANK = { w: 0, g: 1, b: 2, p: 3, o: 4, r: 5 };
  /* 分解成精粹的价值（按品质） */
  var SALVAGE_VALUE = { w: 1, g: 4, b: 12, p: 40, o: 120, r: 400 };
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
  /* ground/deco：程序化地面的底色和装饰配色。
     为什么不用美术图平铺：AI 出的地面没法无缝，镜像拼接一眼能看出对称花纹。
     程序化地面是无限、无缝、零包体、跟着相机完美滚动的。 */
  var MAPS = [
    { id: 1, name: '青石村外', waves: 5, mobs: ['m1', 'm1', 'm2', 'm3', 'm1'], elite: 'e1', boss: null, lv: 1,
      ground: '#5d4f38', ground2: '#6d5c40', deco: ['#4a3f2c', '#7f8a4e', '#8d8a7c'] },
    { id: 2, name: '乱葬岗', waves: 6, mobs: ['m2', 'm3', 'm1', 'e1'], elite: 'e1', boss: null, lv: 4,
      ground: '#3f3c38', ground2: '#4a4641', deco: ['#575249', '#6d6558', '#8a8072'] },
    { id: 3, name: '黑风寨', waves: 7, mobs: ['m2', 'm3', 'e1', 'm1'], elite: 'e1', boss: 'b1', lv: 8,
      ground: '#332821', ground2: '#3d3128', deco: ['#241d17', '#5a4432', '#6d5b46'] }
  ];

  /* ---------- 武器皮肤（只换外观，不改数值）---------- */
  /* ---------- 武器外观（贴图 + 特效，两个独立资源 ID）----------
     ⚠️ 竞品教训（咸鱼之王）：换皮时只迁了模型、没迁特效，老皮肤返场还不带特效。
     所以这里 img 和 fx 必须成对出现，谁也别想只换一半。

     anchor：手在**主角贴图**上的位置（比例坐标，男女取折中值）
     grip  ：握把在**武器贴图**上的位置（比例坐标）
     rot   ：待机角度（弧度，负=向右倾）
     swing ：挥砍时角度从 from 转到 to，dur 秒
     img 指到 assets/ 下；图片没加载出来时游戏回退到「小色条」，不会崩。 */
  var HAND = { x: 0.31, y: 0.70 };          /* 手部锚点（主角贴图比例，男女折中） */
  /* 武器贴图已左右翻转（prep_assets FLIP），所以握把在**右侧** */
  var GRIP_D = { x: 0.87, y: 0.86 };        /* 斜持武器的握把（翻转后） */
  var GRIP_S = { x: 0.50, y: 0.93 };        /* 竖杖的握把 */
  var GRIP_F = { x: 0.32, y: 0.32 };        /* 拳套：拳头中心就是手 */

  var WEAPON_SKIN = [
    { id: 'ws_blade_1', name: '青锋', w: 'blade', col: '#9fd8ff', img: 'weapon/ws_blade_1.png',
      fx: 'slash_ice', anchor: HAND, grip: GRIP_D, rot: 0.22,
      swing: { dur: 0.26, from: -0.85, to: 0.85 }, trail: '#bfe9ff' },
    { id: 'ws_blade_2', name: '赤霄', w: 'blade', col: '#ff6b35', img: 'weapon/ws_blade_2.png',
      fx: 'slash_fire', anchor: HAND, grip: GRIP_D, rot: 0.22,
      swing: { dur: 0.28, from: -0.9, to: 0.9 }, trail: '#ffb066' },
    { id: 'ws_sword_1', name: '流云', w: 'sword', col: '#fff2c4', img: 'weapon/ws_sword_1.png',
      fx: 'slash_gold', anchor: HAND, grip: GRIP_D, rot: 0.26,
      swing: { dur: 0.24, from: -0.8, to: 0.8 }, trail: '#ffe9a8' },
    { id: 'ws_sword_2', name: '紫电', w: 'staff', col: '#b78aff', img: 'weapon/ws_sword_2.png',
      fx: 'slash_thunder', anchor: HAND, grip: GRIP_D, rot: 0.18,
      swing: { dur: 0.3, from: -0.75, to: 0.95 }, trail: '#d9c2ff' },
    { id: 'ws_staff_1', name: '玄木', w: 'staff', col: '#8a6ad6', img: 'weapon/ws_staff_1.png',
      fx: 'orb_cyan', anchor: HAND, grip: GRIP_S, rot: 0,
      swing: { dur: 0.32, from: -0.45, to: 0.75 }, trail: '#a98aff' },
    { id: 'ws_staff_2', name: '烈阳', w: 'staff', col: '#ffb347', img: 'weapon/ws_staff_2.png',
      fx: 'orb_fire', anchor: HAND, grip: GRIP_S, rot: 0,
      swing: { dur: 0.32, from: -0.45, to: 0.75 }, trail: '#ffcf7a' },
    { id: 'ws_fist_1', name: '金刚', w: 'fist', col: '#ffd23a', img: 'weapon/ws_fist_1.png',
      fx: 'punch_blue', anchor: HAND, grip: GRIP_F, rot: 0, h: 26,
      swing: { dur: 0.2, from: -0.5, to: 0.8 }, trail: '#ffe9a8' },
    { id: 'ws_fist_2', name: '血影', w: 'fist', col: '#d94b6a', img: 'weapon/ws_fist_2.png',
      fx: 'punch_crimson', anchor: HAND, grip: GRIP_F, rot: 0, h: 26,
      swing: { dur: 0.22, from: -0.5, to: 0.85 }, trail: '#ff8fa8' },
    { id: 'ws_dagger_1', name: '月影', w: 'blade', col: '#c9d6e8', img: 'weapon/ws_dagger_1.png',
      fx: 'slash_moon', anchor: HAND, grip: GRIP_D, rot: 0.30,
      swing: { dur: 0.2, from: -0.9, to: 0.8 }, trail: '#e8f0ff' },
    { id: 'ws_dagger_2', name: '星辰', w: 'blade', col: '#a98aff', img: 'weapon/ws_dagger_2.png',
      fx: 'slash_star', anchor: HAND, grip: GRIP_D, rot: 0.30,
      swing: { dur: 0.24, from: -0.95, to: 0.85 }, trail: '#d9c2ff' }
  ];

  /* 老存档的武器皮肤 id → 新 id（旧皮肤只对应前四把） */
  var WS_MIGRATE = { ws1: 'ws_blade_1', ws2: 'ws_blade_2', ws3: 'ws_sword_1', ws4: 'ws_staff_1' };

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
    QUAL: QUAL, QUAL_RANK: QUAL_RANK, SALVAGE_VALUE: SALVAGE_VALUE,
    SLOTS: SLOTS, WEAPONS: WEAPONS, AFFIX: AFFIX, MONS: MONS, SKILLS: SKILLS,
    PETS: PETS, MAPS: MAPS, WEAPON_SKIN: WEAPON_SKIN, CHAR_SKIN: CHAR_SKIN, DAGGER: DAGGER,
    WS_MIGRATE: WS_MIGRATE,
    /* 主角贴图（按性别）。img 没加载出来就回退到程序化画的小人。 */
    HERO_IMG: { m: 'run/hero_m.png', f: 'run/hero_f.png' },
    /* 怪物贴图：按 MONS 的 id 对应 */
    MONS_IMG: { m1: 'mob/m1.png', m2: 'mob/m2.png', m3: 'mob/m3.png',
                e1: 'mob/e1.png', b1: 'mob/b1.png' },
    /* 地图底纹：按 MAPS 的 id 对应 */
    MAPS_IMG: { 1: 'map/map1.jpg', 2: 'map/map2.jpg', 3: 'map/map3.jpg' },
    HERO_H: 68,               /* 主角在屏幕上的高度（px） */
    WEAPON_H: 42,             /* 武器贴图在屏幕上的高度（px） */
    /* 装备强化：每级 +8% 基础属性，满级 15 */
    ENH_MAX: 15,
    ENH_MUL: 0.08,
    ENH_COIN: function (lv) { return Math.round(60 * Math.pow(lv + 1, 1.45)); },
    ENH_ESS: function (lv) { return 1 + lv; },
    /* 背包容量：超了自动分解最差的（史诗以上不分解） */
    BAG_CAP: 60,
    /* 掉落保底：连续这么多只怪没出史诗，下一次必出 */
    PITY_EPIC: 150,
    PET_MAX_LV: 10, MOOD_MAX: 100, MOOD_DECAY_MS: 2 * 3600 * 1000, MOOD_FEED: 18,
    LUCK_PER: 0.05,          // 幸运 +N → 爆率 ×(1+0.05N)
    DROPRATE_BASE: 0.058     // 单次独立爆率先按 5.8% 测（调研口径 5%~7%）
  };
})();

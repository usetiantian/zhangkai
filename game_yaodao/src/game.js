/* ============ 《妖刀录》战斗 + 界面（P0） ============ */
(function () {
  'use strict';
  var D = window.DATA, G = window.G, ctx = G.ctx;
  var S = null;   // 游戏状态

  /* ============ 工具 ============ */
  function rnd(a, b) { return a + Math.random() * (b - a); }
  function irnd(a, b) { return Math.floor(rnd(a, b + 1)); }
  function pick(arr) { return arr[Math.floor(Math.random() * arr.length)]; }
  function dist(a, b) { var dx = a.x - b.x, dy = a.y - b.y; return Math.sqrt(dx * dx + dy * dy); }
  function fmt(n) { return n >= 10000 ? (n / 1000).toFixed(1) + 'w' : String(Math.floor(n)); }

  function weightedPick(list, key) {
    var tot = 0, i;
    for (i = 0; i < list.length; i++) tot += list[i][key || 'w'];
    var r = Math.random() * tot;
    for (i = 0; i < list.length; i++) { r -= list[i][key || 'w']; if (r <= 0) return list[i]; }
    return list[list.length - 1];
  }

  /* ============ 存档结构 ============ */
  function newSave() {
    return {
      /* sex 留空 → 首次进入走 'pick' 性别选择（原来默认 'm' 导致选人界面永远进不去） */
      sex: '', skin: 'cs1', wskin: 'ws_blade_1',
      map: 0, wave: 0, best: 0, maxWave: 0, kills: 0, pulls: 0, pity: 0,
      dry: 0, essence: 0,     /* dry=连续没出史诗的击杀数（保底用），essence=精粹 */
      gems: {},               /* 宝石库存 {gem_atk: 2, ...} */
      cleared: {},             /* 通关记录 {1:true, 2:true} */
      signDay: 0, signDate: '',  /* 签到：累计天数 + 最后签到日期 */
      skLv: [1, 1, 1],          /* 三个技能各自等级 */
      lv: 1, xp: 0,             /* 角色等级 + 当前经验 */
      firstDrop: 0,              /* 首杀是否已爆过装备（首杀必掉） */
      dex: {}, dexP: 0,          /* 图鉴：每种怪的击杀数 + 图鉴点 */
      muted: false,             /* 音效开关 */
      bag: [],
      /* 开局送一把基础妖刀 —— 空手开场没有打击感，也没法试强化 */
      equip: { weapon: { uid: 'start_w', q: 'g', qn: '精良妖刀', col: '#5ec46a', slot: 'weapon',
        wtype: 'blade', atk: 7, range: 96, cd: 0.55, dmgMul: 1.05, aff: { atk: 2 }, lv: 0 },
        head: null, body: null, neck: null },
      pet: null, petLv: 1, petMood: 70, petMoodAt: Date.now(),
      coins: 0, items: 0, log: [], offAt: Date.now()
    };
  }
  function load() {
    var s = G.loadSave();
    if (!s || !s.equip) { s = newSave(); }
    if (s.wskin && D.WS_MIGRATE[s.wskin]) s.wskin = D.WS_MIGRATE[s.wskin];
    /* 老存档可能没有武器 */
    if (s.equip && !s.equip.weapon) {
      s.equip.weapon = { uid: 'start_w', q: 'g', qn: '精良妖刀', col: '#5ec46a', slot: 'weapon',
        wtype: 'blade', atk: 7, range: 96, cd: 0.55, dmgMul: 1.05, aff: { atk: 2 }, lv: 0 };
    }
    if (!s.pet) { s.pet = null; s.petLv = 1; s.petMood = 70; s.petMoodAt = Date.now(); }
    if (!s.offAt) s.offAt = Date.now();
    return s;
  }

  /* ============ 离线收益 ============
     回来时按离开时长给金币+精粹，上限 4 小时，效率远低于在线（在线 ~2250 杀/时）。
     门槛 3 分钟起算；offAt 由 boot.persist 每次存档时刷新。 */
  function grantOffline() {
    var s = S.save;
    var now = Date.now();
    var away = now - (s.offAt || now);
    s.offAt = now;
    if (away < 180000 || S.state === 'pick') return;
    var hrs = Math.min(4, away / 3600000);
    var mi = D.MAPS.indexOf(S.map || D.MAPS[0]);
    if (mi < 0) mi = 0;
    var coins = Math.floor(hrs * (90 + mi * 180));
    var ess = Math.floor(hrs * (1 + Math.floor(mi / 2)));
    s.coins += coins; s.items += ess;
    var mins = Math.floor(away / 60000);
    var dur = mins >= 60 ? (Math.floor(mins / 60) + ' 小时 ' + (mins % 60) + ' 分') : (mins + ' 分钟');
    toast('欢迎回来！离线 ' + dur + '：金币 +' + fmt(coins) + '，精粹 +' + ess);
    S.toastT = 5;
    G.persist();
  }

  /* ============ 装备生成 ============ */
  var SLOT_KEYS = ['weapon', 'head', 'body', 'neck'];
  /* forceQ：保底时指定品质（武器攻击/词条数都要按新品质重算，不能只改标签） */
  function rollItem(luck, forceQ) {
    var q = forceQ || weightedPick(D.QUAL);
    var slot = pick(SLOT_KEYS);
    var it = {
      uid: 'i' + Date.now() + Math.floor(Math.random() * 1000),
      q: q.id, qn: q.name, col: q.color, slot: slot,
      wtype: slot === 'weapon' ? pick(['blade', 'sword', 'staff', 'fist']) : null,
      aff: {}
    };
    var n = q.affix;
    var pool = Object.keys(D.AFFIX);
    for (var i = 0; i < n; i++) {
      var k = pick(pool);
      if (it.aff[k] !== undefined) { i--; continue; }
      var a = D.AFFIX[k];
      var v = irnd(a.v[0], a.v[1]) + (k === 'luck' ? 0 : 0);
      it.aff[k] = v;
    }
    if (slot === 'weapon') {
      var w = D.WEAPONS[it.wtype];
      it.atk = Math.round(w.atk * q.mul * (1 + rnd(0, 0.12)));
      it.range = w.range; it.cd = w.cd; it.dmgMul = w.dmgMul;
    }
    /* 套装：蓝色以上 35% 概率带标记 */
    if (D.SETS && (D.QUAL_RANK[q.id] || 0) >= 2 && Math.random() < 0.35) {
      it.set = D.SETS[Math.floor(Math.random() * D.SETS.length)].id;
    }
    return it;
  }

  /* ---------- 背包容量 + 自动分解 ----------
     模拟结论：5.8% 爆率 × 1.6 秒一只怪 = 25 秒一件，30 分钟 64 件。
     背包不设上限的话会被垃圾塞爆、存档越来越大。
     所以：超过容量就把**最差的**几件分解成精粹（不是直接丢，玩家不亏）。 */
  function addToBag(it) {
    var s = S.save;
    if (s.bag.length < D.BAG_CAP) return;
    /* 找一件品质最低的分解掉（史诗以上不分解） */
    var worst = -1, worstRank = 99;
    for (var i = 0; i < s.bag.length; i++) {
      var rk = D.QUAL_RANK && D.QUAL_RANK[s.bag[i].q] !== undefined ? D.QUAL_RANK[s.bag[i].q] : 0;
      if (rk < worstRank) { worstRank = rk; worst = i; }
    }
    if (worst < 0) return;
    if (worstRank >= 3) return;          /* 全是史诗以上就不分解，宁可超容量 */
    var junk = s.bag.splice(worst, 1)[0];
    s.essence = (s.essence || 0) + D.SALVAGE_VALUE[junk.q] || 3;
    S.nums.push({ x: h.x + rnd(-14, 14), y: h.y - 34, v: -24, t: 1.0, txt: '+' + (D.SALVAGE_VALUE[junk.q] || 3) + ' 精粹', col: '#b9a8ff' });
  }

  /* ============ 属性计算 ============ */
  function stats() {
    var s = S.save, lv = s.lv || 1;
    /* 等级加成：每级 +6 攻击 +30 生命 +2 防御 */
    var st = { atk: 10 + (lv - 1) * 6, def: (lv - 1) * 2, hp: 120 + (lv - 1) * 30,
               crit: 5, critDmg: 50, aspd: 0, luck: 0, vamp: 0, drop: 0 };
    var eq = s.equip;
    SLOT_KEYS.forEach(function (k) {
      var it = eq[k];
      if (!it) return;
      var q = D.QUAL.filter(function (x) { return x.id === it.q; })[0] || D.QUAL[0];
      /* 强化等级：每级 +8% 基础属性（武器攻击/词条/品质主属性都吃） */
      var lm = 1 + (it.lv || 0) * D.ENH_MUL;
      if (k === 'weapon') { st.atk += Math.round((it.atk || 0) * lm); }
      for (var a in it.aff) st[a] = (st[a] || 0) + it.aff[a] * lm;
      // 品质给主属性加成
      var sl = D.SLOTS.filter(function (x) { return x.id === k; })[0];
      var base = { atk: 3, def: 2, hp: 14, crit: 1 }[sl.main] || 0;
      st[sl.main] += Math.round(base * q.mul * lm);
      /* 镶嵌的宝石 */
      if (it.gem) {
        var gd = D.GEMS.filter(function (x) { return x.id === it.gem; })[0];
        if (gd) st[gd.main] += gd.v;
      }
    });
    // 宠物
    if (s.pet) {
      var p = D.PETS.filter(function (x) { return x.id === s.pet.slot; })[0];
      var m = mood();
      var mul = 1 + (s.petLv - 1) * 0.05 + (m >= 80 ? 0.10 : 0);
      st[p.main] = Math.round((st[p.main] || 0) + p.base * 10 * mul);
      st.atk = Math.round(st.atk * (1 + (s.petLv - 1) * 0.04 * (m >= 80 ? 1.2 : 1)));
    }
    /* 套装加成：已装备的同名套装 2 件小成 / 4 件大成（放最后，百分比吃满加成） */
    var sc = setCounts(eq);
    for (var sid in sc) {
      var sd = D.SETS && D.SETS.filter(function (x) { return x.id === sid; })[0];
      if (!sd) continue;
      if (sc[sid] >= 2) for (var bk in sd.b2) setBonus(st, bk, sd.b2[bk]);
      if (sc[sid] >= 4) for (var bk2 in sd.b4) setBonus(st, bk2, sd.b4[bk2]);
    }
    st.atk = Math.round(st.atk);
    return st;
  }
  function setCounts(eq) {
    var sc = {};
    SLOT_KEYS.forEach(function (k) { var e2 = eq[k]; if (e2 && e2.set) sc[e2.set] = (sc[e2.set] || 0) + 1; });
    return sc;
  }
  function setBonus(st, k, v) {
    if (k === 'atkPct') st.atk = Math.round(st.atk * (1 + v / 100));
    else if (k === 'hpPct') st.hp = Math.round(st.hp * (1 + v / 100));
    else st[k] = (st[k] || 0) + v;
  }
  function setD(it) {
    if (!it || !it.set || !D.SETS) return null;
    return D.SETS.filter(function (x) { return x.id === it.set; })[0] || null;
  }
  function power(st) {
    st = st || stats();
    return Math.round(st.atk * 2 + st.def * 1.5 + st.hp * 0.6 + st.crit * 12 + st.critDmg * 8 + st.aspd * 10 + st.luck * 14 + st.vamp * 9 + st.drop * 6);
  }
  function mood() {
    var s = S.save;
    var dt = Date.now() - (s.petMoodAt || Date.now());
    if (dt > 0) {
      var dec = Math.floor(dt / D.MOOD_DECAY_MS);
      if (dec > 0) { s.petMood = Math.max(0, (s.petMood || 0) - dec); s.petMoodAt = (s.petMoodAt || 0) + dec * D.MOOD_DECAY_MS; }
    }
    return s.petMood || 0;
  }

  /* ---------- 等级 ---------- */
  /* 升到下一级需要的经验：50 * n^1.5（第 1→2 级 50，第 5→6 级 559） */
  function xpNeed(lv) { return Math.round(50 * Math.pow(lv, 1.5)); }
  function addXp(s, amount) {
    s.xp = (s.xp || 0) + amount;
    var ups = 0;
    while (s.xp >= xpNeed(s.lv)) {
      s.xp -= xpNeed(s.lv);
      s.lv++;
      ups++;
    }
    if (ups) {
      S.stats = stats();
      toast('升级！Lv ' + s.lv);
      if (G.sfx) G.sfx.play('upgrade');
      S.lvFx = 1.6;      /* 升级特效计时 */
    }
    return ups;
  }

  /* ============ 战斗 ============ */
  function newBattle() {
    var st = stats();
    S.hero = {
      x: 0, y: 0, hp: st.hp, maxhp: st.hp, face: 1,
      atkCd: 0, skCd: [0, 0, 0], invuln: 0, hurt: 0,
      swing: 0            /* 挥砍动画剩余时间（秒），>0 表示正在挥武器 */
    };
    S.mobs = []; S.drops = []; S.nums = []; S.eff = [];
    S.waveT = 1.2; S.spawned = 0; S.map = D.MAPS[S.save.map] || D.MAPS[0];
    S.anim = { power: 0, powerFrom: 0 };
    /* 新手提示：只提示一次 */
    if (!S.save.tipMove) {
      S.save.tipMove = 1;
      S.hint = { txt: '拖动屏幕移动角色', t: 4 };
      S.arrow = { x: 0, y: 0, t: 5, kind: 'move' };
    }
  }

  function spawnMob(id) {
    var m = D.MONS.filter(function (x) { return x.id === id; })[0];
    if (!m) return;
    /* 精英/妖王登场：横幅 + 震屏 */
    if (m.boss) {
      if (G.sfx) G.sfx.play('boss');
      /* 妖王的名字本身就带"妖王"，别再拼一遍 */
      S.banner = { txt: (m.boss === 2 ? m.name : '精英 · ' + m.name), t: 2.0, col: m.boss === 2 ? '#ff5a6e' : '#ffd23a' };
      S.shake = 0.45;
    }
    var a = rnd(0, 6.2832), r = rnd(300, 390);   /* 别刷太远，开局 1 秒就能接上 */
    var lv = S.map.lv;
    var hp = m.hp * (1 + lv * 0.34);
    S.mobs.push({
      id: id, x: Math.cos(a) * r, y: Math.sin(a) * r,
      hp: hp, maxhp: hp, atk: m.atk * (1 + lv * 0.3), spd: m.spd,
      xp: m.xp, coin: m.coin, r: m.r, col: m.col, boss: m.boss, drop: m.drop,
      hit: 0, face: 1
    });
  }

  function waveMobList() {
    var m = S.map;
    var list = [];
    var n = m.mobs[Math.min(m.mobs.length - 1, Math.floor(S.wave / 2))] || m.mobs[0];
    return n;
  }

  function updateBattle(dt) {
    var s = S.save, h = S.hero, st = S.stats;
    if (!st) st = S.stats = stats();

    /* —— 自动战斗：10 秒无操作接管 —— */
    var idle = (Date.now() - G.T.lastInput) > 10000;
    if (idle && !S.autoOn) {
      S.autoOn = true;
      if (!S.save.tipAuto) {
        S.save.tipAuto = 1;
        S.hint = { txt: '10 秒不动会自动战斗|点右上角 ✕ 可取消', t: 4.5 };
      }
    }
    if (!idle && S.autoOn && S.autoManual) { S.autoOn = false; }

    /* —— 移动 ——
       传奇类手游的角色是自动走向敌人的（玩家只负责放技能）。
       原来只有「10 秒无操作自动战斗」时才走 → 开局干等 9 秒才打上第一只，
       手感很闷。
       现在的规则：
         拖动中   → 按手指方向走（玩家优先，能拉扯、能捡掉落）
         没在拖   → 自动走向最近的怪（游戏永远在动）
         自动战斗 → 额外自动放技能 */
    var tx = null, ty = null;
    if (G.T.down) {
      var dx = G.T.dx, dy = G.T.dy;
      var len = Math.sqrt(dx * dx + dy * dy);
      if (len > 6) { tx = h.x + dx / len * 200; ty = h.y + dy / len * 200; }
    } else {
      var near = nearest(h, 9999);
      if (near) { tx = near.x; ty = near.y; }
    }
    var spd = 250 * (1 + st.aspd * 0.01);
    if (tx !== null) {
      var a = Math.atan2(ty - h.y, tx - h.x);
      h.x += Math.cos(a) * spd * dt;
      h.y += Math.sin(a) * spd * dt;
      h.face = Math.cos(a) >= 0 ? 1 : -1;
    }

    /* —— 波次 —— */
    S.waveT -= dt;
    if (S.waveT <= 0 && S.mobs.length === 0) {
      if (S.wave >= S.map.waves) {
        /* 通关 → 记录 + 首通奖励 → 下一张图 */
        s.cleared = s.cleared || {};
        if (!s.cleared[S.map.id]) {
          s.cleared[S.map.id] = true;
          var rw = 200 + S.map.id * 260;
          s.coins += rw;
          s.gems = s.gems || {};
          var gdw = D.GEMS.filter(function (x) { return x.id === 'gem_atk'; })[0];
          if (gdw) s.gems[gdw.id] = (s.gems[gdw.id] || 0) + S.map.id;
          toast('首通奖励：灵果 +' + rw + '　红宝石 +' + S.map.id);
        }
        s.maxWave = Math.max(s.maxWave, s.map + 1);
        s.map = Math.min(D.MAPS.length - 1, s.map + 1);
        S.map = D.MAPS[s.map];
        S.wave = 0; S.waveT = 2.0;
        toast('进入 ' + S.map.name);
      } else {
        S.wave++; S.waveT = 2.2;
        var alive = S.mobs.length;
        if (alive === 0) toast('第 ' + S.wave + ' 波');
      }
    }
    if (S.waveT > 1.6 && S.mobs.length < 14) {
      var id = waveMobList();
      S.spawnT = (S.spawnT || 0) - dt;
      if (S.spawnT <= 0) {
        spawnMob(id); S.spawnT = 0.34;
        if (S.wave >= S.map.waves - 1 && Math.random() < 0.10) spawnMob(S.map.elite);
        if (S.map.boss && S.wave >= S.map.waves) spawnMob(S.map.boss);
      }
    }

    /* —— 普攻 —— */
    h.atkCd -= dt;
    if (h.swing > 0) h.swing -= dt;
    if (h.atkCd <= 0) {
      var wpn = equippedWeapon();
      var tg = nearest(h, wpn.range);
      if (tg) {
        h.atkCd = wpn.cd;
        /* 面向目标 + 起手挥砍 */
        h.face = tg.x >= h.x ? 1 : -1;
        h.swing = skinOf(S.save.wskin).swing ? skinOf(S.save.wskin).swing.dur : 0.24;
        var cboost = S.comboBuff > 0 ? 1.1 : 1;
        deal(tg, wpn.atk * wpn.dmgMul * (1 + (st.crit - 5) * 0.004) * rnd(0.92, 1.08) * cboost, st, true);
      }
    }

    /* —— 技能（手动点 or 自动放）—— */
    for (var i = 0; i < 3; i++) {
      h.skCd[i] -= dt;
      var sk = D.SKILLS[i];
      var skLv = (S.save.skLv && S.save.skLv[i]) || 1;
      var skMul = 1 + (skLv - 1) * D.SK_DMG;
      if (h.skCd[i] <= 0 && (S.autoOn || S.skillQueued[i])) {
        var tgt = nearest(h, sk.range);
        if (tgt) {
          h.skCd[i] = sk.cd * (1 - (skLv - 1) * D.SK_CD);
          if (S.skillQueued[i]) S.skillQueued[i] = false;
          if (sk.aoe) {
            S.mobs.forEach(function (m) { if (dist(m, h) <= sk.range) deal(m, sk.dmg * (st.atk * 0.22) * skMul, st, false); });
            /* 旋风(1) = 风环扩散；妖火(2) = 火球爆开 */
            S.eff.push({ x: h.x, y: h.y, r: 0, r2: sk.range, t: 0.5, dur: 0.5, col: sk.col, kind: i === 1 ? 'wind' : 'fire' });
          } else {
            deal(tgt, sk.dmg * (st.atk * 0.30) * skMul, st, false);
            /* 剑气(0) = 从主角射出的一道光刃 */
            S.eff.push({ x: h.x, y: h.y - 14, tx: tgt.x, ty: tgt.y - 10, t: 0.28, dur: 0.28, col: sk.col, kind: 'beam' });
          }
        }
      }
    }

    /* —— 怪物行为 —— */
    S.mobs.forEach(function (m) {
      m.hit = Math.max(0, m.hit - dt);
      var d = dist(m, h);
      if (d > m.r + 20) {
        var a = Math.atan2(h.y - m.y, h.x - m.x);
        m.x += Math.cos(a) * m.spd * dt;
        m.y += Math.sin(a) * m.spd * dt;
        m.face = Math.cos(a) >= 0 ? 1 : -1;
      }
      if (d < m.r + 22 && h.invuln <= 0) {
        h.invuln = 0.55; h.hp -= m.atk; h.hurt = 0.22;
        S.nums.push({ x: h.x, y: h.y - 30, v: -18, t: 0.9, txt: '-' + Math.round(m.atk), col: '#ff6b6b' });
        if (h.hp <= 0) { h.hp = h.maxhp; toast('被击倒，妖气散尽'); }
      }
    });
    h.invuln = Math.max(0, h.invuln - dt);
    h.hurt = Math.max(0, h.hurt - dt);

    /* —— 死亡掉落 —— */
    S.mobs = S.mobs.filter(function (m) {
      if (m.hp > 0) return true;
      s.kills++; s.coins += m.coin;
      addXp(s, m.xp || 0);
      /* 图鉴点：普通怪 1、精英 5、妖王 20；首次击杀额外 +10
         （借鉴咸鱼之王的「微星」收集机制，但按休闲游戏的思路做轻） */
      s.dex = s.dex || {};
      var isNew = !s.dex[m.id];
      s.dex[m.id] = (s.dex[m.id] || 0) + 1;
      s.dexP = (s.dexP || 0) + (m.boss === 2 ? 20 : m.boss === 1 ? 5 : 1) + (isNew ? 10 : 0);
      if (isNew) toast('图鉴：' + m.name);
      S.nums.push({ x: m.x, y: m.y, v: -26, t: 1.0, txt: '+' + m.coin, col: '#ffd76a' });
      /* 掉落保底链：连续太久没出史诗就必出（不然非酋会彻底放弃）
         —— 调研口径的保底链：5-8 / 10-15 / 50 / 100 / 150-200 次 */
      /* 首杀必掉 —— 调研结论：前 3 分钟决定 80% 次日留存，
         第一件装备的到手时间越短，"操作→结果"的因果链越清晰 */
      var firstKill = !s.firstDrop;
      var pityHit = s.dry >= D.PITY_EPIC;
      /* 精英和妖王掉宝石（比装备低得多） */
      if (m.boss && Math.random() < (m.boss === 2 ? 0.85 : 0.35)) {
        var gd2 = weightedPick(D.GEMS);
        s.gems = s.gems || {};
        s.gems[gd2.id] = (s.gems[gd2.id] || 0) + 1;
        S.nums.push({ x: m.x, y: m.y - 40, v: -30, t: 1.4, txt: gd2.name + ' ×1', col: gd2.col, big: true });
        toast('获得 ' + gd2.name + '！');
      }
      if (firstKill || pityHit || Math.random() < m.drop * (1 + st.luck * D.LUCK_PER)) {
        var it = rollItem(st.luck);
        if (pityHit) {
          /* 保底：品质至少史诗（史诗/传说/神话 随机） */
          var qs = D.QUAL.filter(function (x) { return (D.QUAL_RANK[x.id] || 0) >= 3; });
          var q2 = qs.length ? qs[Math.floor(Math.random() * qs.length)] : D.QUAL[D.QUAL.length - 1];
          it = rollItem(st.luck, q2);
          s.dry = 0;
          toast('保底！必出 ' + it.qn);
        } else {
          s.dry++;
          if (D.QUAL_RANK && D.QUAL_RANK[it.q] !== undefined) {
            if (D.QUAL_RANK[it.q] >= 3) s.dry = 0;   /* 出了史诗就重置计数 */
          }
        }
        s.bag.push(it); s.items++;
        addToBag(it);
        if (firstKill) {
          s.firstDrop = 1;
          if (G.sfx) G.sfx.play('rare');
          toast('第一件装备！');
        } else {
          if (G.sfx) G.sfx.play((D.QUAL_RANK[it.q] || 0) >= 3 ? 'rare' : 'drop');
        }
        S.drops.push({ x: m.x, y: m.y, it: it, t: 0 });
        S.nums.push({ x: m.x, y: m.y - 26, v: -30, t: 1.2, txt: it.qn + ' ' + it.slot, col: it.col, big: true });
        if (it.q === 'p' || it.q === 'o' || it.q === 'r') toast('获得 ' + it.qn + '！');
      }
      return false;
    });

    /* —— 掉落物自动吸取 —— */
    S.drops.forEach(function (d) {
      d.t += dt;
      var a = Math.atan2(h.y - d.y, h.x - d.x);
      var dd = dist(d, h);
      if (dd > 46) { d.x += Math.cos(a) * 420 * dt; d.y += Math.sin(a) * 420 * dt; }
    });
    var before = S.drops.length;
    S.drops = S.drops.filter(function (d) { return dist(d, h) > 40; });
    if (S.drops.length !== before) { /* 吸满自动进背包（rollItem 已 push） */ }

    /* —— 飘字 / 特效 —— */
    S.nums.forEach(function (n) { n.t -= dt; n.y += n.v * dt; });
    S.nums = S.nums.filter(function (n) { return n.t > 0; });
    S.eff.forEach(function (e) { e.t -= dt; e.r += (e.kind === 'ring' ? 260 : 140) * dt; });
    /* ⚠️ 过滤条件是 t > 0，所以 push 时 t 必须给正数（给 0 会被这一帧立刻删掉，
       特效一帧都显示不出来 —— 这个坑让三个技能从上线起就没特效）。 */
    S.eff = S.eff.filter(function (e) { return e.t > 0; });

    /* —— 战力跳变动画 —— */
    if (S.anim.power > 0) S.anim.power = Math.max(0, S.anim.power - dt);

    /* —— 自动拾取装备直接进背包（rollItem 已入包）—— */
  }

  function nearest(h, maxR) {
    var best = null, bd = maxR * maxR;
    for (var i = 0; i < S.mobs.length; i++) {
      var m = S.mobs[i], dx = m.x - h.x, dy = m.y - h.y, d = dx * dx + dy * dy;
      if (d < bd) { bd = d; best = m; }
    }
    return best;
  }
  function equippedWeapon() {
    var it = S.save.equip.weapon;
    if (it && it.wtype) {
      var w = D.WEAPONS[it.wtype];
      return { atk: it.atk, range: it.range, cd: it.cd, dmgMul: it.dmgMul };
    }
    return D.DAGGER;
  }
  function skinOf(id) {
    return D.WEAPON_SKIN.filter(function (x) { return x.id === id; })[0] || D.WEAPON_SKIN[0];
  }

  /* ---------- 装备图标按品质染色 ----------
     一张部位底图 × 品质色 = 装备图标。
     染色要离屏画布（source-atop 只染有像素的地方），
     染一次缓存起来，别每帧重画。 */
  function tintedIcon(slot, col) {
    if (!S.iconCache) return null;
    var key = slot + '_' + col;
    if (S.iconCache[key] !== undefined) return S.iconCache[key];
    var src = S.slotIcon && S.slotIcon[slot];
    if (!src || !G.createOffscreen) { S.iconCache[key] = null; return null; }
    var sz = 64;
    var tmp = G.createOffscreen(sz, sz);
    if (!tmp) { S.iconCache[key] = null; return null; }
    var tc = tmp.getContext('2d');
    if (!tc) { S.iconCache[key] = null; return null; }
    tc.clearRect(0, 0, sz, sz);
    tc.drawImage(src, 0, 0, sz, sz);
    tc.globalCompositeOperation = 'source-atop';
    tc.fillStyle = col;
    tc.fillRect(0, 0, sz, sz);
    S.iconCache[key] = tmp;
    return tmp;
  }

  /* ---------- 美术资源预载 ----------
     图没加载完之前，游戏照常跑（程序化画的小人和色条），
     图来了自动换成贴图版 —— 不用等图，不用 loading 界面。 */
  function preloadArt() {
    if (!G.loadImgs) return;
    var list = [];
    if (D.HERO_IMG) {
      if (D.HERO_IMG.m) list.push({ key: 'm', path: 'assets/' + D.HERO_IMG.m });
      if (D.HERO_IMG.f) list.push({ key: 'f', path: 'assets/' + D.HERO_IMG.f });
    }
    D.WEAPON_SKIN.forEach(function (w) {
      if (w.img) list.push({ key: w.id, path: 'assets/' + w.img });
    });
    if (D.CHAR_SKIN) {
      for (var ck in D.CHAR_SKIN) {
        var cs = D.CHAR_SKIN[ck];
        if (cs.img) list.push({ key: cs.id, path: 'assets/' + cs.img });
      }
    }
    if (D.PETS) {
      for (var pk in D.PETS) {
        var ps = D.PETS[pk];
        if (ps.img) list.push({ key: 'pet_' + ps.id, path: 'assets/' + ps.img });
      }
    }
    /* 怪物/地图贴图直接从数据表推导 —— 往 MONS/MAPS 加一条就自动加载对应图，
       不用再回来改代码维护两张映射表 */
    if (D.MONS) {
      D.MONS.forEach(function (m) { list.push({ key: m.id, path: 'assets/mob/' + m.id + '.png' }); });
    }
    /* 地图不加载贴图：地面是程序化绘制的（无缝/零包体），贴图平铺方案已否掉 */
    /* 装备部位图标（一张底图按品质染色） */
    if (D.SLOT_ICON) {
      for (var ik in D.SLOT_ICON) {
        if (D.SLOT_ICON[ik].img) list.push({ key: 'ico_' + ik, path: 'assets/' + D.SLOT_ICON[ik].img });
      }
    }
    G.loadImgs(list, function (out) {
      S.heroImg = { m: out['m'] || null, f: out['f'] || null };
      S.wskinImg = out;
      /* 人物皮肤贴图（cs1~cs4），跟武器贴图分开存 */
      S.charImg = {};
      if (D.CHAR_SKIN) for (var ck2 in D.CHAR_SKIN) S.charImg[D.CHAR_SKIN[ck2].id] = out[D.CHAR_SKIN[ck2].id] || null;
      /* 宠物贴图 */
      S.petImg = {};
      if (D.PETS) for (var pk2 in D.PETS) S.petImg[D.PETS[pk2].id] = out['pet_' + D.PETS[pk2].id] || null;
      /* 怪物贴图单独拎出来，避免和武器的 key 混在一起 */
      S.mobImg = {}; S.slotIcon = {};
      for (var k in out) {
        if (D.MONS) {
          var isMob = false;
          D.MONS.forEach(function (m) { if (m.id === k) isMob = true; });
          if (isMob) { S.mobImg[k] = out[k]; continue; }
        }
        if (k.indexOf('ico_') === 0) S.slotIcon[k.slice(4)] = out[k];
      }
      S.iconCache = {};
    });
  }
  function deal(m, dmg, st, isBasic) {
    var crit = Math.random() * 100 < st.crit;
    if (crit) dmg *= (1 + st.critDmg / 100);
    if (isBasic) {
      if (G.sfx) G.sfx.play(crit ? 'crit' : 'hit');
      /* 连击：2 秒内连续命中就累加 —— 这类游戏最经典的爽点机制 */
      S.combo = (S.combo || 0) + 1;
      S.comboT = 2.0;
      if (S.combo > (S.comboBest || 0)) S.comboBest = S.combo;
      if (S.combo > 0 && S.combo % 10 === 0) {
        /* 每 10 连击：伤害 +10% 持续 5 秒 */
        S.comboBuff = 5.0;
        toast(S.combo + ' 连击！伤害 +10%');
        if (G.sfx) G.sfx.play('rare');
      }
    }
    m.hp -= dmg; m.hit = 0.14;
    S.nums.push({ x: m.x + rnd(-10, 10), y: m.y - 18, v: -34, t: 0.85, txt: (crit ? '暴 ' : '') + Math.round(dmg), col: crit ? '#ffd23a' : '#fff' });
    if (st.vamp > 0) S.hero.hp = Math.min(S.hero.maxhp, S.hero.hp + dmg * st.vamp / 100 * 0.4);
  }

  /* ============ 抽卡（广告）============ */
  function pull10() {
    var s = S.save, got = [];
    S.pullT = 0;              /* 翻牌动画计时 */
    if (G.sfx) G.sfx.play('pull');
    for (var i = 0; i < 10; i++) {
      s.pulls++;
      /* 6% 出宠物卡（已有宠物则折精粹） */
      if (Math.random() < 0.06) {
        var pc = rollPetCard(s);
        if (!s.pet) {
          if (G.sfx) G.sfx.play('pet');
          s.pet = { slot: pc.slot, at: Date.now() };
          s.petLv = 1; s.petMood = 70; s.petMoodAt = Date.now();
        }
        s.essence = (s.essence || 0) + (s.pet ? 10 : 0);
        got.push(pc);
        continue;
      }
      var forced = (s.pulls % 8 === 0);            // 每 8 次必出史诗以上（保底可见）
      var q = forced ? weightedPick(D.QUAL.filter(function (x) { return ['p', 'o', 'r'].indexOf(x.id) >= 0; }))
        : weightedPick(D.QUAL.filter(function (x) { return ['w', 'g', 'b', 'p'].indexOf(x.id) >= 0; }));
      var it = {
        uid: 'c' + s.pulls + '_' + i, q: q.id, qn: q.name, col: q.color,
        slot: pick(SLOT_KEYS),
        wtype: q.id === 'w' ? null : pick(['blade', 'sword', 'staff', 'fist']),
        aff: {}
      };
      var n = q.affix;
      var pool = Object.keys(D.AFFIX);
      for (var k = 0; k < n; k++) {
        var a2 = pick(pool);
        if (it.aff[a2] !== undefined) { k--; continue; }
        it.aff[a2] = irnd(D.AFFIX[a2].v[0], D.AFFIX[a2].v[1]);
      }
      if (it.slot === 'weapon') {
        var w = D.WEAPONS[it.wtype] || D.WEAPONS.blade;
        it.atk = Math.round(w.atk * q.mul * 1.1);
        it.range = w.range; it.cd = w.cd; it.dmgMul = w.dmgMul;
      }
      s.bag.push(it); got.push(it);
    }
    G.persist();
    return got;
  }

  /* ---------- 宠物卡 ----------
     宠物面板写着"去商店抽卡可以抽到宠物"，那就得真能抽到。
     每张卡 6% 概率是宠物；已有宠物时重复卡折成精粹。 */
  function rollPetCard(s) {
    var slot = pick(['beast', 'mount', 'pal']);
    var pd = D.PETS.filter(function (x) { return x.slot === slot; })[0];
    if (s.pet) {
      return { pet: true, dup: true, slot: slot, qn: pd.name + '·重复', col: '#6d675c', q: 'w' };
    }
    return { pet: true, slot: slot, qn: pd.name, col: '#7dff9b', q: 'r', pname: pd.name };
  }

  /* ============ 界面 ============ */
  function toast(t) { S.toast = t; S.toastT = 2.0; }

  /* 假榜单的数据（固定，跨存档不变） */
  var FAKE_NAMES = ['剑无痕', '逍遥客', '叶良辰', '一剑霜寒', '墨白', '孤星', '云中君',
    '半盏茶', '无名氏', '风起时', '青衫客', '落九霄', '不归人', '长安月',
    '白露', '断浪', '孤舟', '拾光', '南风过境', '小酌'];
  /* 阶梯跟着实际战力走（模拟：2 小时约 1700，长期能到上万），
     新玩家前期落在下半区 → 有往上爬的动力 */
  var FAKE_LADDER = [20000, 17000, 14000, 11500, 9500, 8000, 6800, 5800, 5000, 4300,
    3700, 3200, 2750, 2350, 2000, 1700, 1450, 1250, 1050, 900];

  /* ---- 按钮系统 ---- */
  /* 面板切换时**旧按钮必须清掉**。
     S 是个大对象，按钮都挂在上面；换个面板不清理的话，
     上个面板的按钮还会被点到 → 比如在「强化」面板点到残留的「造型」按钮就崩。
     而且按钮 key 有前缀关系（btnSk 是 btnSkin 的前缀），更要用前缀表统一管。 */
  var BTN_PREFIX = ['btn', 'slotBtn', 'bagItem', 'skUp', 'chBtn', 'skBtn', 'mapBtn'];
  function clearBtns() {
    for (var k in S) {
      for (var i = 0; i < BTN_PREFIX.length; i++) {
        if (k.indexOf(BTN_PREFIX[i]) === 0) { delete S[k]; break; }
      }
    }
  }

  /* hit(x, y, b)：b 是**按钮对象**（含 x/y/r），不是半径数字。
     ⚠️ 之前写成 hit(x,y,r) 却用 r.x → NaN 比较恒为 false → 所有按钮都点不动。 */
  function hit(x, y, b) {
    if (!b) return false;
    var dx = x - b.x, dy = y - b.y;
    return dx * dx + dy * dy <= b.r * b.r;
  }
  function hitRect(x, y, b) {
    if (!b) return false;
    return x > b.x - b.w / 2 - 8 && x < b.x + b.w / 2 + 8 && Math.abs(y - b.y) < b.h / 2 + 10;
  }

  /* ---------- 面板公共件（学成熟放置游戏的规范）----------
     返回按钮只能放左上 —— 右上 (W-40,40) 在微信胶囊底下点不到（张凯被困那次）。
     顶部基准吃安全区（刘海/胶囊），底部避开 Home 条。 */
  function panelTop() { return Math.max(46, ((G.SAFE ? G.SAFE.dTop : 0) + 16)); }
  function drawPanelHeader(title) {
    var ty = panelTop() + 6;
    S.btnBack = { x: 48, y: ty, r: 23 };
    G.circle(S.btnBack.x, S.btnBack.y, 21, 'rgba(255,255,255,.10)', 'rgba(255,255,255,.30)', 1.5);
    G.text('‹', S.btnBack.x + 1, S.btnBack.y + 2, 28, '#fff', 'center', true);
    G.text(title, 96, ty + 1, 22, '#ffd88e', 'left', true);
    return ty + 30;   /* 内容起始基准 */
  }
  function drawBackBar(toState) {
    var by = G.H - Math.max(34, ((G.SAFE ? G.SAFE.dBottom : 0) + 26));
    S.btnBack2 = { x: G.W / 2, y: by, r: 0, w: 300, h: 32, to: toState || 'battle' };
    G.round(G.W / 2 - 150, by - 16, 300, 32, 16, 'rgba(255,255,255,.07)', 'rgba(255,255,255,.22)', 1);
    G.text('▲  返回主界面', G.W / 2, by, 12.5, '#c9bda4', 'center', true);
  }

  /* ---------- 视觉设计系统（对标咸鱼之王/寻道大千档次的仙侠风）----------
     深墨底 + 金色描边 + 卡片化 + 按钮有渐变厚度。以前全是裸文字灰框 = 糊弄，
     张凯点名要质量，这套是底线不是上限 */
  var TH = {
    bg0: '#100e0c', bg1: '#1b1713',          /* 面板底：上深下微亮 */
    gold: '#ffd88e', goldD: '#a8823c', goldL: '#ffe9bf',
    ink: '#e8ddc6', ink2: '#b3a88f', ink3: '#7d7460',
    red: '#e05a4a', jade: '#7ec4a0', hp: '#d84a4a'
  };
  function lin(x0, y0, x1, y1, c0, c1) {
    var g = ctx.createLinearGradient(x0, y0, x1, y1);
    g.addColorStop(0, c0); g.addColorStop(1, c1);
    return g;
  }
  /* 面板底 + 装饰头：暗化渐变底、金色双线夹标题、左侧 ‹ 返回 */
  function panelChrome(title) {
    ctx.fillStyle = lin(0, 0, 0, G.H, TH.bg0, TH.bg1);
    ctx.fillRect(0, 0, G.W, G.H);
    /* 顶部装饰带（吃安全区） */
    var hy = panelTop() + 8;
    ctx.fillStyle = 'rgba(212,169,78,.06)';
    ctx.fillRect(0, 0, G.W, hy + 26);
    S.btnBack = { x: 48, y: hy, r: 23 };
    G.circle(S.btnBack.x, S.btnBack.y, 21, 'rgba(255,216,142,.10)', 'rgba(255,216,142,.45)', 1.5);
    G.text('‹', S.btnBack.x + 1, S.btnBack.y + 2, 28, TH.gold, 'center', true);
    /* 标题居中 + 左右金线装饰 */
    G.text(title, G.W / 2 + 14, hy + 1, 24, TH.gold, 'center', true);
    var tw = title.length * 26 + 60;
    ctx.strokeStyle = 'rgba(212,169,78,.55)'; ctx.lineWidth = 1.5;
    ctx.beginPath(); ctx.moveTo(G.W / 2 + 14 - tw / 2, hy); ctx.lineTo(102, hy); ctx.stroke();
    ctx.beginPath(); ctx.moveTo(G.W / 2 + 14 + tw / 2, hy); ctx.lineTo(G.W - 96, hy); ctx.stroke();
    G.circle(102, hy, 2.5, TH.gold); G.circle(G.W - 96, hy, 2.5, TH.gold);
    return hy + 34;
  }
  /* 金色主按钮（渐变 + 描边 + 顶部高光） */
  function btnGold(x, y, w, h, label, sub) {
    ctx.fillStyle = lin(0, y, 0, y + h, '#8a6428', '#5f441c');
    G.round(x, y, w, h, h * 0.32, null, '#c9a04c', 2);
    ctx.fillStyle = lin(0, y, 0, y + h, '#9c7330', '#6b4d20');
    G.round(x + 2, y + 2, w - 4, h - 4, h * 0.3, null, null, 0);
    ctx.strokeStyle = 'rgba(255,233,191,.35)'; ctx.lineWidth = 1;
    ctx.beginPath(); ctx.moveTo(x + 10, y + 4); ctx.lineTo(x + w - 10, y + 4); ctx.stroke();
    G.text(label, x + w / 2, y + h / 2 + (sub ? -4 : 1), 17, TH.goldL, 'center', true);
    if (sub) G.text(sub, x + w / 2, y + h / 2 + 13, 10.5, '#d9b98a', 'center');
  }
  /* 幽灵按钮（次级） */
  function btnGhost(x, y, w, h, label) {
    G.round(x, y, w, h, h * 0.32, 'rgba(255,255,255,.05)', 'rgba(255,255,255,.22)', 1.2);
    G.text(label, x + w / 2, y + h / 2 + 1, 13, TH.ink2, 'center', true);
  }
  /* 通用卡片：微亮底 + 细边 + 可选强调色边 */
  function card(x, y, w, h, accent, glow) {
    G.round(x, y, w, h, 10, lin(0, y, 0, y + h, 'rgba(255,255,255,.055)', 'rgba(255,255,255,.02)'),
      accent || 'rgba(255,255,255,.12)', accent ? 1.8 : 1);
    if (glow) {
      ctx.save();
      ctx.shadowColor = glow; ctx.shadowBlur = 14;
      G.round(x + 1, y + 1, w - 2, h - 2, 9, null, accent, 1.8);
      ctx.restore();
    }
  }

  /* ---------- 程序化地面 ----------
     底色 + 按世界坐标哈希散落的装饰（石头/草/枯枝）。
     用坐标做哈希 → 同一个世界坐标永远长一样，但整体无限、无缝、无重复感。 */
  function hash2(x, y, k) {
    var n = (x * 374761393 + y * 668265263 + (k || 0) * 1442695040) | 0;
    n = (n ^ (n >> 13)) * 1274126177;
    return ((n ^ (n >> 16)) >>> 0) / 4294967296;
  }
  function drawGround(sx, sy) {
    var mp = S.map;
    /* ⚠️ 这里已经在 ctx.translate(sx, sy) 之后了 —— 屏幕原点是世界坐标 (-sx, -sy)，
       直接 fillRect(0,0,W,H) 只会画到世界原点那一片，屏幕会露底。 */
    ctx.fillStyle = mp.ground || '#2b2f26';
    ctx.fillRect(-sx, -sy, G.W, G.H);

    /* 大块的深浅斑（打破纯色） */
    var CELL = 150;
    var cx0 = Math.floor((-sx) / CELL) - 1, cx1 = Math.ceil((G.W - sx) / CELL) + 1;
    var cy0 = Math.floor((-sy) / CELL) - 1, cy1 = Math.ceil((G.H - sy) / CELL) + 1;
    for (var cx = cx0; cx <= cx1; cx++) {
      for (var cy = cy0; cy <= cy1; cy++) {
        var px = cx * CELL + hash2(cx, cy, 1) * CELL;
        var py = cy * CELL + hash2(cx, cy, 2) * CELL;
        var r = 26 + hash2(cx, cy, 3) * 30;
        ctx.fillStyle = mp.ground2 || 'rgba(255,255,255,.04)';
        ctx.globalAlpha = 0.55;
        ctx.beginPath();
        ctx.ellipse(px, py, r, r * 0.6, hash2(cx, cy, 4) * 3, 0, 6.2832);
        ctx.fill();
        ctx.globalAlpha = 1;
      }
    }

    /* 装饰物：碎石 / 草 / 枯枝，三种形态随机分布 */
    var dec = mp.deco || ['#555'];
    for (var dx = cx0; dx <= cx1; dx++) {
      for (var dy = cy0; dy <= cy1; dy++) {
        var hv = hash2(dx, dy, 7);
        if (hv > 0.42) continue;           /* 一部分格子才有装饰 */
        var kx = dx * CELL + hash2(dx, dy, 8) * CELL;
        var ky = dy * CELL + hash2(dx, dy, 9) * CELL;
        var kind = Math.floor(hash2(dx, dy, 10) * 3);
        var col = dec[kind] || dec[0];
        var s2 = 0.7 + hash2(dx, dy, 11) * 0.8;
        if (kind === 0) {
          /* 碎石：两三个小圆 */
          for (var q = 0; q < 3; q++) {
            var ox = (hash2(dx * 3 + q, dy, 12) - 0.5) * 22;
            var oy = (hash2(dx, dy * 3 + q, 13) - 0.5) * 14;
            G.circle(kx + ox, ky + oy, (2.2 + hash2(dx + q, dy + q, 14) * 2.6) * s2, col);
          }
        } else if (kind === 1) {
          /* 草：三根短竖线 */
          ctx.strokeStyle = col; ctx.lineWidth = 1.6 * s2; ctx.lineCap = 'round';
          for (var b = 0; b < 3; b++) {
            var ang = -1.9 + hash2(dx, dy + b, 15) * 0.9;
            var len = (6 + hash2(dx + b, dy, 16) * 6) * s2;
            var bx = kx + (b - 1) * 4 * s2;
            ctx.beginPath();
            ctx.moveTo(bx, ky);
            ctx.lineTo(bx + Math.cos(ang) * len, ky + Math.sin(ang) * len);
            ctx.stroke();
          }
        } else {
          /* 枯枝：一小段横线 */
          ctx.strokeStyle = col; ctx.lineWidth = 2.4 * s2; ctx.lineCap = 'round';
          ctx.beginPath();
          ctx.moveTo(kx - 7 * s2, ky);
          ctx.lineTo(kx + 8 * s2, ky + (hash2(dx, dy, 17) - 0.5) * 6);
          ctx.stroke();
        }
      }
    }

    /* 每张图的专属地面特征（mp.fx）—— 还是程序化（无缝/零包体/跟相机滚），
       但让 7 张图一眼能分出来：白骨/竹叶/霜裂/余烬/星光。
       ⚠️ 余烬和星光带呼吸动画，用 Date.now()，别用会倒退的计时器。 */
    var fx = mp.fx;
    if (fx) {
      var FT = Date.now() / 1000;
      var FCELL = 230;
      var gx0 = Math.floor((-sx) / FCELL) - 1, gx1 = Math.ceil((G.W - sx) / FCELL) + 1;
      var gy0 = Math.floor((-sy) / FCELL) - 1, gy1 = Math.ceil((G.H - sy) / FCELL) + 1;
      for (var gx = gx0; gx <= gx1; gx++) {
        for (var gy = gy0; gy <= gy1; gy++) {
          if (hash2(gx, gy, 21) > 0.55) continue;
          var qx = gx * FCELL + hash2(gx, gy, 22) * FCELL;
          var qy = gy * FCELL + hash2(gx, gy, 23) * FCELL;
          var fs = 0.7 + hash2(gx, gy, 24) * 0.7;
          var ra = hash2(gx, gy, 25) * 6.2832;
          if (fx === 'bone') {
            /* 白骨：两三节淡色骨节 + 碎屑（乱葬岗） */
            ctx.lineCap = 'round';
            for (var bn = 0; bn < 2 + Math.floor(hash2(gx, gy, 26) * 2); bn++) {
              var bl = (7 + hash2(gx + bn, gy, 27) * 7) * fs;
              var ba = ra + bn * 0.9 - 0.45;
              var bx2 = qx + (bn - 0.5) * 10 * fs;
              ctx.strokeStyle = bn % 2 ? '#a8a294' : '#b8b2a4';
              ctx.lineWidth = 3.4 * fs;
              ctx.beginPath();
              ctx.moveTo(bx2 - Math.cos(ba) * bl / 2, qy - Math.sin(ba) * bl / 2);
              ctx.lineTo(bx2 + Math.cos(ba) * bl / 2, qy + Math.sin(ba) * bl / 2);
              ctx.stroke();
            }
            ctx.fillStyle = '#8f8a7c';
            ctx.globalAlpha = 0.6;
            G.circle(qx + 12 * fs, qy + 8 * fs, 1.6 * fs, '#8f8a7c');
            ctx.globalAlpha = 1;
          } else if (fx === 'leaf') {
            /* 竹叶：几片两头尖的细长叶，深浅两绿（竹林） */
            for (var lf = 0; lf < 3; lf++) {
              var la = ra + hash2(gx, gy + lf, 28) * 1.6 - 0.8;
              var ll = (9 + hash2(gx + lf, gy, 29) * 7) * fs;
              var lw = ll * 0.22;
              var lx2 = qx + (hash2(gx * 5 + lf, gy, 30) - 0.5) * 34;
              var ly2 = qy + (hash2(gx, gy * 5 + lf, 31) - 0.5) * 34;
              ctx.save();
              ctx.translate(lx2, ly2);
              ctx.rotate(la);
              ctx.fillStyle = lf % 2 ? '#4e7a36' : '#6f9a4c';
              ctx.globalAlpha = 0.85;
              ctx.beginPath();
              ctx.moveTo(-ll / 2, 0);
              ctx.quadraticCurveTo(0, -lw, ll / 2, 0);
              ctx.quadraticCurveTo(0, lw, -ll / 2, 0);
              ctx.fill();
              ctx.restore();
              ctx.globalAlpha = 1;
            }
          } else if (fx === 'frost') {
            /* 霜裂：淡白折线裂纹 + 冰晶亮点（寒霜） */
            ctx.strokeStyle = 'rgba(215,232,248,.34)';
            ctx.lineWidth = 1.4 * fs;
            ctx.lineCap = 'round';
            ctx.beginPath();
            var cx2 = qx, cy2 = qy;
            ctx.moveTo(cx2, cy2);
            for (var fr = 0; fr < 3; fr++) {
              cx2 += Math.cos(ra + fr * 0.85) * (13 + hash2(gx + fr, gy, 32) * 9) * fs;
              cy2 += Math.sin(ra + fr * 0.85) * (9 + hash2(gx, gy + fr, 33) * 7) * fs;
              ctx.lineTo(cx2, cy2);
            }
            ctx.stroke();
            ctx.fillStyle = 'rgba(224,240,252,.75)';
            G.circle(qx, qy, 1.5 * fs, 'rgba(224,240,252,.75)');
          } else if (fx === 'ember') {
            /* 余烬：橙色光斑缓慢呼吸 + 两粒火星（熔岩） */
            var pu = 0.45 + 0.32 * Math.sin(FT * 1.6 + hash2(gx, gy, 34) * 6.2832);
            var er = 24 * fs;
            var eg = ctx.createRadialGradient(qx, qy, 0, qx, qy, er);
            eg.addColorStop(0, 'rgba(224,112,58,' + (0.30 * pu + 0.12).toFixed(3) + ')');
            eg.addColorStop(1, 'rgba(224,112,58,0)');
            ctx.fillStyle = eg;
            ctx.beginPath();
            ctx.arc(qx, qy, er, 0, 6.2832);
            ctx.fill();
            ctx.fillStyle = '#f0a060';
            ctx.globalAlpha = 0.5 + pu * 0.4;
            G.circle(qx - 8 * fs, qy - 5 * fs, 1.6 * fs, '#f0a060');
            G.circle(qx + 7 * fs, qy + 6 * fs, 1.2 * fs, '#f0a060');
            ctx.globalAlpha = 1;
          } else if (fx === 'star') {
            /* 星光：小亮点闪烁，偶尔一颗带十字光（落星） */
            var tw = 0.35 + 0.55 * (0.5 + 0.5 * Math.sin(FT * 2.1 + hash2(gx, gy, 35) * 6.2832));
            var big = hash2(gx, gy, 36) > 0.72;
            var sr = (big ? 2.6 : 1.4) * fs;
            ctx.fillStyle = 'rgba(216,228,255,' + (0.35 + tw * 0.55).toFixed(3) + ')';
            ctx.beginPath();
            ctx.arc(qx, qy, sr, 0, 6.2832);
            ctx.fill();
            if (big) {
              ctx.strokeStyle = 'rgba(216,228,255,' + (tw * 0.5).toFixed(3) + ')';
              ctx.lineWidth = 1;
              ctx.beginPath();
              ctx.moveTo(qx - sr * 4, qy); ctx.lineTo(qx + sr * 4, qy);
              ctx.moveTo(qx, qy - sr * 4); ctx.lineTo(qx, qy + sr * 4);
              ctx.stroke();
            }
          }
        }
      }
    }
  }

  function drawBattle() {
    var h = S.hero, st = S.stats;
    var camX = h.x, camY = h.y;
    var sx = G.W / 2 - camX * G.SCALE, sy = G.H / 2 - camY * G.SCALE;

    /* 地面 */
    ctx.fillStyle = '#2b2f26'; ctx.fillRect(0, 0, G.W, G.H);
    ctx.save();
    if (S.shake > 0) {
      var sh = S.shake * 9;
      ctx.translate(sx + rnd(-sh, sh), sy + rnd(-sh, sh));
    } else {
      ctx.translate(sx, sy);
    }
    drawGround(sx, sy);

    /* 掉落物：品质光柱 + 图标 + 弹出动画 */
    S.drops.forEach(function (d) {
      var rk = D.QUAL_RANK[d.it.q] || 0;
      var pop = Math.min(1, d.t / 0.25);      /* 弹出 */
      var sc = 0.5 + pop * 0.5 + Math.max(0, 1 - d.t * 2) * 0.35;
      /* 光柱：史诗以上才明显 */
      if (rk >= 2) {
        var gg = ctx.createLinearGradient(d.x, d.y - 46, d.x, d.y + 6);
        gg.addColorStop(0, 'rgba(255,255,255,0)');
        gg.addColorStop(1, d.it.col);
        ctx.save();
        ctx.globalAlpha = (rk >= 3 ? 0.55 : 0.3) * pop;
        ctx.fillStyle = gg;
        ctx.fillRect(d.x - 7 * sc, d.y - 46, 14 * sc, 52);
        ctx.restore();
      }
      /* 图标 */
      var img = null;
      if (d.it.wtype) {
        var sk = D.WEAPON_SKIN.filter(function (w) { return w.w === d.it.wtype; })[0];
        if (sk && S.wskinImg) img = S.wskinImg[sk.id];
      }
      ctx.save();
      ctx.globalAlpha = pop;
      if (img) {
        var ww = img.width / img.height * 30 * sc;
        ctx.drawImage(img, d.x - ww / 2, d.y - 26 * sc, ww, 30 * sc);
      } else {
        G.circle(d.x, d.y - 9 * sc, 9 * sc, d.it.col, 'rgba(255,255,255,.5)', 1.5);
        G.circle(d.x - 3 * sc, d.y - 12 * sc, 2.4 * sc, 'rgba(255,255,255,.75)');
      }
      ctx.restore();
      /* 名字 */
      G.text(d.it.qn, d.x, d.y - 32 * sc, 12 + (rk >= 3 ? 2 : 0), d.it.col, 'center', true);
    });

    /* 怪物 */
    S.mobs.forEach(function (m) {
      var r = m.r * (m.boss === 2 ? 1.5 : m.boss === 1 ? 1.15 : 1);
      var img = S.mobImg && S.mobImg[m.id];
      var top = m.y - r;              /* 血条和标签的基准高度 */
      if (img) {
        var hh = r * 2.6;             /* 贴图高度 */
        var ww = img.width / img.height * hh;
        top = m.y - hh + r * 0.55;
        ctx.save();
        if (m.hit > 0) ctx.globalAlpha = 0.8;
        ctx.drawImage(img, m.x - ww / 2, top, ww, hh);
        ctx.restore();
        if (m.hit > 0) {              /* 受击闪白 */
          ctx.save();
          ctx.globalAlpha = Math.min(1, m.hit / 0.14) * 0.45;
          G.circle(m.x, m.y - r * 0.9, r * 0.85, '#fff');
          ctx.restore();
        }
      } else {
        /* 没贴图 → 回退到原来的圆球 */
        G.circle(m.x, m.y, r, m.hit > 0 ? '#fff' : m.col);
        G.circle(m.x - r * 0.32, m.y - r * 0.18, r * 0.15, '#1a1a1a');
        G.circle(m.x + r * 0.32, m.y - r * 0.18, r * 0.15, '#1a1a1a');
      }
      if (m.boss) {
        G.text(m.id === 'b1' ? '妖王' : '精英', m.x, top - 14, 14, '#ffd23a', 'center', true);
      }
      var bw = r * 1.7;
      G.bar(m.x - bw / 2, top - 7, bw, 5, m.hp / m.maxhp, '#e0483f', 'rgba(0,0,0,.5)');
    });

    /* 主角 */
    var sk = D.CHAR_SKIN.filter(function (x) { return x.id === S.save.skin; })[0] || D.CHAR_SKIN[0];
    /* 装备品质光环：身上最高品质是什么色，身上就发什么光 */
    var topQ = 0, topC = null;
    for (var ek in S.save.equip) {
      var ei = S.save.equip[ek];
      if (!ei) continue;
      var er = D.QUAL_RANK[ei.q] || 0;
      if (er > topQ) { topQ = er; topC = ei.col; }
    }
    if (topC && topQ >= 2) {
      var gq = ctx.createRadialGradient(h.x, h.y - 16, 4, h.x, h.y - 16, 34);
      gq.addColorStop(0, topC);
      gq.addColorStop(1, 'rgba(0,0,0,0)');
      ctx.save();
      ctx.globalAlpha = 0.16 + 0.05 * Math.sin(Date.now() / 420);
      ctx.fillStyle = gq;
      ctx.beginPath(); ctx.arc(h.x, h.y - 16, 34, 0, 6.2832); ctx.fill();
      ctx.restore();
    }
    /* 优先用当前人物皮肤的贴图，没有才回退到性别定妆图 */
    var heroImg = (S.charImg && S.charImg[S.save.skin]) || (S.heroImg && S.heroImg[S.save.sex]);
    if (heroImg) {
      /* 贴图版：贴图是「脚底对齐」的，脚落在角色坐标上 */
      var hh = D.HERO_H;
      var hw = heroImg.width / heroImg.height * hh;
      ctx.save();
      if (h.hurt > 0) ctx.globalAlpha = 0.75;
      ctx.drawImage(heroImg, h.x - hw / 2, h.y - hh + 6, hw, hh);
      ctx.restore();
    } else {
      /* 没图（包还没带图 / 图加载失败）→ 回退程序化小人，不能黑屏 */
      G.circle(h.x, h.y, 17, h.hurt > 0 ? '#fff' : sk.col);
      G.circle(h.x, h.y - 5, 15, sk.hair);
      G.circle(h.x - 6 + h.face * 2, h.y - 4, 2.6, '#fff');
    }
    G.bar(h.x - 24, h.y - 76, 48, 6, h.hp / h.maxhp, '#4ad07a', 'rgba(0,0,0,.5)');

    /* 武器（贴图层）：握把对齐手的位置，挥砍时按 swing 轨迹转 */
    var wsk = skinOf(S.save.wskin);
    var wImg = S.wskinImg && S.wskinImg[S.save.wskin];
    if (wImg && heroImg) {
      var wh = wsk.h || D.WEAPON_H;   /* 每把武器可以有自己的尺寸 */
      var ww = wImg.width / wImg.height * wh;
      /* 主角贴图左上角在 (h.x - hw/2, h.y - hh + 6)，锚点是贴图里的比例坐标 */
      var hx = (h.x - hw/2) + wsk.anchor.x * hw;
      var hy = (h.y - hh + 6) + wsk.anchor.y * hh;
      var rot = wsk.rot;
      var pr = 0;
      if (h.swing > 0 && wsk.swing) {
        pr = 1 - h.swing / wsk.swing.dur;      /* 0 起手 → 1 砍完 */
        /* from/to 是相对待机角的增量 */
        rot = wsk.rot + wsk.swing.from + (wsk.swing.to - wsk.swing.from) * pr;
      }
      ctx.save();
      ctx.translate(hx, hy);
      ctx.rotate(rot);
      /* 握把点挪到原点：图片左上角 = -grip × 尺寸 */
      ctx.drawImage(wImg, -wsk.grip.x * ww, -wsk.grip.y * wh, ww, wh);
      ctx.restore();

      /* 刀光：挥砍时在身前画一道弧 —— 纯程序化，零包体 */
      if (pr > 0 && wsk.swing) {
        ctx.save();
        ctx.globalAlpha = Math.max(0, 1 - pr) * 0.9;
        ctx.strokeStyle = wsk.trail;
        ctx.lineWidth = 4 + 7 * (1 - pr);
        ctx.lineCap = 'round';
        ctx.beginPath();
        var a0 = wsk.rot + wsk.swing.from - 0.45;
        var a1 = wsk.rot + wsk.swing.from + (wsk.swing.to - wsk.swing.from) * pr;
        ctx.arc(h.x, h.y - 16, 42, a0, a1, false);
        ctx.stroke();
        ctx.restore();
      }
    } else {
      /* 没武器图 → 画原来的小色条 */
      G.round(h.x + h.face * 16, h.y - 4, 22, 4, 2, wsk.col);
    }

    /* 特效 */
    S.eff.forEach(function (e) {
      var dur = e.dur || 0.45;
      var k = 1 - e.t / dur;                 /* 1 → 0 */
      if (k <= 0) { ctx.globalAlpha = 1; return; }
      ctx.save();
      if (e.kind === 'beam') {
        /* 剑气：一道从主角射向目标的光刃 */
        ctx.globalAlpha = k;
        var dx = e.tx - e.x, dy = e.ty - e.y, len = Math.sqrt(dx * dx + dy * dy);
        var ux = dx / len, uy = dy / len;
        ctx.strokeStyle = e.col;
        ctx.lineWidth = 5 + 12 * k;
        ctx.lineCap = 'round';
        ctx.beginPath();
        ctx.moveTo(e.x, e.y);
        ctx.lineTo(e.x + ux * len * Math.min(1, (1 - k) * 3.2), e.y + uy * len * Math.min(1, (1 - k) * 3.2));
        ctx.stroke();
        ctx.globalAlpha = k * 0.85;
        ctx.strokeStyle = '#fff';
        ctx.lineWidth = 2.5;
        ctx.stroke();
      } else if (e.kind === 'wind') {
        /* 旋风：一圈扩散的风弧 */
        var rr = e.r2 * Math.min(1, (1 - k) * 2.6);
        ctx.globalAlpha = Math.min(1, k * 1.15);
        ctx.strokeStyle = e.col;
        ctx.lineWidth = 4 + 6 * k;
        for (var a = 0; a < 4; a++) {
          ctx.beginPath();
          ctx.arc(e.x, e.y, rr, a * 2.09 + (1 - k) * 1.6, a * 2.09 + (1 - k) * 1.6 + 1.1);
          ctx.stroke();
        }
      } else if (e.kind === 'fire') {
        /* 妖火：一团炸开的火 */
        var fr = (e.r2 || 120) * 0.52 * (0.4 + k * 0.9);
        ctx.globalAlpha = k * 0.85;
        var fg = ctx.createRadialGradient(e.x, e.y, 2, e.x, e.y, fr);
        fg.addColorStop(0, '#fff3c4');
        fg.addColorStop(0.45, e.col);
        fg.addColorStop(1, 'rgba(0,0,0,0)');
        ctx.fillStyle = fg;
        ctx.beginPath(); ctx.arc(e.x, e.y, fr, 0, 6.2832); ctx.fill();
        /* 火星 */
        ctx.globalAlpha = k;
        ctx.fillStyle = e.col;
        for (var f = 0; f < 7; f++) {
          var fa = f * 0.897 + (1 - k) * 2;
          var fd = fr * (0.7 + (f % 3) * 0.25);
          ctx.beginPath();
          ctx.arc(e.x + Math.cos(fa) * fd, e.y + Math.sin(fa) * fd * 0.6, 3 + (f % 3), 0, 6.2832);
          ctx.fill();
        }
      } else {
        /* 旧特效：t 从 dur 开始倒计时 */
        ctx.globalAlpha = Math.max(0, e.t / dur);
        G.circle(e.x, e.y, e.r, null, e.col, 3);
      }
      ctx.globalAlpha = 1;
      ctx.restore();
    });

    /* 飘字 */
    S.nums.forEach(function (n) {
      ctx.globalAlpha = Math.min(1, n.t * 2);
      G.shadowText(n.txt, n.x, n.y, n.big ? 18 : 14, n.col, 'rgba(0,0,0,.8)');
      ctx.globalAlpha = 1;
    });
    ctx.restore();

    /* 登场横幅 */
    if (S.banner && S.banner.t > 0) {
      var bt = S.banner.t;
      var ba = Math.min(1, bt / 0.4);
      ctx.save();
      ctx.globalAlpha = ba;
      ctx.translate(G.W / 2, G.H * 0.36);
      var sc = 1 + (1 - Math.min(1, (2.0 - bt) / 0.25)) * 0.6;
      ctx.scale(sc, sc);
      G.shadowText(S.banner.txt, 0, 0, 30, S.banner.col, 'rgba(0,0,0,.9)');
      ctx.restore();
    }

    /* 连击数：右侧大字，越大越显眼 */
    if (S.combo > 1) {
      var cs2 = 1 + Math.min(0.6, S.combo / 60);
      ctx.save();
      ctx.translate(G.W - 100, G.H * 0.34);
      ctx.scale(cs2, cs2);
      ctx.globalAlpha = Math.min(1, S.comboT);
      G.shadowText(S.combo + ' 连击', 0, 0, 22, S.combo >= 20 ? '#ffd23a' : '#ffe2b0', 'rgba(0,0,0,.85)');
      ctx.restore();
    }
    /* 连击加成还在时的提示 */
    if (S.comboBuff > 0) {
      ctx.globalAlpha = Math.min(1, S.comboBuff / 1.2);
      G.shadowText('伤害 +10%', G.W - 100, G.H * 0.34 + 28, 13, '#ffd23a', 'rgba(0,0,0,.85)');
      ctx.globalAlpha = 1;
    }
    /* 受击红闪 */
    if (h.hurt > 0) {
      ctx.save();
      ctx.globalAlpha = Math.min(0.4, h.hurt * 1.6);
      var hg = ctx.createRadialGradient(G.W / 2, G.H / 2, G.H * 0.3, G.W / 2, G.H / 2, G.H * 0.7);
      hg.addColorStop(0, 'rgba(255,0,0,0)');
      hg.addColorStop(1, '#ff2a2a');
      ctx.fillStyle = hg;
      ctx.fillRect(0, 0, G.W, G.H);
      ctx.restore();
    }

    /* 升级金光 */
    if (S.lvFx > 0) {
      var lf = S.lvFx;
      ctx.save();
      ctx.globalAlpha = Math.min(1, lf / 0.6) * 0.55;
      var lgr = ctx.createRadialGradient(h.x, h.y - 18, 4, h.x, h.y - 18, 52);
      lgr.addColorStop(0, '#fff6d0');
      lgr.addColorStop(1, 'rgba(255,214,90,0)');
      ctx.fillStyle = lgr;
      ctx.beginPath(); ctx.arc(h.x, h.y - 18, 52, 0, 6.2832); ctx.fill();
      ctx.restore();
    }

    /* 新手箭头引导：脉动的箭头比文字有效得多（调研：完成率 30%→75%） */
    if (S.arrow && S.arrow.t > 0) {
      var at = S.arrow;
      var pul = 0.6 + 0.4 * Math.sin(Date.now() / 160);
      ctx.save();
      ctx.globalAlpha = Math.min(1, at.t) * pul;
      var ax = at.x, ay = at.y + Math.sin(Date.now() / 220) * 4;
      ctx.strokeStyle = '#ffd88e';
      ctx.fillStyle = '#ffd88e';
      ctx.lineWidth = 3;
      ctx.lineCap = 'round';
      /* 一个上指的小箭头 */
      ctx.beginPath();
      ctx.moveTo(ax, ay);
      ctx.lineTo(ax, ay - 16);
      ctx.stroke();
      ctx.beginPath();
      ctx.moveTo(ax, ay - 22);
      ctx.lineTo(ax - 7, ay - 12);
      ctx.lineTo(ax + 7, ay - 12);
      ctx.closePath();
      ctx.fill();
      ctx.restore();
    }

    /* 新手提示 */
    if (S.hint && S.hint.t > 0) {
      ctx.globalAlpha = Math.min(1, S.hint.t);
      /* 提示可能有两行（用 | 分隔），一行太宽会出屏 */
      var hlines = String(S.hint.txt).split('|');
      for (var hi = 0; hi < hlines.length; hi++) {
        G.shadowText(hlines[hi], G.W / 2, G.H - 186 + hi * 22, 15, '#ffe2b0', 'rgba(0,0,0,.9)');
      }
      ctx.globalAlpha = 1;
    }

    /* 屏幕暗角：把注意力收到中间的角色上 */
    var vg = ctx.createRadialGradient(G.W / 2, G.H / 2, G.H * 0.34, G.W / 2, G.H / 2, G.H * 0.78);
    vg.addColorStop(0, 'rgba(0,0,0,0)');
    vg.addColorStop(1, 'rgba(0,0,0,.42)');
    ctx.fillStyle = vg;
    ctx.fillRect(0, 0, G.W, G.H);

    /* ============ HUD（整排吃安全区：刘海/状态栏下再开始） ============ */
    var pd = G.W * 0.5;
    var hty = Math.max(14, ((G.SAFE ? G.SAFE.dTop : 0) + 10));
    G.round(12, hty, pd - 24, 42, 8, 'rgba(0,0,0,.5)');
    /* 地图名可点 → 选关（加 ▾ 提示玩家能点） */
    S.btnMap = { x: 70, y: hty + 14, r: 60 };
    G.text(S.map.name, 24, hty + 14, 16, '#ffd88e', 'left', true);
    G.text('▾', 24 + String(S.map.name).length * 16 + 4, hty + 15, 12, '#ffd88e', 'left');
    G.text('第 ' + (S.wave + 1) + '/' + S.map.waves + ' 波　妖 ' + S.mobs.length, 24, hty + 32, 12.5, '#c9bda4');

    /* 等级 + 经验条（跟 HUD 顶栏一起吃安全区偏移） */
    G.round(12, hty + 46, 92, 24, 6, 'rgba(0,0,0,.5)');
    G.text('Lv ' + (S.save.lv || 1), 22, hty + 58, 13, '#ffd88e', 'left', true);
    var need = xpNeed(S.save.lv || 1), cur = S.save.xp || 0;
    G.bar(52, hty + 52, 44, 12, need ? cur / need : 0, '#8fe3ff', 'rgba(0,0,0,.55)');
    G.text(cur + '/' + need, 74, hty + 58, 8.5, '#dff3ff', 'center', true);

    /* 战力（右上，安全区内 —— 胶囊正下方） */
    G.round(G.W - 12 - 118, hty + 2, 118, 30, 8, 'rgba(0,0,0,.5)');
    var pw = power(st);
    G.text('战力 ' + fmt(pw), G.W - 24, hty + 17, 16, '#ffd23a', 'right', true);
    if (S.anim.power > 0) {
      ctx.globalAlpha = Math.min(1, S.anim.power);
      G.text('+' + (pw - S.anim.powerFrom), G.W - 24, hty + 38, 14, '#7dff9b', 'right', true);
      ctx.globalAlpha = 1;
    }

    /* 自动战斗开关 */
    S.btnAuto = { x: G.W - 44, y: 74, r: 17 };
    G.circle(S.btnAuto.x, S.btnAuto.y, 17, S.autoOn ? '#3f7f4f' : 'rgba(30,30,30,.65)', 'rgba(255,255,255,.35)', 1.5);
    G.text('自动', S.btnAuto.x, S.btnAuto.y, 12, S.autoOn ? '#c9ffd0' : '#c8c0b0', 'center', true);

    /* 自动战斗提示条（可取消） */
    if (S.autoOn) {
      /* 放在顶部第二行下面 —— 原来压着 XP 条和静音键 */
      G.round(G.W / 2 - 130, 100, 260, 32, 8, 'rgba(20,40,25,.82)');
      G.text('自动战斗中 · 触碰屏幕切回', G.W / 2 - 8, 116, 13.5, '#b8f5c4', 'center');
      S.btnAutoX = { x: G.W / 2 + 116, y: 116, r: 13 };
      G.circle(S.btnAutoX.x, S.btnAutoX.y, 12, 'rgba(255,255,255,.14)');
      G.text('✕', S.btnAutoX.x, S.btnAutoX.y, 13, '#fff', 'center', true);
    }

    /* 静音开关 */
    S.btnMute = { x: 146, y: 74, r: 15 };
    G.circle(S.btnMute.x, S.btnMute.y, 14, 'rgba(0,0,0,.45)', 'rgba(255,255,255,.2)', 1);
    G.text(G.sfx && G.sfx.mute ? '🔇' : '🔊', S.btnMute.x, S.btnMute.y, 13, '#e6dcc6', 'center', true);

    /* 技能按钮 */
    for (var i = 0; i < 3; i++) {
      var sk2 = D.SKILLS[i];
      /* 技能排一排放在底部功能键**上方**，否则会和「抽卡」按钮叠在一起点不到 */
      var bx = G.W - 48 - (2 - i) * 70, by = G.H - 116;
      S['btnS' + i] = { x: bx, y: by, r: 27 };
      var ready = h.skCd[i] <= 0;
      G.circle(bx, by, 27, ready ? 'rgba(60,70,90,.86)' : 'rgba(40,42,50,.7)', ready ? sk2.col : 'rgba(255,255,255,.2)', 2);
      /* 冷却扇形遮罩要先画，名字再画上去，不然字会被盖住 */
      if (!ready) {
        var cd = h.skCd[i] / sk2.cd;      /* 1 = 刚放完，0 = 转好了 */
        ctx.save();
        ctx.fillStyle = 'rgba(0,0,0,.58)';
        ctx.beginPath();
        ctx.moveTo(bx, by);
        ctx.arc(bx, by, 26, -Math.PI / 2, -Math.PI / 2 + cd * Math.PI * 2, false);
        ctx.closePath();
        ctx.fill();
        ctx.restore();
      }
      G.text('Lv' + ((S.save.skLv && S.save.skLv[i]) || 1), bx, by - 14, 8.5, ready ? '#9aa0a8' : '#6a6a70', 'center');
      G.text(sk2.name, bx, by - 1, 12.5, ready ? '#fff' : '#a8a8b0', 'center', true);
      if (!ready) G.text(Math.ceil(h.skCd[i]) + 's', bx, by + 13, 12, '#ffd23a', 'center', true);
    }

    /* 底部功能键 */
    S.btnBag = { x: 44, y: G.H - 46, r: 21 };
    G.circle(S.btnBag.x, S.btnBag.y, 21, 'rgba(30,32,38,.8)', 'rgba(255,255,255,.3)', 1.5);
    G.text('背包', S.btnBag.x, S.btnBag.y, 12.5, '#e8e0d0', 'center', true);
    S.btnPet = { x: 98, y: G.H - 46, r: 21 };
    G.circle(S.btnPet.x, S.btnPet.y, 21, 'rgba(30,32,38,.8)', 'rgba(255,255,255,.3)', 1.5);
    G.text('宠物', S.btnPet.x, S.btnPet.y, 12.5, '#e8e0d0', 'center', true);
    S.btnRank = { x: 152, y: G.H - 46, r: 21 };
    G.circle(S.btnRank.x, S.btnRank.y, 21, 'rgba(30,32,38,.8)', 'rgba(255,255,255,.3)', 1.5);
    G.text('排行', S.btnRank.x, S.btnRank.y, 12.5, '#e8e0d0', 'center', true);
    S.btnPull = { x: 206, y: G.H - 46, r: 21 };
    G.circle(S.btnPull.x, S.btnPull.y, 21, 'rgba(120,70,30,.85)', 'rgba(255,190,90,.5)', 1.5);
    G.text('抽卡', S.btnPull.x, S.btnPull.y, 12.5, '#ffe2b0', 'center', true);

    /* toast */
    if (S.toastT > 0) {
      S.toastT -= G.dt;
      ctx.globalAlpha = Math.min(1, S.toastT);
      G.round(G.W / 2 - 90, G.H * 0.36, 180, 32, 8, 'rgba(0,0,0,.72)');
      G.text(S.toast, G.W / 2, G.H * 0.36 + 16, 14, '#ffd88e', 'center');
      ctx.globalAlpha = 1;
    }
  }

  /* ============ 背包界面 ============ */
  /* ============ 装备强化面板 ============ */
  function itemIcon(it, x, y, size) {
    /* 武器用贴图，其它部位用品质色方块 */
    var img = null;
    if (it.wtype) {
      var sk = D.WEAPON_SKIN.filter(function (w) { return w.w === it.wtype; })[0];
      if (sk && S.wskinImg) img = S.wskinImg[sk.id];
    }
    if (img) {
      var ww = img.width / img.height * size;
      ctx.drawImage(img, x - ww / 2, y - size * 0.5, ww, size);
      return;
    }
    G.round(x - size / 2, y - size / 2, size, size, 8, it.col, 'rgba(255,255,255,.35)', 1.5);
    G.text(slotName(it.slot).slice(0, 1), x, y, size * 0.45, 'rgba(0,0,0,.45)', 'center', true);
  }

  /* ============ 选关面板 ============ */
  function drawMaps() {
    clearBtns();
    var cy = panelChrome('选 择 地 图');
    /* 签到 + 战力放标题下一行（原来和居中标题挤在一行会重叠） */
    var canSign = canSignIn();
    S.btnSign = { x: G.W - 208, y: cy - 16, r: 24 };
    btnGhost(G.W - 240, cy - 31, 64, 30, '签到');
    if (canSign) G.circle(G.W - 180, cy - 28, 4.5, '#ff5a6e');
    G.text('战力 ' + fmt(power()), G.W - 28, cy - 16, 13, TH.gold, 'right', true);

    var s = S.save;
    var pw2 = power();
    /* 整块内容可滚动（7 卡 + 图鉴 + 兑换超过一屏） */
    var listTop = cy + 4, listBot = G.H - 72;
    ctx.save();
    ctx.beginPath(); ctx.rect(0, listTop, G.W, listBot - listTop); ctx.clip();
    var y = cy + 8 - (S.mapScroll || 0);
    for (var i = 0; i < D.MAPS.length; i++) {
      var mp = D.MAPS[i];
      var unlocked = (i <= s.maxWave);
      var cur = (S.map && S.map.id === mp.id);
      var cleared = s.cleared && s.cleared[mp.id];
      var strong = pw2 >= mp.pw;

      /* 卡片：当前图金边微光，锁定压暗 */
      card(20, y, G.W - 40, 74, cur ? TH.goldD : null, cur ? 'rgba(255,216,142,.35)' : null);
      if (!unlocked) G.round(20, y, G.W - 40, 74, 10, 'rgba(10,10,12,.62)');
      /* 左侧地面预览块（每图配色渐变 + fx 名） */
      var px = 30, pw3 = 72, ph = 54, py = y + 10;
      G.round(px, py, pw3, ph, 8, lin(px, py, px + pw3, py + ph, unlocked ? mp.ground : '#26241f', unlocked ? mp.ground2 : '#302d27'),
        'rgba(255,255,255,.14)', 1);
      if (unlocked && mp.fx) {
        G.round(px + 4, py + ph - 16, pw3 - 8, 13, 6, 'rgba(0,0,0,.45)');
        var fxn = { bone: '白骨', leaf: '竹叶', frost: '霜冻', ember: '余烬', star: '星辉' }[mp.fx] || '';
        G.text(fxn, px + pw3 / 2, py + ph - 9, 9, TH.ink2, 'center');
      }
      if (!unlocked) {
        var lx = px + pw3 / 2, ly2 = py + ph / 2;
        ctx.strokeStyle = '#8d8272'; ctx.lineWidth = 2.5;
        ctx.beginPath(); ctx.arc(lx, ly2 - 3, 6, Math.PI, 0); ctx.stroke();
        G.round(lx - 8, ly2 - 3, 16, 12, 3, '#8d8272');
      }

      G.text(mp.name, 116, y + 20, 16.5, unlocked ? TH.ink : TH.ink3, 'left', true);
      var names = [];
      for (var k = 0; k < mp.mobs.length; k++) {
        var md = D.MONS.filter(function (x) { return x.id === mp.mobs[k]; })[0];
        if (md && names.indexOf(md.name) < 0) names.push(md.name);
      }
      var ed = D.MONS.filter(function (x) { return x.id === mp.elite; })[0];
      if (ed && names.indexOf(ed.name) < 0) names.push(ed.name);
      if (mp.boss) {
        var bd = D.MONS.filter(function (x) { return x.id === mp.boss; })[0];
        if (bd && names.indexOf(bd.name) < 0) names.push(bd.name);
      }
      G.text((mp.waves + ' 波 · ' + names.join(' · ')).slice(0, 24), 116, y + 44, 10.5, unlocked ? TH.ink3 : '#4f4b43', 'left');
      /* 状态徽章 + 推荐战力（右列独立，怪物行截断避让） */
      var stTxt = unlocked ? (cleared ? '已通关' : (cur ? '征战中' : '进入')) : '未解锁';
      var stCol = cur ? TH.gold : (cleared ? TH.ink3 : (unlocked ? TH.jade : TH.ink3));
      G.round(G.W - 118, y + 10, 88, 22, 11, cur ? 'rgba(212,169,78,.20)' : 'rgba(255,255,255,.05)',
        cur ? 'rgba(212,169,78,.55)' : 'rgba(255,255,255,.14)', 1);
      G.text(stTxt, G.W - 74, y + 21, 11.5, stCol, 'center', true);
      G.text('推荐 ' + fmt(mp.pw), G.W - 74, y + 48, 11, strong ? TH.jade : TH.red, 'center', true);
      S['mapBtn' + i] = { x: G.W / 2, y: y + 37, r: 39, idx: i, locked: !unlocked };
      y += 84;
    }
    /* 图鉴：击杀收集 */
    y += 6;
    G.text('— 图鉴 —', G.W / 2, y, 12, TH.ink3, 'center');
    y += 20;
    var dxc = S.save.dex || {};
    var gotN = 0;
    for (var di2 = 0; di2 < D.MONS.length; di2++) if (dxc[D.MONS[di2].id]) gotN++;
    G.text('已收录 ' + gotN + ' / ' + D.MONS.length + ' 种', 40, y, 11, TH.ink2, 'left');
    G.text('图鉴点 ' + (S.save.dexP || 0) + ' / ' + D.DEX_GOAL, G.W - 36, y, 11, '#b9a8ff', 'right');
    y += 16;
    var col2 = 0, row2 = 0;
    for (var di = 0; di < D.MONS.length && row2 < 3; di++) {
      var dm = D.MONS[di];
      var cnt = dxc[dm.id] || 0;
      var gx = 40 + col2 * 200;
      var gy = y + row2 * 21;
      G.text(dm.name, gx, gy, 11.5, cnt ? TH.ink : '#4f4b45');
      G.text(cnt ? cnt + '只' : '—', gx + 68, gy, 10.5, cnt ? TH.ink2 : '#413d38');
      G.text(dm.boss === 2 ? '妖王' : (dm.boss === 1 ? '精英' : ''), gx + 116, gy, 10,
        dm.boss === 2 ? TH.red : TH.gold, 'left');
      col2++;
      if (col2 >= 2) { col2 = 0; row2++; }
    }
    y += 3 * 21 + 10;
    /* 兑换按钮 */
    var canDex = (s.dexP || 0) >= D.DEX_GOAL;
    S.btnDex = { x: G.W / 2, y: y + 26, r: 44 };
    if (canDex) btnGold(G.W / 2 - 165, y, 330, 52, '兑换奖励', '精粹×' + D.DEX_ESS + ' 宝石×1');
    else btnGhost(G.W / 2 - 165, y, 330, 52, '还差 ' + (D.DEX_GOAL - (s.dexP || 0)) + ' 图鉴点可兑换');

    S.mapMax = Math.max(0, (y - cy - 8) - (listBot - listTop) + 16);
    ctx.restore();
    G.text('低图掉低级装备 · 高图出好东西 · 自由切换', G.W / 2, G.H - Math.max(58, (G.SAFE ? G.SAFE.dBottom : 0) + 48), 11, TH.ink3, 'center');
    drawBackBar();
  }

  /* ============ 每日签到面板 ============ */
  function todayKey() {
    var d = new Date();
    return d.getFullYear() + '-' + (d.getMonth() + 1) + '-' + d.getDate();
  }
  function canSignIn() { return S.save.signDate !== todayKey(); }

  function drawSign() {
    clearBtns();
    var cy = panelChrome('每日签到');
    drawBackBar();
    G.text('连签 ' + S.save.signDay + ' 天', G.W - 28, cy - 24, 13, '#c9bda4', 'right');

    var can = canSignIn();
    var cur = S.save.signDay % D.SIGN.length;
    /* 7 个格子排两行 */
    for (var i = 0; i < D.SIGN.length; i++) {
      var r = D.SIGN[i];
      var col = i % 4, row = Math.floor(i / 4);
      var bx = 16 + col * ((G.W - 32) / 4), bw = (G.W - 32) / 4 - 8;
      var by = 96 + row * 116;
      var claimed = i < cur || (!can && i === cur);
      var today = can && i === cur;
      G.round(bx, by, bw, 100, 10,
        claimed ? 'rgba(255,255,255,.03)' : (today ? 'rgba(255,220,150,.12)' : 'rgba(255,255,255,.05)'),
        today ? '#ffd88e' : 'rgba(255,255,255,.13)', today ? 2 : 1);
      G.text('第' + (i + 1) + '天', bx + bw / 2, by + 18, 12, today ? '#ffd88e' : '#8a8272', 'center');
      /* 奖励内容 */
      var ry = by + 46;
      if (r.gem) {
        var gd = D.GEMS.filter(function (x) { return x.id === r.gem; })[0];
        G.circle(bx + bw / 2, ry, 16, gd ? gd.col : '#888');
        G.text(gd ? gd.name : '宝石', bx + bw / 2, ry, 9, 'rgba(0,0,0,.6)', 'center', true);
      } else if (r.coin) {
        G.text('灵果', bx + bw / 2, ry - 8, 11, '#8a8272', 'center');
        G.text('+' + r.coin, bx + bw / 2, ry + 8, 16, '#ffd76a', 'center', true);
      } else {
        G.text('精粹', bx + bw / 2, ry - 8, 11, '#8a8272', 'center');
        G.text('+' + r.ess, bx + bw / 2, ry + 8, 16, '#b9a8ff', 'center', true);
      }
      if (claimed) G.text('✓', bx + bw / 2, by + 84, 15, '#7dff9b', 'center', true);
    }
    /* 领取按钮 */
    S.btnClaim = { x: G.W / 2, y: G.H - 90, r: 60 };
    G.round(G.W / 2 - 110, G.H - 124, 220, 56, 14,
      can ? 'rgba(150,80,30,.95)' : 'rgba(50,48,44,.9)', can ? 'rgba(255,190,90,.75)' : 'rgba(255,255,255,.12)', 2);
    G.text(can ? '领取奖励' : '今天已领取', G.W / 2, G.H - 96, 19, can ? '#ffe2b0' : '#6d675c', 'center', true);
    if (can) G.text('第 ' + (cur + 1) + ' 天奖励', G.W / 2, G.H - 76, 11.5, '#d9b98a', 'center');
  }

  function doSign() {
    var s = S.save;
    if (!canSignIn()) { toast('今天已经签过啦'); return; }
    var cur = s.signDay % D.SIGN.length;
    var r = D.SIGN[cur];
    s.coins += r.coin || 0;
    s.essence = (s.essence || 0) + (r.ess || 0);
    if (r.gem) { s.gems = s.gems || {}; s.gems[r.gem] = (s.gems[r.gem] || 0) + 1; }
    s.signDay = (s.signDay || 0) + 1;
    s.signDate = todayKey();
    G.persist();
    toast('签到成功！第 ' + s.signDay + ' 天');
    S.state = 'maps';
  }

  /* ============ 武器造型面板 ============ */
  function drawSkins() {
    clearBtns();
    var cy = panelChrome('造型');
    drawBackBar();

    /* 页签：人物 / 武器 */
    S.skinTab = S.skinTab || 'char';
    S.tabChar = { x: 74, y: 70, r: 40 };
    S.tabWeapon = { x: 168, y: 70, r: 40 };
    G.round(24, 56, 100, 28, 14, S.skinTab === 'char' ? 'rgba(255,220,150,.85)' : 'rgba(255,255,255,.07)');
    G.round(118, 56, 100, 28, 14, S.skinTab === 'weapon' ? 'rgba(255,220,150,.85)' : 'rgba(255,255,255,.07)');
    G.text('人物', 74, 70, 13, S.skinTab === 'char' ? '#2a2418' : '#8a8272', 'center', true);
    G.text('武器', 168, 70, 13, S.skinTab === 'weapon' ? '#2a2418' : '#8a8272', 'center', true);
    G.text('只换外观，不加属性', G.W - 64, 70, 11.5, '#8a8272', 'right');

    if (S.skinTab === 'char') { drawCharSkins(); return; }
    var list = D.WEAPON_SKIN;
    var cols = 3, cw = (G.W - 32) / cols;
    for (var i = 0; i < list.length; i++) {
      var w = list[i];
      var col = i % cols, row = Math.floor(i / cols);
      var bx = 16 + col * cw, by = 88 + row * 152;
      var on = S.save.wskin === w.id;
      G.round(bx, by, cw - 10, 140, 10, on ? 'rgba(255,220,150,.10)' : 'rgba(255,255,255,.04)',
        on ? w.col : 'rgba(255,255,255,.12)', on ? 2 : 1);
      var img = S.wskinImg && S.wskinImg[w.id];
      if (img) {
        var ih = 84, iw = img.width / img.height * ih;
        ctx.drawImage(img, bx + (cw - 10) / 2 - iw / 2, by + 14, iw, ih);
      } else {
        G.text('?', bx + (cw - 10) / 2, by + 50, 26, 'rgba(255,255,255,.2)', 'center', true);
      }
      G.text(w.name, bx + (cw - 10) / 2, by + 114, 14, on ? w.col : '#cfc6b0', 'center', true);
      G.text(on ? '使用中' : '点击装备', bx + (cw - 10) / 2, by + 130, 10.5, on ? '#ffd88e' : '#6d675c', 'center');
      S['skBtn' + w.id] = { x: bx + (cw - 10) / 2, y: by + 60, r: 46, id: w.id, name: w.name };
    }
  }

  /* 人物造型页 */
  function drawCharSkins() {
    var sex = S.save.sex || 'm';
    var list = D.CHAR_SKIN.filter(function (x) { return x.sex === sex; });
    G.text('当前：' + (D.CHAR_SKIN.filter(function (x) { return x.id === S.save.skin; })[0] || {}).name,
      24, 106, 13, '#9c9484', 'left');
    for (var i = 0; i < list.length; i++) {
      var c = list[i];
      var bx = 16 + i * ((G.W - 32) / 2), bw = (G.W - 32) / 2 - 8;
      var on = S.save.skin === c.id;
      G.round(bx, 126, bw, 320, 12, on ? 'rgba(255,220,150,.10)' : 'rgba(255,255,255,.04)',
        on ? '#ffd88e' : 'rgba(255,255,255,.13)', on ? 2 : 1);
      var img = S.charImg && S.charImg[c.id];
      if (img) {
        var ih = 236, iw = img.width / img.height * ih;
        ctx.drawImage(img, bx + bw / 2 - iw / 2, by0(126, ih), iw, ih);
      } else {
        G.circle(bx + bw / 2, 240, 40, c.col);
        G.text('?', bx + bw / 2, 240, 30, 'rgba(255,255,255,.25)', 'center', true);
      }
      G.text(c.name, bx + bw / 2, 400, 17, on ? '#ffd88e' : '#cfc6b0', 'center', true);
      G.text(on ? '使用中' : '点击装备', bx + bw / 2, 424, 11.5, on ? '#ffd88e' : '#6d675c', 'center');
      S['chBtn' + c.id] = { x: bx + bw / 2, y: 250, r: 80, id: c.id };
    }
    G.text('人物造型', G.W / 2, G.H - 40, 11.5, '#6d675c', 'center');
  }
  function by0(y, h) { return y + 12; }

  function drawUpgrade() {
    clearBtns();
    G.round(0, 0, G.W, G.H, 0, 'rgba(10,10,12,.97)');
    var it = S.save.equip[S.upSlot];
    if (!it) { S.state = 'bag'; return; }
    var lv = it.lv || 0;

    var cy = panelChrome('强化');
    drawBackBar();

    /* 装备卡 */
    G.round(16, 74, G.W - 32, 150, 12, 'rgba(255,255,255,.05)', it.col, 1.5);
    itemIcon(it, 68, 148, 84);
    G.text(it.qn + (lv ? ' +' + lv : ''), 122, 106, 19, it.col, 'left', true);
    G.text(slotName(it.slot) + (it.wtype ? ' · ' + D.WEAPONS[it.wtype].name : ''), 122, 130, 12.5, '#a89f8c', 'left');
    G.text('强化等级 ' + lv + ' / ' + D.ENH_MAX, 122, 152, 13, lv ? '#ffd23a' : '#8a8272', 'left');
    G.text('每级属性 +' + Math.round(D.ENH_MUL * 100) + '%', 122, 172, 11.5, '#8a8272', 'left');

    /* 属性 */
    var y = 244;
    G.text('词条', 24, y, 13, '#9c9484', 'left');
    var affs = affixTxt(it);
    G.text(affs === '无词条' ? '无' : affs, 24, y + 22, 14, affs === '无词条' ? '#6d675c' : '#cfc6b0', 'left');

    /* 攻击预览 */
    if (it.wtype && it.atk) {
      var lm = 1 + lv * D.ENH_MUL;
      G.text('攻击', 24, y + 52, 13, '#9c9484', 'left');
      G.text(Math.round(it.atk), 70, y + 52, 15, '#e6dcc6', 'left');
      G.text('→', 108, y + 52, 13, '#6d675c', 'left');
      G.text(Math.round(it.atk * (1 + D.ENH_MUL)), 128, y + 52, 17, '#ffd23a', 'left', true);
      G.text('（+1 级）', 172, y + 52, 11.5, '#8a8272', 'left');
    }

    /* 技能升级 */
    G.text('技能', 24, 414, 14, '#ffd88e', 'left', true);
    G.text('每级 +' + Math.round(D.SK_DMG * 100) + '% 伤害', G.W - 32, 414, 11, '#8a8272', 'right');
    for (var si = 0; si < 3; si++) {
      var skd = D.SKILLS[si];
      var slv = (S.save.skLv && S.save.skLv[si]) || 1;
      var yy = 430 + si * 42;
      G.round(20, yy, G.W - 40, 36, 8, 'rgba(255,255,255,.04)');
      G.text(skd.name, 34, yy + 18, 13, skd.col, 'left', true);
      G.text('Lv ' + slv + '/' + D.SK_MAX, 92, yy + 18, 12, slv > 1 ? '#ffd23a' : '#c9bda4');
      G.text('伤害+' + Math.round((slv - 1) * D.SK_DMG * 100) + '%', 156, yy + 18, 11, '#8a8272');
      /* 升级按钮 */
      var canSk = slv < D.SK_MAX && S.save.coins >= D.SK_COIN(slv) && (S.save.essence || 0) >= D.SK_ESS(slv);
      S['skUp' + si] = { x: G.W - 58, y: yy + 18, r: 16, idx: si };
      G.round(G.W - 92, yy + 6, 52, 24, 12,
        canSk ? 'rgba(90,70,40,.9)' : 'rgba(45,45,48,.8)', canSk ? 'rgba(255,190,90,.5)' : 'rgba(255,255,255,.1)', 1);
      G.text(slv >= D.SK_MAX ? '满' : '升级', G.W - 58, yy + 18, 11.5, canSk ? '#ffe2b0' : '#6d675c', 'center', true);
    }

    /* 资源 */
    G.text('灵果 ' + Math.floor(S.save.coins), 24, G.H - 150, 13, '#ffd76a', 'left');
    G.text('精粹 ' + Math.floor(S.save.essence || 0), 24, G.H - 128, 13, '#b9a8ff', 'left');

    /* 宝石槽 */
    var gd3 = it.gem ? D.GEMS.filter(function (x) { return x.id === it.gem; })[0] : null;
    var sl2 = D.SLOTS.filter(function (x) { return x.id === it.slot; })[0];
    var want = D.GEMS.filter(function (x) { return x.main === (sl2 ? sl2.main : 'atk'); })[0];
    var have = want ? (S.save.gems && S.save.gems[want.id] || 0) : 0;
    S.btnGem = { x: 26, y: y + 118, r: 22 };
    G.round(4, y + 96, 44, 44, 10, gd3 ? gd3.col : 'rgba(255,255,255,.05)', gd3 ? gd3.col : 'rgba(255,255,255,.2)', 1.5);
    if (gd3) {
      G.circle(26, y + 118, 13, gd3.col);
      G.text(gd3.name, 26, y + 118, 9, 'rgba(0,0,0,.6)', 'center', true);
    } else {
      G.text('槽', 26, y + 118, 12, '#6d675c', 'center');
    }
    G.text(gd3 ? (gd3.name + '（点击卸下）') : (have > 0 ? ('可镶嵌 ' + want.name + ' ×' + have) : '暂无宝石'),
      58, y + 112, 12, gd3 ? gd3.col : (have > 0 ? '#7dff9b' : '#6d675c'), 'left');
    G.text(gd3 ? ('+' + gd3.v + ' ' + (gd3.main === 'hp' ? '生命' : gd3.main === 'crit' ? '暴击' : gd3.main === 'def' ? '防御' : '攻击'))
      : (have > 0 ? '点击镶嵌' : '精英/妖王掉落'),
      58, y + 130, 10.5, '#8a8272', 'left');

    /* 强化按钮 */
    var coin = D.ENH_COIN(lv), ess = D.ENH_ESS(lv);
    var can = lv < D.ENH_MAX && S.save.coins >= coin && (S.save.essence || 0) >= ess;
    S.btnEnh = { x: G.W / 2, y: G.H - 74, r: 60 };
    G.round(G.W / 2 - 130, G.H - 122, 260, 60, 14,
      can ? 'rgba(150,80,30,.95)' : 'rgba(50,48,44,.9)',
      can ? 'rgba(255,190,90,.75)' : 'rgba(255,255,255,.12)', 2);
    G.text(lv >= D.ENH_MAX ? '已满级' : '强化 +1', G.W / 2, G.H - 92, 20,
      can ? '#ffe2b0' : '#6d675c', 'center', true);
    G.text(lv >= D.ENH_MAX ? '' : ('灵果 ' + coin + ' · 精粹 ' + ess),
      G.W / 2, G.H - 68, 12, can ? '#d9b98a' : '#5c574d', 'center');

    /* 分解（把这件卖了） */
    S.btnSell = { x: G.W - 62, y: G.H - 190, r: 34 };
    G.round(G.W - 96, G.H - 224, 68, 68, 12, 'rgba(90,50,40,.85)', 'rgba(220,120,90,.5)', 1.5);
    G.text('分解', G.W - 62, G.H - 190, 13, '#ffcbb0', 'center', true);
    G.text('+' + (D.SALVAGE_VALUE[it.q] || 3) + '精粹', G.W - 62, G.H - 170, 10, '#e0a890', 'center');
  }

  function doEnhance() {
    var s = S.save, it = s.equip[S.upSlot];
    if (!it) return;
    var lv = it.lv || 0;
    if (lv >= D.ENH_MAX) { toast('已经满级了'); return; }
    var coin = D.ENH_COIN(lv), ess = D.ENH_ESS(lv);
    if (s.coins < coin) { toast('灵果不够'); return; }
    if ((s.essence || 0) < ess) { toast('精粹不够，去分解装备'); return; }
    s.coins -= coin; s.essence -= ess;
    it.lv = lv + 1;
    var before = power();
    S.stats = stats();
    var after = power();
    S.anim.power = 1.4; S.anim.powerFrom = before;
    if (after > s.best) s.best = after;
    toast('强化成功 +' + it.lv + '　战力 +' + (after - before));
    if (G.sfx) G.sfx.play('upgrade');
    G.persist();
  }

  function upSk(idx) {
    if (idx === undefined || idx < 0 || idx > 2) return;
    var s = S.save;
    s.skLv = s.skLv || [1, 1, 1];
    var lv = s.skLv[idx] || 1;
    if (lv >= D.SK_MAX) { toast('技能已满级'); return; }
    var coin = D.SK_COIN(lv), ess = D.SK_ESS(lv);
    if (s.coins < coin) { toast('灵果不够'); return; }
    if ((s.essence || 0) < ess) { toast('精粹不够，去分解装备'); return; }
    s.coins -= coin; s.essence -= ess;
    s.skLv[idx] = lv + 1;
    toast(D.SKILLS[idx].name + ' 升到 Lv ' + s.skLv[idx]);
    if (G.sfx) G.sfx.play('upgrade');
    G.persist();
  }

  function claimDex() {
    var s = S.save;
    if ((s.dexP || 0) < D.DEX_GOAL) { toast('图鉴点不够'); return; }
    s.dexP -= D.DEX_GOAL;
    s.essence = (s.essence || 0) + D.DEX_ESS;
    s.gems = s.gems || {};
    var g = D.GEMS[0];
    s.gems[g.id] = (s.gems[g.id] || 0) + 1;
    toast('图鉴兑换：精粹 +' + D.DEX_ESS + '　' + g.name + ' ×1');
    if (G.sfx) G.sfx.play('rare');
    G.persist();
  }

  function sellEquipped() {
    var s = S.save, it = s.equip[S.upSlot];
    if (!it) return;
    var v = D.SALVAGE_VALUE[it.q] || 3;
    v = Math.round(v * (1 + (it.lv || 0) * 0.3));   /* 强化过的更值钱 */
    delete s.equip[S.upSlot];
    s.essence = (s.essence || 0) + v;
    S.stats = stats();
    S.state = 'bag';
    toast('分解得到 ' + v + ' 精粹');
    G.persist();
  }

  function toggleGem() {
    var s = S.save, it = s.equip[S.upSlot];
    if (!it) return;
    if (it.gem) {                       /* 已镶 → 卸下 */
      s.gems = s.gems || {};
      s.gems[it.gem] = (s.gems[it.gem] || 0) + 1;
      var gd = D.GEMS.filter(function (x) { return x.id === it.gem; })[0];
      delete it.gem;
      S.stats = stats();
      toast('卸下 ' + (gd ? gd.name : '宝石'));
      G.persist();
      return;
    }
    /* 没镶 → 找和部位主属性匹配的宝石 */
    var sl = D.SLOTS.filter(function (x) { return x.id === it.slot; })[0];
    var want = D.GEMS.filter(function (x) { return x.main === (sl ? sl.main : 'atk'); })[0];
    if (!want) { toast('这个部位不能镶宝石'); return; }
    s.gems = s.gems || {};
    if (!(s.gems[want.id] > 0)) { toast('没有 ' + want.name + ' 了'); return; }
    s.gems[want.id]--;
    if (s.gems[want.id] <= 0) delete s.gems[want.id];
    it.gem = want.id;
    S.stats = stats();
    toast('镶嵌 ' + want.name + '！');
    if (G.sfx) G.sfx.play('gem');
    G.persist();
  }

  function salvageJunk() {
    var s = S.save, n = 0, gain = 0;
    for (var i = s.bag.length - 1; i >= 0; i--) {
      var q = s.bag[i].q;
      if (q === 'w' || q === 'g') {
        gain += D.SALVAGE_VALUE[q] || 1;
        s.bag.splice(i, 1); n++;
      }
    }
    if (!n) { toast('没有可分解的装备'); return; }
    s.essence = (s.essence || 0) + gain;
    toast('分解 ' + n + ' 件 → 精粹 +' + gain);
    G.persist();
  }

  function drawBag() {
    clearBtns();
    var cy = panelChrome('背 包');
    /* 第二行（CSS 像素空间，屏宽≈393）：战力（左）· 造型 / 改形象 / 一键分解（右） */
    var ry = cy + 6;
    G.text('战力', 16, ry, 10, TH.ink3, 'left');
    G.text(fmt(power()), 16, ry + 18, 17, TH.gold, 'left', true);
    S.btnSkin = { x: 152, y: ry + 11, r: 42 };
    btnGhost(126, ry - 3, 52, 28, '造型');
    S.btnLook = { x: 218, y: ry + 11, r: 42 };
    btnGhost(186, ry - 3, 64, 28, '改形象');
    S.btnSalvage = { x: 320, y: ry + 11, r: 42 };
    btnGhost(258, ry - 3, 124, 28, '一键分解');

    /* 已装备 4 卡（品质色描边 + 强化徽章 + 套装点） */
    var slots = D.SLOTS;
    var sy = ry + 44;
    for (var i = 0; i < slots.length; i++) {
      var sl = slots[i], bx = 20 + i * ((G.W - 40) / 4), bw = (G.W - 40) / 4 - 8;
      var it = S.save.equip[sl.id];
      card(bx, sy, bw, 92, it ? it.col : null);
      G.text(sl.name, bx + 10, sy + 14, 11, TH.ink3, 'left');
      S['slotBtn' + sl.id] = { x: bx + bw / 2, y: sy + 52, r: 44, slot: sl.id };
      if (it) {
        if (it.lv) {
          G.round(bx + bw - 40, sy + 6, 32, 17, 8, 'rgba(212,169,78,.18)', 'rgba(212,169,78,.5)', 1);
          G.text('+' + it.lv, bx + bw - 24, sy + 15, 10.5, TH.gold, 'center', true);
        }
        G.text(it.qn, bx + bw / 2, sy + 38, 12.5, it.col, 'center', true);
        var sd0 = setD(it);
        if (sd0) { G.circle(bx + bw / 2 - (sd0.name.length * 11 + 14) / 2 - 6, sy + 56, 3.5, sd0.col); }
        G.text(affixTxt(it).slice(0, 12), bx + bw / 2 + (sd0 ? 4 : 0), sy + 57, 9.5, TH.ink2, 'center');
        G.text(it.gem ? '◆ 已镶宝石' : '◇ 空宝石槽', bx + bw / 2, sy + 76, 9.5, it.gem ? TH.jade : TH.ink3, 'center');
      } else {
        G.text('空', bx + bw / 2, sy + 50, 14, TH.ink3, 'center');
      }
    }

    /* 背包列表 */
    var y = sy + 108, n = 0;
    /* 套装进度（凑到 2 件才显示） */
    var sumTxt = '';
    var scNow = setCounts(S.save.equip);
    for (var ssid in scNow) {
      if (scNow[ssid] < 2) continue;
      var ssd = D.SETS.filter(function (x) { return x.id === ssid; })[0];
      if (ssd) sumTxt += (sumTxt ? ' · ' : '') + ssd.name + ' ' + scNow[ssid] + '/4 ' + (scNow[ssid] >= 4 ? ssd.d4 : ssd.d2);
    }
    if (sumTxt) { G.text('◈ ' + sumTxt, 24, y, 12, TH.ink2); y += 20; }
    var gemTot = 0;
    if (S.save.gems) for (var gk in S.save.gems) gemTot += S.save.gems[gk];
    G.text('持有 ' + S.save.bag.length + ' 件' + (gemTot ? ' · 宝石 ' + gemTot : ''), 24, y, 12.5, TH.ink2);
    G.text('点装备穿上 · 上下滑动', G.W - 24, y, 11, TH.ink3, 'right');
    y += 20;
    /* 可滚动的物品列表：裁剪区 + 滚动偏移（拖动在 update 里轮询 G.T） */
    var listTop = y - 6, listBot = G.H - 196;
    ctx.save();
    ctx.beginPath(); ctx.rect(0, listTop, G.W, listBot - listTop); ctx.clip();
    var yy = y - (S.bagScroll || 0);
    for (var j = S.save.bag.length - 1; j >= 0 && n < 60; j--) {
      if (yy > listTop - 62 && yy < listBot) {
        var it2 = S.save.bag[j];
        card(20, yy, G.W - 40, 50, null);
        G.round(20, yy + 6, 4, 38, 2, it2.col);
        var iw2 = null;
        if (it2.wtype) {
          var sk2 = D.WEAPON_SKIN.filter(function (w) { return w.w === it2.wtype; })[0];
          if (sk2 && S.wskinImg) iw2 = S.wskinImg[sk2.id];
        }
        var ti2 = tintedIcon(it2.slot, it2.col);
        if (iw2) {
          var bhh2 = 34, bww2 = iw2.width / iw2.height * bhh2;
          ctx.drawImage(iw2, 34 + (34 - bww2) / 2, yy + 8, bww2, bhh2);
        } else if (ti2) {
          ctx.drawImage(ti2, 34, yy + 8, 34, 34);
        } else {
          G.round(34, yy + 8, 28, 34, 6, 'rgba(255,255,255,.05)', it2.col, 1.2);
          G.circle(48, yy + 25, 8, it2.col);
        }
        G.text(it2.qn + (it2.lv ? ' +' + it2.lv : ''), 80, yy + 16, 13.5, it2.col, 'left', true);
        var sdi = setD(it2);
        G.text(slotName(it2.slot) + (it2.wtype ? '·' + D.WEAPONS[it2.wtype].name : '') + (sdi ? ' · ' + sdi.name : ''),
          80, yy + 34, 11, sdi ? sdi.col : TH.ink3);
        G.text(affixTxt(it2), G.W - 32, yy + 26, 11, TH.ink2, 'right');
        S['bagItem' + j] = { x: 24, y: yy + 25, r: 0, w: G.W - 48, h: 26, idx: j };
      }
      yy += 58; n++;
    }
    S.bagMax = Math.max(0, (yy - y) - (listBot - listTop) + 12);
    ctx.restore();
    if (!S.save.bag.length) G.text('还没有装备 · 去打怪爆', G.W / 2, y + 60, 15, TH.ink3, 'center');

    /* 底部：十连抽（金主按钮）+ 返回条 */
    S.btnPull10 = { x: G.W / 2, y: G.H - 148, r: 62 };
    btnGold(G.W / 2 - 140, G.H - 178, 280, 60, '十 连 抽',
      '免费 · 每 8 次必出史诗以上（当前 ' + (S.save.pulls % 8) + '/8）');
    drawBackBar();
  }
  function slotName(id) { var s = D.SLOTS.filter(function (x) { return x.id === id; })[0]; return s ? s.name : id; }
  function affixTxt(it) {
    var out = [];
    for (var k in it.aff) {
      var a = D.AFFIX[k];
      out.push(a.name + '+' + it.aff[k]);
    }
    return out.length ? out.join(' ') : '无词条';
  }

  /* ============ 宠物界面 ============ */
  function drawPets() {
    clearBtns();
    var cy = panelChrome('宠物');
    drawBackBar();
    G.text('战力 ' + fmt(power()), G.W - 28, cy - 24, 15, TH.gold, 'right', true);
    G.text('战力 ' + fmt(power()), G.W - 64, 40, 18, '#ffd23a', 'right');
    S.btnBack = { x: G.W - 34, y: 40, r: 17 };
    G.circle(S.btnBack.x, S.btnBack.y, 16, 'rgba(255,255,255,.12)');
    G.text('✕', S.btnBack.x, S.btnBack.y, 14, '#fff', 'center', true);

    var s = S.save, m = mood();
    if (!s.pet) {
      G.text('还没有宠物', G.W / 2, 150, 19, '#8a8272', 'center');
      G.text('去商店抽卡可以抽到宠物', G.W / 2, 180, 13, '#6d675c', 'center');
      return;
    }
    var p = D.PETS.filter(function (x) { return x.id === s.pet.slot; })[0];
    /* 卡片：80~248，贴图占上半，名字/等级/心情条分两行 —— 别让文字压在贴图上 */
    G.round(20, 80, G.W - 40, 168, 10, 'rgba(255,255,255,.05)', 'rgba(255,255,255,.12)');
    var pimg = S.petImg && S.petImg[s.pet.slot];
    if (pimg) {
      var ph = 104, pw = pimg.width / pimg.height * ph;
      ctx.drawImage(pimg, G.W / 2 - pw / 2, 86, pw, ph);
    } else {
      G.circle(G.W / 2, 138, 34, '#6a7f9a');
    }
    /* 名字 + 等级 */
    G.text(p.name, 34, 202, 17, '#fff', 'left', true);
    G.text('Lv ' + s.petLv + ' / ' + D.PET_MAX_LV, G.W - 34, 202, 13, '#c9bda4', 'right');
    /* 心情条 */
    G.text('心情', 34, 226, 12, '#9c9484');
    G.bar(72, 219, G.W - 130, 13, m / 100, m >= 80 ? '#7dff9b' : (m < 30 ? '#e0685a' : '#ffd23a'), 'rgba(0,0,0,.45)');
    G.text(moodTxt(m), G.W - 34, 226, 12, m >= 80 ? '#7dff9b' : '#c9bda4', 'right');
    G.text('心情好 → 词条数值 +10%', G.W / 2, 262, 11.5, '#8a8272', 'center');

    /* 词条 */
    G.text('宠物词条', 24, 288, 14, '#ffd88e', 'left', true);
    G.text('主属性 ' + (D.AFFIX[p.main] ? D.AFFIX[p.main].name : p.main) + ' +' + Math.round(p.base * 10 * (1 + (s.petLv - 1) * 0.05)), 24, 312, 13, '#c9bda4');

    /* 喂食 */
    var need = s.petLv * 50;
    S.btnFeed = { x: G.W / 2, y: G.H - 92, r: 62 };
    G.round(G.W / 2 - 130, G.H - 124, 260, 56, 12, 'rgba(60,90,60,.9)', 'rgba(140,230,150,.5)', 2);
    G.text('喂食升级', G.W / 2, G.H - 102, 17, '#d9ffdd', 'center', true);
    G.text('精粹×5 + 灵果' + need + '（灵果 ' + Math.floor(s.coins) + '）', G.W / 2, G.H - 82, 11.5, '#b6d9b8', 'center');
  }
  function moodTxt(m) { return m >= 80 ? '心情好' : m >= 50 ? '还行' : m >= 30 ? '有点闷' : '闷闷不乐'; }

  /* ============ 排行 ============ */
  function drawRank() {
    clearBtns();
    var cy = panelChrome('排行榜');
    drawBackBar();
    var s = S.save, y = 78;

    /* 假榜单：固定阶梯战力 + 玩家按自己的战力插进去。
       单机游戏没有真排行，但一个空空的"本机记录"面板很没劲 ——
       给个像样的榜单，玩家才有"我要爬上去"的目标。 */
    var list = [];
    for (var i = 0; i < FAKE_NAMES.length; i++) list.push({ n: FAKE_NAMES[i], p: FAKE_LADDER[i], me: false });
    var myP = power();
    list.push({ n: '我', p: myP, me: true });
    list.sort(function (a, b) { return b.p - a.p; });
    var myRank = 0;
    for (var j = 0; j < list.length; j++) { if (list[j].me) { myRank = j + 1; break; } }
    /* 只显示 6 名 —— 10 名会把下面的图鉴挤出屏幕 */
    var from = Math.max(0, Math.min(myRank - 3, list.length - 6));
    for (var k = from; k < Math.min(list.length, from + 6); k++) {
      var e = list[k], rk = k + 1;
      var medal = rk === 1 ? '#ffd23a' : rk === 2 ? '#d8d8d8' : rk === 3 ? '#d08a4a' : '#8a8272';
      G.round(20, y, G.W - 40, 40, 8, e.me ? 'rgba(255,220,150,.14)' : 'rgba(255,255,255,.04)',
        e.me ? 'rgba(255,220,150,.4)' : 'rgba(255,255,255,.08)');
      G.text(String(rk), 42, y + 20, 14, medal, 'center', true);
      G.text(e.n, 62, y + 20, 14, e.me ? '#ffd88e' : '#cfc6b0', 'left', e.me);
      G.text(fmt(e.p), G.W - 38, y + 20, 14, e.me ? '#ffd23a' : '#a89f8c', 'right');
      y += 44;
    }
    /* 我的名次 */
    G.round(20, y + 6, G.W - 40, 40, 8, 'rgba(255,220,150,.12)', 'rgba(255,220,150,.35)');
    G.text('我的名次', 36, y + 26, 14, '#ffd88e', 'left', true);
    G.text('第 ' + myRank + ' 名', G.W - 38, y + 26, 15, '#ffd23a', 'right', true);
    y += 56;

    /* 本机记录 */
    G.text('本机记录', 24, y, 13, '#8a8272', 'left');
    y += 18;
    var rows = [
      ['最高战力', fmt(s.best)],
      ['最远地图', (s.maxWave + 1) + ' 图'],
      ['累计击杀', s.kills + ' 只'],
      ['累计抽卡', s.pulls + ' 次'],
      ['爆装总数', s.items + ' 件']
    ];
    for (var r = 0; r < rows.length; r++) {
      G.text(rows[r][0], 28, y + r * 24, 12.5, '#9c9484');
      G.text(rows[r][1], G.W - 36, y + r * 24, 13, '#c9bda4', 'right');
    }
    G.text('（单机版：榜单为模拟数据，记录只存在本机）', G.W / 2, G.H - 26, 11, '#5c574d', 'center');
  }

  /* ============ 性别/皮肤选择 ============ */
  function drawPick() {
    clearBtns();
    G.round(0, 0, G.W, G.H, 0, '#14161a');
    G.text('《妖刀录》', G.W / 2, 110, 34, '#ffd88e', 'center', true);
    G.text('休闲 Q 版仙侠 · 打怪爆装', G.W / 2, 146, 14, '#9c9484', 'center');

    var sexes = [{ id: 'm', name: '男侠', col: '#5b6b7a', hair: '#1d1b1a' },
    { id: 'f', name: '女侠', col: '#7a6a86', hair: '#241b1c' }];
    for (var i = 0; i < sexes.length; i++) {
      var s = sexes[i], bx = G.W / 2 - 130 + i * 140;
      S['btnSex' + s.id] = { x: bx + 55, y: 250, r: 52 };
      G.circle(bx + 55, 250, 52, s.col, 'rgba(255,255,255,.18)', 2);
      G.circle(bx + 55, 240, 44, s.hair);
      G.text(s.name, bx + 55, 250, 16, '#fff', 'center', true);
    }
    G.text('选一个开始', G.W / 2, 330, 13, '#6d675c', 'center');

    /* 已选过才能取消（首次进入没有返回） */
    if (S.save.sex) {
      S.btnBack = { x: G.W - 40, y: 40, r: 17 };
      G.circle(S.btnBack.x, S.btnBack.y, 16, 'rgba(255,255,255,.12)');
      G.text('✕', S.btnBack.x, S.btnBack.y, 14, '#fff', 'center', true);
    }
  }

  /* ============ 输入分发 ============ */
  function onDown(x, y) {
    S.lastTap = { x: x, y: y };      /* 埋点：看收到的实际坐标 */
    if (G.sfx) { G.sfx.unlock(); G.sfx.play('click', 0.35); }
    S.autoManual = true;           // 一操作就交还控制权
    if (S.autoOn) { S.autoOn = false; S.autoManual = false; }
    /* 面板底部「返回主界面」条 —— 全局面板通用 */
    if (S.state !== 'battle' && S.state !== 'pick' && S.btnBack2 && hitRect(x, y, S.btnBack2)) {
      S.state = S.btnBack2.to || 'battle'; return;
    }
    /* 列表滚动：按下即记录锚点（拖动在 update 里轮询 G.T） */
    if (S.state === 'bag') { S._sy = y; S._sdown = true; S.bagV = 0; }
    if (S.state === 'maps') { S._sy = y; S.mapV = 0; }
    if (S.state === 'pick') {
      if (S.btnBack && hit(x, y, S.btnBack)) { S.state = S.pickPrev || 'battle'; return; }
      ['m', 'f'].forEach(function (k) {
        var b = S['btnSex' + k]; if (!b) return;
        if (hit(x, y, b)) {
          var first = !S.save.sex;
          S.save.sex = k;
          S.save.skin = k === 'm' ? 'cs1' : 'cs3';
          S.save.wskin = D.WEAPON_SKIN[0].id;   /* 不能再写死老 id，否则贴图查不到 */
          S.state = S.pickPrev || 'battle';
          S.pickPrev = null;
          if (first) newBattle();      /* 改形象不该重开一局 */
          G.persist();
        }
      });
      return;
    }
    if (S.state === 'bag') {
      if (S.btnBack && hit(x, y, S.btnBack)) { S.state = 'battle'; return; }
      if (S.btnLook && hit(x, y, S.btnLook)) { S.pickPrev = 'bag'; S.state = 'pick'; return; }
      if (S.btnSalvage && hit(x, y, S.btnSalvage)) { salvageJunk(); return; }
      if (S.btnSkin && hit(x, y, S.btnSkin)) { S.state = 'skin'; return; }
      if (S.btnPull10 && hit(x, y, S.btnPull10)) { S.pullRes = pull10(); S.state = 'pull'; return; }
      /* 装备格/物品行的点击挪到 onUp：拖动滚列表不该误触穿装备 */
      return;
    }
    if (S.state === 'sign') {
      if (S.btnBack && hit(x, y, S.btnBack)) { S.state = 'maps'; return; }
      if (S.btnClaim && hit(x, y, S.btnClaim)) { doSign(); return; }
      return;
    }
    if (S.state === 'maps') {
      if (S.btnBack && hit(x, y, S.btnBack)) { S.state = 'battle'; return; }
      if (S.btnSign && hit(x, y, S.btnSign)) { S.state = 'sign'; return; }
      /* 地图卡在滚动区里，点击挪到 onUp 判定 */
      return;
    }
    if (S.state === 'skin') {
      if (S.btnBack && hit(x, y, S.btnBack)) { S.state = 'bag'; return; }
      if (S.tabChar && hit(x, y, S.tabChar)) { S.skinTab = 'char'; return; }
      if (S.tabWeapon && hit(x, y, S.tabWeapon)) { S.skinTab = 'weapon'; return; }
      /* 人物造型 */
      for (var ck in S) {
        if (ck.indexOf('chBtn') === 0) {
          var cb2 = S[ck];
          if (cb2 && hit(x, y, cb2)) {
            var cs2 = D.CHAR_SKIN.filter(function (x) { return x.id === cb2.id; })[0];
            S.save.skin = cb2.id;
            S.stats = stats();
            toast('换上 ' + (cs2 ? cs2.name : '造型'));
            G.persist();
            return;
          }
        }
      }
      /* 武器造型 */
      for (var wsk in S) {
        if (wsk.indexOf('skBtn') === 0) {
          var wb = S[wsk];
          if (wb && hit(x, y, wb)) {
            S.save.wskin = wb.id;
            S.stats = stats();
            toast('换上 ' + wb.name);
            G.persist();
            return;
          }
        }
      }
      return;
    }
    if (S.state === 'upgrade') {
      if (S.btnBack && hit(x, y, S.btnBack)) { S.state = 'bag'; return; }
      if (S.btnEnh && hit(x, y, S.btnEnh)) { doEnhance(); return; }
      if (S.btnSell && hit(x, y, S.btnSell)) { sellEquipped(); return; }
      if (S.btnGem && hit(x, y, S.btnGem)) { toggleGem(); return; }
      for (var skk in S) {
        if (skk.indexOf('skUp') === 0) {
          var kb = S[skk];
          if (kb && hit(x, y, kb)) { upSk(kb.idx); return; }
        }
      }
      return;
    }
    if (S.state === 'pets') {
      if (S.btnBack && hit(x, y, S.btnBack)) { S.state = 'battle'; return; }
      if (S.btnFeed && hit(x, y, S.btnFeed)) { feedPet(); return; }
      return;
    }
    if (S.state === 'rank') {
      if (S.btnBack && hit(x, y, S.btnBack)) { S.state = 'battle'; return; }
      if (S.btnDex && hit(x, y, S.btnDex)) { claimDex(); return; }
      return;
    }
    if (S.state === 'pull') {
      if (S.btnBack && hit(x, y, S.btnBack)) { S.state = 'bag'; return; }
      return;
    }
    /* battle */
    if (S.btnAuto && hit(x, y, S.btnAuto)) { S.autoOn = !S.autoOn; S.autoManual = S.autoOn; return; }
    if (S.autoOn && S.btnAutoX && hit(x, y, S.btnAutoX)) { S.autoOn = false; S.autoManual = false; return; }
    /* 点地图名 → 选关 */
    if (S.btnMap && hit(x, y, S.btnMap)) { S.state = 'maps'; return; }
    if (S.btnBag && hit(x, y, S.btnBag)) { S.state = 'bag'; return; }
    if (S.btnPet && hit(x, y, S.btnPet)) { S.state = 'pets'; return; }
    if (S.btnRank && hit(x, y, S.btnRank)) { S.state = 'rank'; return; }
    if (S.btnMute && hit(x, y, S.btnMute)) {
      if (G.sfx) G.sfx.mute = !G.sfx.mute;
      S.save.muted = G.sfx && G.sfx.mute;
      toast(G.sfx && G.sfx.mute ? '已静音' : '音效开启');
      G.persist();
      return;
    }
    if (S.btnPull && hit(x, y, S.btnPull)) { S.pullRes = pull10(); S.state = 'pull'; return; }
    for (var i = 0; i < 3; i++) {
      var b2 = S['btnS' + i];
      if (b2 && hit(x, y, b2)) {
        if (S.hero.skCd[i] > 0) { toast(D.SKILLS[i].name + ' 冷却中'); return; }
        S.save.tipSkill = 1;
        if (S.arrow && S.arrow.kind === 'skill') S.arrow.t = 0;
        S.skillQueued = S.skillQueued || [0, 0, 0];
        S.skillQueued[i] = true;
        return;
      }
    }
  }

  /* 松手才判定的点击：拖动滚列表（G.T.moved）不算点击 */
  function onUp(x, y) {
    if (G.T.moved) return;
    if (S.state === 'maps') {
      if (S.btnDex && hit(x, y, S.btnDex)) { claimDex(); return; }
      for (var mk in S) {
        if (mk.indexOf('mapBtn') === 0) {
          var mb = S[mk];
          if (mb && hit(x, y, mb)) {
            if (mb.locked) {
              var mp2 = D.MAPS[mb.idx];
              var prev = mb.idx > 0 ? D.MAPS[mb.idx - 1] : null;
              toast('通关「' + (prev ? prev.name : '前一图') + '」后解锁');
              return;
            }
            S.save.map = mb.idx;
            S.map = D.MAPS[mb.idx];
            S.wave = 0; S.waveT = 1.0;
            S.mobs = []; S.drops = []; S.nums = []; S.eff = [];
            S.state = 'battle';
            toast('进入 ' + S.map.name);
            G.persist();
            return;
          }
        }
      }
      return;
    }
    if (S.state === 'bag') {
      for (var sk in S) {
        if (sk.indexOf('slotBtn') === 0) {
          var sb = S[sk];
          if (sb && hit(x, y, sb) && S.save.equip[sb.slot]) {
            S.upSlot = sb.slot; S.state = 'upgrade'; return;
          }
        }
      }
      for (var k in S) {
        if (k.indexOf('bagItem') === 0) {
          var b = S[k];
          if (x > b.x - 8 && x < b.x + b.w + 8 && Math.abs(y - b.y) < b.h / 2 + 6) {
            equipItem(b.idx); return;
          }
        }
      }
    }
  }
  function equipItem(idx) {
    var s = S.save, it = s.bag[idx];
    if (!it) return;
    var before = power();
    var scB = setCounts(s.equip);
    s.equip[it.slot] = it;
    s.bag.splice(idx, 1);
    S.stats = stats();
    var after = power();
    S.anim.power = 1.4; S.anim.powerFrom = before;
    if (after > s.best) s.best = after;
    toast('换上 ' + it.qn + '　战力 +' + (after - before));
    /* 套装达成提示（2 件/4 件都响，覆盖装备 toast） */
    var scA = setCounts(s.equip);
    for (var sid in scA) {
      if ((scA[sid] || 0) < 2) continue;
      var sd = D.SETS.filter(function (x) { return x.id === sid; })[0];
      if (!sd) continue;
      if ((scB[sid] || 0) < 2 && scA[sid] >= 2) toast('◈ ' + sd.name + ' 2 件套：' + sd.d2);
      if ((scB[sid] || 0) < 4 && scA[sid] >= 4) { toast('◈ ' + sd.name + ' 4 件套：' + sd.d4); if (G.sfx) G.sfx.play('rare'); }
    }
    G.persist();
  }
  function feedPet() {
    var s = S.save;
    if (!s.pet) { toast('还没有宠物'); return; }
    if (s.petLv >= D.PET_MAX_LV) { toast('已经满级了'); return; }
    /* ⚠️ 原来要"体力果"，但那资源全游戏 nowhere 拿得到 → 宠物只能喂两次。
       改用真正拿得到的资源：精粹（分解装备来的）+ 灵果。 */
    var need = s.petLv * 50;
    var needEss = 5;
    if ((s.essence || 0) < needEss) { toast('精粹不够，去分解装备'); return; }
    if (s.coins < need) { toast('灵果不够（需 ' + need + '）'); return; }
    s.coins -= need; s.essence -= needEss; s.petLv++;
    s.petMood = Math.min(D.MOOD_MAX, mood() + D.MOOD_FEED);
    s.petMoodAt = Date.now();
    S.stats = stats();
    toast('宠物升到 Lv' + s.petLv + '　心情 ' + moodTxt(mood()));
    G.persist();
  }

  /* ============ 抽卡结果 ============ */
  function drawPull() {
    clearBtns();
    var cy = panelChrome('抽 卡 结 果');
    var res = S.pullRes || [];
    /* 按品质从高到低排 —— 抽卡出史诗排在最前面才有仪式感 */
    res.sort(function (a, b) {
      return (D.QUAL_RANK[b.q] || 0) - (D.QUAL_RANK[a.q] || 0);
    });
    G.text('十连结果', G.W / 2, 46, 22, '#ffd88e', 'center', true);

    for (var i = 0; i < res.length; i++) {
      var it = res[i];
      var rank = D.QUAL_RANK[it.q] || 0;
      var cx = G.W / 2 + ((i % 5) - 2) * 62, cy = 130 + Math.floor(i / 5) * 96;
      /* 逐张翻开：每张间隔 0.06s */
      var reveal = (S.pullT || 0) - i * 0.06;
      if (reveal < 0) {
        /* 还没翻到：显示背面 */
        G.round(cx - 27, cy - 27, 54, 54, 8, 'rgba(40,44,52,.9)', 'rgba(255,255,255,.12)', 1.5);
        G.text('?', cx, cy, 22, 'rgba(255,255,255,.18)', 'center', true);
        continue;
      }
      var ap = Math.min(1, reveal / 0.18);
      var pop = 1 + (1 - ap) * 0.5;   /* 翻开时先弹一下 */
      /* 史诗以上：发光 + 呼吸 */
      if (rank >= 3) {
        var pu = 0.5 + 0.5 * Math.sin((S.pullT || 0) * 5);
        ctx.save();
        ctx.globalAlpha = 0.25 + pu * 0.35;
        ctx.fillStyle = it.col;
        ctx.beginPath();
        ctx.arc(cx, cy, 34 * pop, 0, 6.2832);
        ctx.fill();
        ctx.restore();
      }
      ctx.save();
      ctx.translate(cx, cy);
      ctx.scale(pop, pop);
      G.round(-27, -27, 54, 54, 8, 'rgba(255,255,255,.06)', it.col, rank >= 3 ? 2.5 : 1.5);
      /* 武器用贴图当图标 */
      var img = null;
      if (it.pet) {
        /* 宠物卡：圆球 + 名字 */
        G.circle(0, -4, 17, it.dup ? 'rgba(90,90,90,.8)' : 'rgba(125,255,155,.28)', it.col, 2);
        G.text(it.pet && it.slot ? (it.slot === 'beast' ? '兽' : it.slot === 'mount' ? '骑' : '友') : '宠',
          0, -4, 14, it.dup ? '#8a8272' : '#d9ffdd', 'center', true);
      } else if (it.wtype) {
        var sk = D.WEAPON_SKIN.filter(function (w) { return w.w === it.wtype; })[0];
        if (sk && S.wskinImg) img = S.wskinImg[sk.id];
      }
      if (img) {
        var ww = img.width / img.height * 40;
        ctx.drawImage(img, -ww / 2, -20, ww, 40);
      } else {
        G.text(it.qn, 0, -5, 13, it.col, 'center', true);
      }
      ctx.restore();
      G.text(it.pet ? (it.dup ? '重复' : '宠物') : slotName(it.slot), cx, cy + 20, 10, '#a89f8c', 'center');
      /* 传说/神话额外标个角 */
      if (rank >= 4) G.text('★', cx + 20, cy - 20, 13, it.col, 'center', true);
    }
    var hasPet = false, hasDup = false;
    for (var pi = 0; pi < res.length; pi++) { if (res[pi].pet) { if (res[pi].dup) hasDup = true; else hasPet = true; } }
    G.text(hasPet ? '获得宠物！去「宠物」面板看看' : (hasDup ? '重复宠物已折成 10 精粹' : '已入背包'),
      G.W / 2, 340, 13, hasPet ? '#7dff9b' : '#8a8272', 'center');
    S.btnBack = { x: G.W / 2, y: G.H - 60, r: 58 };
    G.round(G.W / 2 - 90, G.H - 90, 180, 56, 12, 'rgba(50,90,60,.9)', 'rgba(140,230,150,.5)', 2);
    G.text('收下', G.W / 2, G.H - 62, 18, '#d9ffdd', 'center', true);
  }

  /* ============ 主循环 ============ */
  function update(dt) {
    if (!S) return;
    if (S.shake > 0) S.shake = Math.max(0, S.shake - dt);
    if (S.hint && S.hint.t > 0) S.hint.t -= dt;
    if (S.arrow) {
      S.arrow.t -= dt;
      if (S.arrow.kind === 'move') {
        /* ⚠️ update() 这个作用域里没有 h，只有 S.hero —— 用 h 会 ReferenceError，
           而且 update 一抛错后面的 draw 就不执行了（整个画面冻住） */
        S.arrow.x = S.hero ? S.hero.x : 0;
        S.arrow.y = S.hero ? S.hero.y + 40 : 0;
        /* 移动教会了 → 接着教放技能（只教必要规则，分步来） */
        if (S.arrow.t <= 0 && !S.save.tipSkill && S.mobs.length > 0 && S.btnS0) {
          S.arrow = { x: S.btnS0.x, y: S.btnS0.y - 36, t: 4.5, kind: 'skill' };
        }
      } else if (S.arrow.kind === 'skill' && S.btnS0) {
        S.arrow.x = S.btnS0.x; S.arrow.y = S.btnS0.y - 36;
      }
    }
    if (S.comboT > 0) { S.comboT -= dt; if (S.comboT <= 0) S.combo = 0; }
    if (S.comboBuff > 0) S.comboBuff -= dt;
    if (S.lvFx > 0) S.lvFx -= dt;
    if (S.banner && S.banner.t > 0) S.banner.t -= dt;
    /* 背包列表滚动：拖动跟随 + 松手惯性 */
    if (S.state === 'bag') {
      if (G.T.down && G.T.moved) {
        var sdy = G.T.y - (S._sy !== undefined ? S._sy : G.T.y);
        S._sy = G.T.y;
        S.bagScroll = Math.max(0, Math.min(S.bagMax || 0, (S.bagScroll || 0) - sdy));
        S.bagV = -sdy;
      } else if (S.bagV) {
        S.bagScroll = Math.max(0, Math.min(S.bagMax || 0, (S.bagScroll || 0) + S.bagV));
        S.bagV *= 0.9;
        if (Math.abs(S.bagV) < 0.4) S.bagV = 0;
      }
    }
    if (S.state === 'maps') {
      if (G.T.down && G.T.moved) {
        var mdy = G.T.y - (S._sy !== undefined ? S._sy : G.T.y);
        S._sy = G.T.y;
        S.mapScroll = Math.max(0, Math.min(S.mapMax || 0, (S.mapScroll || 0) - mdy));
        S.mapV = -mdy;
      } else if (S.mapV) {
        S.mapScroll = Math.max(0, Math.min(S.mapMax || 0, (S.mapScroll || 0) + S.mapV));
        S.mapV *= 0.9;
        if (Math.abs(S.mapV) < 0.4) S.mapV = 0;
      }
    }
    if (S.state === 'pull' && S.pullT !== undefined) S.pullT += dt;
    if (S.state === 'battle') {
      updateBattle(dt);
      var pw = power(S.stats);
      if (pw > S.save.best) { S.save.best = pw; }
    }
  }
  function draw() {
    if (!S) return;
    if (S.state === 'pick') return drawPick();
    if (S.state === 'battle') { S.panelA = 0; drawBattle(); return; }
    /* 面板统一走打开动画（上滑渐入 ~0.15s）——学成熟游戏的进场反馈 */
    var fn = { bag: drawBag, upgrade: drawUpgrade, skin: drawSkins, maps: drawMaps,
      sign: drawSign, pets: drawPets, rank: drawRank, pull: drawPull }[S.state];
    if (!fn) { drawBattle(); return; }
    if (S.panelState !== S.state) { S.panelState = S.state; S.panelA = 1; }
    if (S.panelA > 0) S.panelA = Math.max(0, S.panelA - (G.dt || 0.016) * 7);
    var k = S.panelA * S.panelA;      /* ease-out */
    ctx.save();
    ctx.globalAlpha = 1 - k * 0.85;
    ctx.translate(0, k * 56);
    fn();
    ctx.restore();
  }

  /* ============ 启动 ============ */
  function start() {
    var s = load();
    S = {
      save: s, state: s.sex ? 'battle' : 'pick',
      hero: null, mobs: [], drops: [], nums: [], eff: [],
      wave: 0, waveT: 1.2, map: D.MAPS[s.map] || D.MAPS[0],
      stats: null, autoOn: false, autoManual: false, pickPrev: null,
      combo: 0, comboT: 0, comboBest: 0,   /* 连击 */
      skillQueued: [0, 0, 0], toast: '', toastT: 0, bagScroll: 0, bagV: 0, bagMax: 0, mapScroll: 0, mapV: 0, mapMax: 0,
      anim: { power: 0, powerFrom: 0 }, pullRes: []
    };
    S.stats = stats();          /* 必须在 S 赋值之后：stats() 读 S.save */
    if (S.state === 'battle') newBattle();
    grantOffline();
    /* 微信切后台再回来时也结算一次（浏览器垫片里 onShow 是空实现，不会触发） */
    try { if (window.wx && window.wx.onShow) window.wx.onShow(function () { grantOffline(); }); } catch (e) { }
    preloadArt();
    if (G.loadSfx) {
      G.loadSfx(['click', 'hit', 'crit', 'drop', 'rare', 'pull', 'upgrade', 'boss', 'gem', 'pet']);
      if (G.sfx) G.sfx.mute = !!s.muted;
    }
    G.update = update;      /* ⚠️ 必须挂上去：boot.js 的主循环只认 G.update / G.draw */
    G.draw = draw;
    G.setHandlers({ down: onDown, up: onUp });
    G.loop();
  }

  window.GAME = { start: start, S: function () { return S; }, power: power, stats: stats };
})();

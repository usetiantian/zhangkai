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
      bag: [],
      /* 开局送一把基础妖刀 —— 空手开场没有打击感，也没法试强化 */
      equip: { weapon: { uid: 'start_w', q: 'g', qn: '精良妖刀', col: '#5ec46a', slot: 'weapon',
        wtype: 'blade', atk: 7, range: 96, cd: 0.55, dmgMul: 1.05, aff: { atk: 2 }, lv: 0 },
        head: null, body: null, neck: null },
      pet: null, petLv: 1, petMood: 70, petMoodAt: Date.now(),
      coins: 0, items: 0, log: []
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
    return s;
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
    var s = S.save, st = { atk: 10, def: 0, hp: 120, crit: 5, critDmg: 50, aspd: 0, luck: 0, vamp: 0, drop: 0 };
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
    st.atk = Math.round(st.atk);
    return st;
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
  }

  function spawnMob(id) {
    var m = D.MONS.filter(function (x) { return x.id === id; })[0];
    if (!m) return;
    /* 精英/妖王登场：横幅 + 震屏 */
    if (m.boss) {
      /* 妖王的名字本身就带"妖王"，别再拼一遍 */
      S.banner = { txt: (m.boss === 2 ? m.name : '精英 · ' + m.name), t: 2.0, col: m.boss === 2 ? '#ff5a6e' : '#ffd23a' };
      S.shake = 0.45;
    }
    var a = rnd(0, 6.2832), r = rnd(430, 560);
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
    if (idle && !S.autoOn) { S.autoOn = true; }
    if (!idle && S.autoOn && S.autoManual) { S.autoOn = false; }

    /* —— 移动 —— */
    var tx = null, ty = null;
    if (S.autoOn) {
      var near = nearest(h, 520);
      if (near) { tx = near.x; ty = near.y; }
    } else if (G.T.down) {
      var dx = G.T.dx, dy = G.T.dy;
      var len = Math.sqrt(dx * dx + dy * dy);
      if (len > 6) { tx = h.x + dx / len * 200; ty = h.y + dy / len * 200; }
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
          toast('首通奖励：金币 +' + rw + '　红宝石 +' + S.map.id);
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
        deal(tg, wpn.atk * wpn.dmgMul * (1 + (st.crit - 5) * 0.004) * rnd(0.92, 1.08), st, true);
      }
    }

    /* —— 技能（手动点 or 自动放）—— */
    for (var i = 0; i < 3; i++) {
      h.skCd[i] -= dt;
      var sk = D.SKILLS[i];
      if (h.skCd[i] <= 0 && (S.autoOn || S.skillQueued[i])) {
        var tgt = nearest(h, sk.range);
        if (tgt) {
          h.skCd[i] = sk.cd;
          if (S.skillQueued[i]) S.skillQueued[i] = false;
          if (sk.aoe) {
            S.mobs.forEach(function (m) { if (dist(m, h) <= sk.range) deal(m, sk.dmg * (st.atk * 0.22), st, false); });
            /* 旋风(1) = 风环扩散；妖火(2) = 火球爆开 */
            S.eff.push({ x: h.x, y: h.y, r: 0, r2: sk.range, t: 0.5, dur: 0.5, col: sk.col, kind: i === 1 ? 'wind' : 'fire' });
          } else {
            deal(tgt, sk.dmg * (st.atk * 0.30), st, false);
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
      S.nums.push({ x: m.x, y: m.y, v: -26, t: 1.0, txt: '+' + m.coin, col: '#ffd76a' });
      /* 掉落保底链：连续太久没出史诗就必出（不然非酋会彻底放弃）
         —— 调研口径的保底链：5-8 / 10-15 / 50 / 100 / 150-200 次 */
      var pityHit = s.dry >= D.PITY_EPIC;
      /* 精英和妖王掉宝石（比装备低得多） */
      if (m.boss && Math.random() < (m.boss === 2 ? 0.85 : 0.35)) {
        var gd2 = weightedPick(D.GEMS);
        s.gems = s.gems || {};
        s.gems[gd2.id] = (s.gems[gd2.id] || 0) + 1;
        S.nums.push({ x: m.x, y: m.y - 40, v: -30, t: 1.4, txt: gd2.name + ' ×1', col: gd2.col, big: true });
        toast('获得 ' + gd2.name + '！');
      }
      if (pityHit || Math.random() < m.drop * (1 + st.luck * D.LUCK_PER)) {
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
    if (D.MONS_IMG) {
      for (var mk in D.MONS_IMG) list.push({ key: mk, path: 'assets/' + D.MONS_IMG[mk] });
    }
    if (D.MAPS_IMG) {
      for (var gk in D.MAPS_IMG) list.push({ key: 'map' + gk, path: 'assets/' + D.MAPS_IMG[gk] });
    }
    G.loadImgs(list, function (out) {
      S.heroImg = { m: out['m'] || null, f: out['f'] || null };
      S.wskinImg = out;
      /* 人物皮肤贴图（cs1~cs4），跟武器贴图分开存 */
      S.charImg = {};
      if (D.CHAR_SKIN) for (var ck2 in D.CHAR_SKIN) S.charImg[D.CHAR_SKIN[ck2].id] = out[D.CHAR_SKIN[ck2].id] || null;
      /* 怪物和地图底单独拎出来，避免和武器的 key 混在一起 */
      S.mobImg = {}; S.mapImg = {};
      for (var k in out) {
        if (D.MONS_IMG && D.MONS_IMG[k]) S.mobImg[k] = out[k];
        else if (k.indexOf('map') === 0) S.mapImg[k.slice(3)] = out[k];
      }
      /* 地图底做成 pattern，跟着相机滚 */
      S.mapPat = {};
      for (var id in S.mapImg) {
        try { S.mapPat[id] = ctx.createPattern(S.mapImg[id], 'repeat'); } catch (e) { }
      }
    });
  }
  function deal(m, dmg, st, isBasic) {
    var crit = Math.random() * 100 < st.crit;
    if (crit) dmg *= (1 + st.critDmg / 100);
    m.hp -= dmg; m.hit = 0.14;
    S.nums.push({ x: m.x + rnd(-10, 10), y: m.y - 18, v: -34, t: 0.85, txt: (crit ? '暴 ' : '') + Math.round(dmg), col: crit ? '#ffd23a' : '#fff' });
    if (st.vamp > 0) S.hero.hp = Math.min(S.hero.maxhp, S.hero.hp + dmg * st.vamp / 100 * 0.4);
  }

  /* ============ 抽卡（广告）============ */
  function pull10() {
    var s = S.save, got = [];
    S.pullT = 0;              /* 翻牌动画计时 */
    for (var i = 0; i < 10; i++) {
      s.pulls++;
      /* 6% 出宠物卡（已有宠物则折精粹） */
      if (Math.random() < 0.06) {
        var pc = rollPetCard(s);
        if (!s.pet) {
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

  /* ---- 按钮系统 ---- */
  /* hit(x, y, b)：b 是**按钮对象**（含 x/y/r），不是半径数字。
     ⚠️ 之前写成 hit(x,y,r) 却用 r.x → NaN 比较恒为 false → 所有按钮都点不动。 */
  function hit(x, y, b) {
    if (!b) return false;
    var dx = x - b.x, dy = y - b.y;
    return dx * dx + dy * dy <= b.r * b.r;
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

    /* 屏幕暗角：把注意力收到中间的角色上 */
    var vg = ctx.createRadialGradient(G.W / 2, G.H / 2, G.H * 0.34, G.W / 2, G.H / 2, G.H * 0.78);
    vg.addColorStop(0, 'rgba(0,0,0,0)');
    vg.addColorStop(1, 'rgba(0,0,0,.42)');
    ctx.fillStyle = vg;
    ctx.fillRect(0, 0, G.W, G.H);

    /* ============ HUD ============ */
    var pd = G.W * 0.5;
    G.round(12, 14, pd - 24, 42, 8, 'rgba(0,0,0,.5)');
    /* 地图名可点 → 选关（加 ▾ 提示玩家能点） */
    S.btnMap = { x: 70, y: 28, r: 60 };
    G.text(S.map.name, 24, 28, 16, '#ffd88e', 'left', true);
    G.text('▾', 24 + String(S.map.name).length * 16 + 4, 29, 12, '#ffd88e', 'left');
    G.text('第 ' + (S.wave + 1) + '/' + S.map.waves + ' 波　妖 ' + S.mobs.length, 24, 46, 12.5, '#c9bda4');

    /* 战力 */
    G.round(G.W - 12 - 118, 14, 118, 30, 8, 'rgba(0,0,0,.5)');
    var pw = power(st);
    G.text('战力 ' + fmt(pw), G.W - 24, 29, 16, '#ffd23a', 'right', true);
    /* 背包/宠物/排行/抽卡界面的右上「✕」要和标题错开 */
    if (S.anim.power > 0) {
      ctx.globalAlpha = Math.min(1, S.anim.power);
      G.text('+' + (pw - S.anim.powerFrom), G.W - 24, 50, 14, '#7dff9b', 'right', true);
      ctx.globalAlpha = 1;
    }

    /* 自动战斗开关 */
    S.btnAuto = { x: G.W - 44, y: 74, r: 17 };
    G.circle(S.btnAuto.x, S.btnAuto.y, 17, S.autoOn ? '#3f7f4f' : 'rgba(30,30,30,.65)', 'rgba(255,255,255,.35)', 1.5);
    G.text('自动', S.btnAuto.x, S.btnAuto.y, 12, S.autoOn ? '#c9ffd0' : '#c8c0b0', 'center', true);

    /* 自动战斗提示条（可取消） */
    if (S.autoOn) {
      G.round(G.W / 2 - 130, 62, 260, 32, 8, 'rgba(20,40,25,.82)');
      G.text('自动战斗中 · 触碰屏幕切回', G.W / 2 - 8, 78, 13.5, '#b8f5c4', 'center');
      S.btnAutoX = { x: G.W / 2 + 116, y: 78, r: 13 };
      G.circle(S.btnAutoX.x, S.btnAutoX.y, 12, 'rgba(255,255,255,.14)');
      G.text('✕', S.btnAutoX.x, S.btnAutoX.y, 13, '#fff', 'center', true);
    }

    /* 技能按钮 */
    for (var i = 0; i < 3; i++) {
      var sk2 = D.SKILLS[i];
      /* 技能排一排放在底部功能键**上方**，否则会和「抽卡」按钮叠在一起点不到 */
      var bx = G.W - 48 - (2 - i) * 70, by = G.H - 116;
      S['btnS' + i] = { x: bx, y: by, r: 27 };
      var ready = h.skCd[i] <= 0;
      G.circle(bx, by, 27, ready ? 'rgba(60,70,90,.86)' : 'rgba(40,42,50,.7)', ready ? sk2.col : 'rgba(255,255,255,.2)', 2);
      G.text(sk2.name, bx, by, 13, ready ? '#fff' : '#8a8a90', 'center', true);
      if (!ready) {
        var cd = h.skCd[i] / sk2.cd;
        ctx.globalAlpha = 0.55;
        G.bar(bx - 22, by + 32, 44, 4, 1 - cd, sk2.col);
        ctx.globalAlpha = 1;
      }
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
    G.round(0, 0, G.W, G.H, 0, 'rgba(12,12,14,.97)');
    G.text('选择地图', 24, 40, 24, '#ffd88e', 'left', true);
    /* 每日签到入口（有红点提示） */
    var canSign = canSignIn();
    S.btnSign = { x: 118, y: 40, r: 17 };
    G.round(92, 26, 52, 28, 14, canSign ? 'rgba(160,70,40,.9)' : 'rgba(255,255,255,.08)',
      canSign ? 'rgba(255,190,90,.6)' : 'rgba(255,255,255,.15)', 1);
    G.text('签到', 118, 40, 13, canSign ? '#ffe2b0' : '#6d675c', 'center', true);
    if (canSign) G.circle(142, 24, 5, '#ff5a6e');
    S.btnBack = { x: G.W - 40, y: 40, r: 17 };
    G.circle(S.btnBack.x, S.btnBack.y, 16, 'rgba(255,255,255,.12)');
    G.text('✕', S.btnBack.x, S.btnBack.y, 14, '#fff', 'center', true);
    var pw = power();
    G.text('战力 ' + fmt(pw), G.W - 64, 64, 13, '#ffd23a', 'right');

    var s = S.save;
    var y = 92;
    for (var i = 0; i < D.MAPS.length; i++) {
      var mp = D.MAPS[i];
      var unlocked = (i <= s.maxWave);
      var cur = (S.map && S.map.id === mp.id);
      var cleared = s.cleared && s.cleared[mp.id];
      /* 卡片底色用地图自己的地面色，锁定的压灰 */
      G.round(16, y, G.W - 32, 152, 12,
        unlocked ? (cur ? 'rgba(255,220,150,.10)' : 'rgba(255,255,255,.045)') : 'rgba(30,30,32,.6)',
        cur ? '#ffd88e' : (unlocked ? 'rgba(255,255,255,.14)' : 'rgba(255,255,255,.07)'), cur ? 2 : 1);
      /* 左边一条地面色的色带 */
      G.round(16, y, 8, 152, 4, unlocked ? mp.ground2 : '#3a3a3c');

      G.text(mp.name, 38, y + 24, 18, unlocked ? '#f0e6d2' : '#6d675c', 'left', true);
      G.text(mp.waves + ' 波', 38, y + 48, 12, unlocked ? '#a89f8c' : '#55504a', 'left');
      /* 怪物 */
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
      G.text(names.join(' · '), 38, y + 70, 12, unlocked ? '#c9bda4' : '#55504a', 'left');
      /* 推荐战力 */
      var strong = pw >= mp.pw;
      G.text('推荐战力 ' + fmt(mp.pw), 38, y + 94, 12, strong ? '#7dff9b' : '#e0685a', 'left');
      if (unlocked) {
        G.text(cleared ? '已通关（可重复刷）' : (cur ? '当前地图' : '点击进入'),
          G.W - 32, y + 94, 12, cleared ? '#8a8272' : (cur ? '#ffd88e' : '#a89f8c'), 'right');
        if (pw < mp.pw) G.text('⚠ 战力偏低', G.W - 32, y + 118, 12, '#e0685a', 'right');
      } else {
        G.text('🔒 通关「' + D.MAPS[i - 1].name + '」解锁', G.W - 32, y + 94, 12, '#6d675c', 'right');
      }
      /* 缩略地面色块 */
      G.round(38, y + 112, 84, 26, 6, unlocked ? mp.ground : '#333');
      for (var d2 = 0; d2 < 3; d2++) {
        G.circle(52 + d2 * 26, y + 125, 5, unlocked ? mp.deco[d2 % 3] : '#3c3c3e');
      }
      S['mapBtn' + i] = { x: G.W / 2, y: y + 76, r: 76, idx: i, locked: !unlocked };
      y += 168;
    }
    G.text('低地图掉低级装备，高地图掉好东西 —— 自由切换', G.W / 2, G.H - 40, 11.5, '#6d675c', 'center');
  }

  /* ============ 每日签到面板 ============ */
  function todayKey() {
    var d = new Date();
    return d.getFullYear() + '-' + (d.getMonth() + 1) + '-' + d.getDate();
  }
  function canSignIn() { return S.save.signDate !== todayKey(); }

  function drawSign() {
    G.round(0, 0, G.W, G.H, 0, 'rgba(12,12,14,.97)');
    G.text('每日签到', 24, 40, 24, '#ffd88e', 'left', true);
    S.btnBack = { x: G.W - 40, y: 40, r: 17 };
    G.circle(S.btnBack.x, S.btnBack.y, 16, 'rgba(255,255,255,.12)');
    G.text('✕', S.btnBack.x, S.btnBack.y, 14, '#fff', 'center', true);
    G.text('连签 ' + S.save.signDay + ' 天', G.W - 64, 64, 13, '#c9bda4', 'right');

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
        G.text('金币', bx + bw / 2, ry - 8, 11, '#8a8272', 'center');
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
    G.round(0, 0, G.W, G.H, 0, 'rgba(12,12,14,.97)');
    G.text('造型', 24, 40, 24, '#ffd88e', 'left', true);
    S.btnBack = { x: G.W - 40, y: 40, r: 17 };
    G.circle(S.btnBack.x, S.btnBack.y, 16, 'rgba(255,255,255,.12)');
    G.text('✕', S.btnBack.x, S.btnBack.y, 14, '#fff', 'center', true);

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
      S['skin' + w.id] = { x: bx + (cw - 10) / 2, y: by + 60, r: 46, id: w.id, name: w.name };
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
      S['char' + c.id] = { x: bx + bw / 2, y: 250, r: 80, id: c.id };
    }
    G.text('人物造型', G.W / 2, G.H - 40, 11.5, '#6d675c', 'center');
  }
  function by0(y, h) { return y + 12; }

  function drawUpgrade() {
    G.round(0, 0, G.W, G.H, 0, 'rgba(10,10,12,.97)');
    var it = S.save.equip[S.upSlot];
    if (!it) { S.state = 'bag'; return; }
    var lv = it.lv || 0;

    G.text('强化', 24, 40, 24, '#ffd88e', 'left', true);
    S.btnBack = { x: G.W - 40, y: 40, r: 17 };
    G.circle(S.btnBack.x, S.btnBack.y, 16, 'rgba(255,255,255,.12)');
    G.text('✕', S.btnBack.x, S.btnBack.y, 14, '#fff', 'center', true);

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

    /* 资源 */
    G.text('金币 ' + Math.floor(S.save.coins), 24, G.H - 150, 13, '#ffd76a', 'left');
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
    G.text(lv >= D.ENH_MAX ? '' : ('金币 ' + coin + ' · 精粹 ' + ess),
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
    if (s.coins < coin) { toast('金币不够'); return; }
    if ((s.essence || 0) < ess) { toast('精粹不够，去分解装备'); return; }
    s.coins -= coin; s.essence -= ess;
    it.lv = lv + 1;
    var before = power();
    S.stats = stats();
    var after = power();
    S.anim.power = 1.4; S.anim.powerFrom = before;
    if (after > s.best) s.best = after;
    toast('强化成功 +' + it.lv + '　战力 +' + (after - before));
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
    G.round(0, 0, G.W, G.H, 0, 'rgba(12,12,14,.96)');
    G.text('背包', 24, 40, 24, '#ffd88e', 'left', true);
    G.text('战力 ' + fmt(power()), G.W - 64, 40, 18, '#ffd23a', 'right', true);
    G.text('点击装备即换上', G.W - 64, 62, 12, '#9c9484', 'right');

    /* 已装备 4 格 */
    var slots = D.SLOTS;
    for (var i = 0; i < slots.length; i++) {
      var sl = slots[i], bx = 16 + i * ((G.W - 32) / 4), bw = (G.W - 32) / 4 - 8;
      var it = S.save.equip[sl.id];
      G.round(bx, 78, bw, 74, 8, 'rgba(255,255,255,.05)', 'rgba(255,255,255,.14)');
      G.text(sl.name, bx + bw / 2, 92, 12, '#9c9484', 'center');
      S['slotBtn' + sl.id] = { x: bx + bw / 2, y: 115, r: 40, slot: sl.id };
      if (it) {
        G.round(bx + 8, 100, bw - 16, 34, 5, 'rgba(255,255,255,.07)', it.col, 1.5);
        G.text(it.qn + (it.lv ? ' +' + it.lv : ''), bx + bw / 2, 114, 12.5, it.col, 'center', true);
        G.text(affixTxt(it), bx + bw / 2, 130, 10.5, '#bdb49e', 'center');
      } else {
        G.text('空', bx + bw / 2, 117, 13, '#6d675c', 'center');
      }
    }

    /* 背包列表 */
    var y = 168, n = 0;
    var gemTot = 0;
    if (S.save.gems) for (var gk in S.save.gems) gemTot += S.save.gems[gk];
    G.text('持有 ' + S.save.bag.length + ' 件' + (gemTot ? ' · 宝石 ' + gemTot : ''), 24, y, 13, '#9c9484');
    y += 22;
    for (var j = S.save.bag.length - 1; j >= 0 && n < 40; j--) {
      var it2 = S.save.bag[j];
      G.round(16, y, G.W - 32, 52, 7, 'rgba(255,255,255,.045)', 'rgba(255,255,255,.10)');
      G.round(24, y + 8, 8, 36, 4, it2.col);
      G.text(it2.qn, 42, y + 16, 14, it2.col, 'left', true);
      G.text(slotName(it2.slot) + (it2.wtype ? '·' + D.WEAPONS[it2.wtype].name : ''), 42, y + 34, 11.5, '#a89f8c');
      G.text(affixTxt(it2), G.W - 28, y + 26, 11.5, '#cfc6b0', 'right');
      S['bagItem' + j] = { x: 24, y: y + 26, r: 0, w: G.W - 48, h: 26, idx: j };
      y += 58; n++;
    }
    if (!S.save.bag.length) G.text('还没有装备 · 去打怪爆', G.W / 2, 260, 15, '#6d675c', 'center');

    /* 抽卡按钮 */
    S.btnPull10 = { x: G.W / 2, y: G.H - 52, r: 62 };
    G.round(G.W / 2 - 130, G.H - 86, 260, 56, 12, 'rgba(120,70,30,.9)', 'rgba(255,190,90,.55)', 2);
    G.text('看广告 · 十连抽', G.W / 2, G.H - 64, 17, '#ffe2b0', 'center', true);
    G.text('每 8 次必出史诗以上（当前 ' + (S.save.pulls % 8) + '/8）', G.W / 2, G.H - 44, 11.5, '#d9b98a', 'center');

    S.btnBack = { x: G.W - 40, y: 40, r: 17 };
    G.circle(S.btnBack.x, S.btnBack.y, 16, 'rgba(255,255,255,.12)');
    G.text('✕', S.btnBack.x, S.btnBack.y, 14, '#fff', 'center', true);

    /* 改形象：回性别选择页重选（装备/等级/进度都保留） */
    /* 一键分解：放在列表标题行右边（原来放左下角会和「十连抽」按钮重叠） */
    S.btnSalvage = { x: G.W - 62, y: 168, r: 46 };
    G.round(G.W - 118, 154, 108, 28, 14, 'rgba(120,70,30,.85)', 'rgba(255,190,90,.45)', 1.5);
    G.text('一键分解', G.W - 62, 168, 12.5, '#ffe2b0', 'center', true);

    /* 造型：换武器皮肤 */
    S.btnSkin = { x: G.W - 196, y: 40, r: 17 };
    G.round(S.btnSkin.x - 34, S.btnSkin.y - 14, 68, 28, 14, 'rgba(255,255,255,.10)', 'rgba(255,255,255,.22)', 1);
    G.text('造型', S.btnSkin.x, S.btnSkin.y, 13, '#e6dcc6', 'center', true);

    S.btnLook = { x: G.W - 118, y: 40, r: 17 };
    G.round(S.btnLook.x - 38, S.btnLook.y - 14, 76, 28, 14, 'rgba(255,255,255,.10)', 'rgba(255,255,255,.22)', 1);
    G.text('改形象', S.btnLook.x, S.btnLook.y, 13, '#e6dcc6', 'center', true);
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
    G.round(0, 0, G.W, G.H, 0, 'rgba(12,12,14,.96)');
    G.text('宠物', 24, 40, 24, '#ffd88e', 'left', true);
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
    G.round(20, 80, G.W - 40, 120, 10, 'rgba(255,255,255,.05)', 'rgba(255,255,255,.12)');
    G.circle(G.W / 2, 128, 34, '#6a7f9a');
    G.text(p.name, G.W / 2, 128, 17, '#fff', 'center', true);
    G.text('Lv ' + s.petLv + ' / ' + D.PET_MAX_LV, G.W / 2, 172, 14, '#c9bda4', 'center');
    /* 心情条 */
    G.text('心情', 40, 190, 12, '#9c9484');
    G.bar(80, 183, G.W - 160, 14, m / 100, m >= 80 ? '#7dff9b' : (m < 30 ? '#e0685a' : '#ffd23a'), 'rgba(0,0,0,.45)');
    G.text(moodTxt(m), G.W - 44, 190, 12, m >= 80 ? '#7dff9b' : '#c9bda4', 'right');
    G.text('心情好 → 词条数值 +10%', G.W / 2, 208, 11.5, '#8a8272', 'center');

    /* 词条 */
    G.text('宠物词条', 24, 232, 14, '#ffd88e', 'left', true);
    G.text('主属性 ' + (D.AFFIX[p.main] ? D.AFFIX[p.main].name : p.main) + ' +' + Math.round(p.base * 10 * (1 + (s.petLv - 1) * 0.05)), 24, 256, 13, '#c9bda4');

    /* 喂食 */
    var need = s.petLv * 50;
    S.btnFeed = { x: G.W / 2, y: G.H - 92, r: 62 };
    G.round(G.W / 2 - 130, G.H - 124, 260, 56, 12, 'rgba(60,90,60,.9)', 'rgba(140,230,150,.5)', 2);
    G.text('喂食升级', G.W / 2, G.H - 102, 17, '#d9ffdd', 'center', true);
    G.text('体力果×1 + 灵果' + need + '（当前 ' + s.coins + '）', G.W / 2, G.H - 82, 11.5, '#b6d9b8', 'center');
  }
  function moodTxt(m) { return m >= 80 ? '心情好' : m >= 50 ? '还行' : m >= 30 ? '有点闷' : '闷闷不乐'; }

  /* ============ 排行 ============ */
  function drawRank() {
    G.round(0, 0, G.W, G.H, 0, 'rgba(12,12,14,.96)');
    G.text('本机排行', 24, 40, 24, '#ffd88e', 'left', true);
    S.btnBack = { x: G.W - 40, y: 40, r: 17 };
    G.circle(S.btnBack.x, S.btnBack.y, 16, 'rgba(255,255,255,.12)');
    G.text('✕', S.btnBack.x, S.btnBack.y, 14, '#fff', 'center', true);
    var s = S.save, y = 96;
    var rows = [
      ['最高战力', fmt(s.best)],
      ['最远地图', (s.maxWave + 1) + ' 图'],
      ['累计击杀', s.kills + ' 只'],
      ['累计抽卡', s.pulls + ' 次'],
      ['爆装总数', s.items + ' 件'],
      ['当前灵果', s.coins]
    ];
    rows.forEach(function (r) {
      G.round(24, y, G.W - 48, 44, 8, 'rgba(255,255,255,.045)');
      G.text(r[0], 40, y + 22, 14, '#c9bda4');
      G.text(r[1], G.W - 40, y + 22, 16, '#ffd23a', 'right', true);
      y += 52;
    });
    G.text('（单机版：记录只存在本机）', G.W / 2, y + 20, 12, '#6d675c', 'center');
  }

  /* ============ 性别/皮肤选择 ============ */
  function drawPick() {
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
    S.autoManual = true;           // 一操作就交还控制权
    if (S.autoOn) { S.autoOn = false; S.autoManual = false; }
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
      /* 点已装备的格子 → 强化面板 */
      for (var sk in S) {
        if (sk.indexOf('slotBtn') === 0) {
          var sb = S[sk];
          if (sb && hit(x, y, sb) && S.save.equip[sb.slot]) {
            S.upSlot = sb.slot; S.state = 'upgrade'; return;
          }
        }
      }
      if (S.btnPull10 && hit(x, y, S.btnPull10)) { S.pullRes = pull10(); S.state = 'pull'; return; }
      for (var k in S) {
        if (k.indexOf('bagItem') === 0) {
          var b = S[k];
          if (x > b.x - 8 && x < b.x + b.w + 8 && Math.abs(y - b.y) < b.h / 2 + 6) {
            equipItem(b.idx); return;
          }
        }
      }
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
      for (var mk in S) {
        if (mk.indexOf('mapBtn') === 0) {
          var mb = S[mk];
          if (mb && hit(x, y, mb)) {
            if (mb.locked) { toast('还没解锁'); return; }
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
    if (S.state === 'skin') {
      if (S.btnBack && hit(x, y, S.btnBack)) { S.state = 'bag'; return; }
      if (S.tabChar && hit(x, y, S.tabChar)) { S.skinTab = 'char'; return; }
      if (S.tabWeapon && hit(x, y, S.tabWeapon)) { S.skinTab = 'weapon'; return; }
      /* 人物造型 */
      for (var ck in S) {
        if (ck.indexOf('char') === 0 && ck !== 'charImg') {
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
        if (wsk.indexOf('skin') === 0 && wsk !== 'skinBox') {
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
      return;
    }
    if (S.state === 'pets') {
      if (S.btnBack && hit(x, y, S.btnBack)) { S.state = 'battle'; return; }
      if (S.btnFeed && hit(x, y, S.btnFeed)) { feedPet(); return; }
      return;
    }
    if (S.state === 'rank') {
      if (S.btnBack && hit(x, y, S.btnBack)) { S.state = 'battle'; return; }
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
    if (S.btnPull && hit(x, y, S.btnPull)) { S.pullRes = pull10(); S.state = 'pull'; return; }
    for (var i = 0; i < 3; i++) {
      var b2 = S['btnS' + i];
      if (b2 && hit(x, y, b2)) {
        S.skillQueued = S.skillQueued || [0, 0, 0];
        S.skillQueued[i] = true;
        return;
      }
    }
  }

  function equipItem(idx) {
    var s = S.save, it = s.bag[idx];
    if (!it) return;
    var before = power();
    s.equip[it.slot] = it;
    s.bag.splice(idx, 1);
    S.stats = stats();
    var after = power();
    S.anim.power = 1.4; S.anim.powerFrom = before;
    if (after > s.best) s.best = after;
    toast('换上 ' + it.qn + '　战力 +' + (after - before));
    G.persist();
  }
  function feedPet() {
    var s = S.save;
    if (!s.pet) { toast('还没有宠物'); return; }
    if (s.petLv >= D.PET_MAX_LV) { toast('已经满级了'); return; }
    var need = s.petLv * 50;
    if ((s.ef || 0) < 1) { toast('没有体力果'); return; }
    if (s.coins < need) { toast('灵果不够（需 ' + need + '）'); return; }
    s.coins -= need; s.ef--; s.petLv++;
    s.petMood = Math.min(D.MOOD_MAX, mood() + D.MOOD_FEED);
    s.petMoodAt = Date.now();
    S.stats = stats();
    toast('宠物升到 Lv' + s.petLv + '　心情 ' + moodTxt(mood()));
    G.persist();
  }

  /* ============ 抽卡结果 ============ */
  function drawPull() {
    G.round(0, 0, G.W, G.H, 0, 'rgba(12,12,14,.97)');
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
    if (S.banner && S.banner.t > 0) S.banner.t -= dt;
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
    if (S.state === 'bag') return drawBag();
    if (S.state === 'upgrade') return drawUpgrade();
    if (S.state === 'skin') return drawSkins();
    if (S.state === 'maps') return drawMaps();
    if (S.state === 'sign') return drawSign();
    if (S.state === 'pets') return drawPets();
    if (S.state === 'rank') return drawRank();
    if (S.state === 'pull') return drawPull();
    drawBattle();
  }

  /* ============ 启动 ============ */
  function start() {
    var s = load();
    S = {
      save: s, state: s.sex ? 'battle' : 'pick',
      hero: null, mobs: [], drops: [], nums: [], eff: [],
      wave: 0, waveT: 1.2, map: D.MAPS[s.map] || D.MAPS[0],
      stats: null, autoOn: false, autoManual: false, pickPrev: null,
      skillQueued: [0, 0, 0], toast: '', toastT: 0,
      anim: { power: 0, powerFrom: 0 }, pullRes: []
    };
    /* 体力果库存（简单起见放在 save 里） */
    if (s.ef == null) s.ef = 2;
    s.farmInvEf = s.ef;
    S.stats = stats();          /* 必须在 S 赋值之后：stats() 读 S.save */
    if (S.state === 'battle') newBattle();
    preloadArt();
    G.update = update;      /* ⚠️ 必须挂上去：boot.js 的主循环只认 G.update / G.draw */
    G.draw = draw;
    G.setHandlers({ down: onDown, up: null });
    G.loop();
  }

  window.GAME = { start: start, S: function () { return S; }, power: power, stats: stats };
})();

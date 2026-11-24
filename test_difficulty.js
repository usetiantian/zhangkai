/* 难度曲线实测：用真实关卡数据模拟"2座满级炉"打法能否通关
   模型：击杀吞吐 = 110 DPS（2×炉Lv4）；敌人按 0.8s 间隔进图；
        可用时间 = 波内敌数×0.8 + 走完全程时间(路径长/速度)；击杀需求 = 总HP/吞吐 */
const fs = require("fs");
const src = fs.readFileSync("game/src/levels.js", "utf8");
const levels = JSON.parse(src.slice(src.indexOf("["), src.lastIndexOf("]") + 1));
const routeLen = lv => {
  /* routes = 路径点序列（折线），真实长度 = 各段曼哈顿距离和 */
  let mx = 0;
  (lv.routes || []).forEach(rt => {
    let len = 0;
    for (let i = 1; i < rt.length; i++)
      len += Math.abs(rt[i][0] - rt[i-1][0]) + Math.abs(rt[i][1] - rt[i-1][1]);
    mx = Math.max(mx, len);
  });
  return mx;
};
function demand(lv, levelScale){
  let hp = 0, n = 0;
  lv.waves.forEach((w, wi) => {
    (w.list || [w]).forEach(e => {
      let h = (e.hp || 10) * 1.0 * Math.pow(1.0, wi) * (e.hpMul || 1);
      h *= 1.18 + 0.06 * wi;
      if (levelScale) h *= 1 + 0.045 * ((lv.no || 0));
      hp += h; n++;
    });
  });
  return { hp, n };
}
function strategy2kiln(lv, levelScale){
  const L = routeLen(lv);
  const d = demand(lv, levelScale);
  const dps = 110;                       /* 2 × 炉Lv4(22dmg×2.5倍率) */
  const sp = 1.1;                        /* 平均移速 格/秒 */
  const avail = d.n * 0.8 + L / sp;      /* 从开波到最后一只走完 */
  const need = d.hp / dps;
  return { L, n: d.n, hp: Math.round(d.hp), need: need.toFixed(1), avail: avail.toFixed(1),
           verdict: need < avail * 0.6 ? "轻松" : need < avail ? "勉强" : "打不过" };
}
console.log("关卡 | 路径长 | 敌数 | 有效总HP(旧) | 旧判定 | 有效总HP(新) | 新判定");
for (const no of [1, 10, 20, 40, 60, 80, 100]){
  const lv = levels[no - 1];
  lv.no = no;
  const oldS = strategy2kiln(lv, false);
  const newS = strategy2kiln(lv, true);
  console.log(String(no).padStart(3) + "  | " + String(oldS.L).padStart(4) + " | " +
    String(oldS.n).padStart(3) + " | " + String(oldS.hp).padStart(8) + " | " + oldS.verdict +
    "(" + oldS.need + "s/" + oldS.avail + "s) | " + String(newS.hp).padStart(8) + " | " +
    newS.verdict + "(" + newS.need + "s/" + newS.avail + "s)");
}

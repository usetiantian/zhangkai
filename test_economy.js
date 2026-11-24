/* 逐波经济时间线：每一关"到账的钱"能否及时买出"打掉当波敌人"的火力
   模型：波 w 需求 DPS = 当波有效HP / (敌数×0.8s + 路径长/速度)
        可买 DPS = 累计支出 / 8.5余烬每DPS； Frost减速折算需求×0.8 */
const fs = require("fs");
const src = fs.readFileSync("game/src/levels.js", "utf8");
const levels = JSON.parse(src.slice(src.indexOf("["), src.lastIndexOf("]") + 1));
const routeLen = lv => {
  let mx = 0;
  (lv.routes || []).forEach(rt => {
    let len = 0;
    for (let i = 1; i < rt.length; i++) len += Math.abs(rt[i][0]-rt[i-1][0]) + Math.abs(rt[i][1]-rt[i-1][1]);
    mx = Math.max(mx, len);
  });
  return mx;
};
function sim(no){
  const lv = levels[no-1]; lv.no = no;
  const L = routeLen(lv), sp = 1.1;
  const lvMul = 1 + 0.045*(no-1), incMul = 1 + 0.025*(no-1);
  let purse = 260 + (no-1)*12, earned = purse;
  let worst = { ratio: 99, wave: 0 };
  let cumNeed = 0, cumSpendable = 0;
  lv.waves.forEach((w, wi) => {
    const list = w.list || [w];
    let hp = 0, n = 0, rew = 0;
    list.forEach(e => {
      hp += (e.hp||10) * (1.18+0.06*wi) * lvMul * (e.hpMul||1);
      n++; rew += (e.reward||5) * incMul;
    });
    const avail = n*0.8 + L/sp;
    const needDps = (hp/avail) / 0.8;           /* Frost减速折算 */
    cumNeed = Math.max(cumNeed, needDps);       /* 火力只增不减（塔是永久的） */
    cumSpendable = earned / 8.5;
    const ratio = cumNeed / Math.max(1, cumSpendable);
    if (ratio < worst.ratio) worst = { ratio, wave: wi+1 };  /* 最宽裕=资金覆盖最好 */
    earned += rew + Math.round((40+18*wi)*incMul);
  });
  /* 判定：整关结束时的资金火力 vs 全程最高需求 */
  const finalDps = earned / 8.5;
  const ok = finalDps >= cumNeed;
  return { no, purse0: 260+(no-1)*12, income: Math.round(earned),
           needDps: Math.round(cumNeed), affordDps: Math.round(finalDps), ok,
           headroom: Math.round((finalDps/cumNeed - 1)*100) };
}
console.log("关卡 | 开局 | 整关收入 | 需求火力DPS | 钱能买DPS | 余量 | 可完成");
for (const no of [1, 5, 10, 20, 40, 60, 80, 100]){
  const r = sim(no);
  console.log(String(r.no).padStart(3) + "  | " + String(r.purse0).padStart(4) + " | " +
    String(r.income).padStart(7) + " | " + String(r.needDps).padStart(8) + " | " +
    String(r.affordDps).padStart(8) + " | " + String(r.headroom).padStart(4) + "% | " + (r.ok ? "✓" : "✗"));
}

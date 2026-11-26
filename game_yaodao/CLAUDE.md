# 《妖刀录》· 微信小游戏（独立工程）

> 本目录是**独立工程**，与 `../game/`（《果子的乐园》）**完全隔离**。
> 两个游戏各自发版、各自升级版本，不共享任何代码/工具/存档。

---

## 一、目录结构

```
game_yaodao/
├── CLAUDE.md          ← 本文件
├── index.html         ← H5 单页入口（浏览器调试用）
├── build.py           ← 打包：H5 单文件 + 微信小游戏包
├── src/               ← 源码（唯一真源）
│   ├── data.js        ← 数值表（品质/部位/武器/词条/怪物/宠物/地图/皮肤）
│   ├── boot.js        ← 微信运行时垫片 + 画布 + 输入 + 存档 + 主循环
│   ├── game.js        ← 战斗 + 各面板 UI
│   └── main.js        ← 启动
├── wx/                ← 打包产物（微信开发者工具直接打开这个目录）
│   ├── game.js        ← 四个 src 拼接产物（勿手改，改 src 后重新 build）
│   ├── game.json
│   └── project.config.json
├── tools/             ← 本项目专用工具（不放别的游戏的）
│   ├── yd_wx.js       ← 微信模拟器端到端验证
│   ├── yd_diag.js     ← 启动诊断（抓控制台/异常）
│   └── yd_two.js      ← 双项目体检
└── dist/index.html    ← H5 打包产物
```

## 二、铁律

1. **改 `src/`，然后 `python build.py --wx`**，别直接改 `wx/game.js`。
2. **不往 `../game/`（果子乐园）放任何东西**。共享脚本要复制一份到本项目 `tools/`。
3. **存档 key 独立**：`yaodao_save_v1`（果子乐园用 `__guozi`），互不干扰。
4. **appid 独立上架**：本项目 `wxdb991cea3b78ea95`（与果子乐园同主体，但发布时各自是独立小游戏）。

## 三、微信运行时兼容性（踩过的坑）

| 现象 | 根因 | 正确写法 |
|------|------|----------|
| `document` 存在但没有 DOM 布局 | 小游戏是 canvas 环境，不是网页 | 用 `wx.createCanvas()` 画，别用 DOM |
| `localStorage` 是 undefined | 小游戏没有 | 用 `wx.setStorageSync/getStorageSync` |
| `window` 可用 | 开发者工具里 `window === GameGlobal` | 用 `window`/`GameGlobal` 都行 |
| `document.readyState === 'loading'` | 模拟器里是 `complete` | 但真机可能是 loading → 启动别等 DOMContentLoaded |

**验证方式**：`node tools/yd_wx.js` —— 自动清档 → 点「普通编译」→ 选性别 → 抽卡 → 背包 → 改形象，逐项截图。

## 四、CDP 通道

```bash
# 开发者工具必须带调试端口启动（不带就没有 CDP）
"C:/Program Files (x86)/Tencent/微信web开发者工具/微信开发者工具.exe" ^
  --remote-debugging-port=9333 "C:/Users/87999/claude-workspace/game_yaodao/wx"
```

- 多个工程同时开着时，所有 gamePage 长得一样 → **按 `typeof GAME` 认工程**，别抓错。
- contextId 是 130+ 的，不能只扫 1..40。
- 找不到 context 时用 `Runtime.executionContextCreated` 事件收集。

## 五、美术管线（ComfyUI 8188 + Flux.1-dev）

```bash
python tools/gen_art.py hero       # 出主角定妆图（男/女，空手）
python tools/gen_art.py weapon     # 出 10 把武器
python tools/gen_art.py staff      # 杖（竖立模板）
python tools/gen_art.py fist       # 拳套（只要拳头）
python tools/prep_assets.py        # 抠背景→裁剪→缩放 → assets/run + assets/weapon
python build.py --wx               # 打包并报告主包体积
```

| 目录 | 内容 | 入库 |
|------|------|------|
| `assets/raw/<批次>/` | ComfyUI 出的 768px 原图 | ❌ gitignore |
| `assets/run/` | 主角 256×256（**不裁剪**，锚点比例才对） | ✅ |
| `assets/weapon/` | 武器 128px 长边（裁到内容） | ✅ |

⚠️ **原图和成品目录必须分开** —— 之前撞名，处理会把原图覆盖，反复处理还会越处理越糊。

⚠️ **武器贴图左右翻转**（`prep_assets.py` 的 `FLIP`）：出图时刀身朝右上，角色右手在画面左侧，
不翻转刀会横跨角色脸。翻转后握把点从 `x:0.13` 变成 `x:0.87`。

## 六、当前进度（2026-11-26）

- ✅ P0 原型：选性别 → 战斗 → 10 秒无操作自动战斗（带✕取消）→ 背包 → 抽卡 → 宠物 → 排行
- ✅ 微信模拟器端到端验证通过（真实触摸事件）
- ✅ 性别选择首次进入可达（`newSave()` 里 `sex` 留空）+ 背包内「改形象」可重选且保留进度
- ✅ 主角贴图（男/女 Q版立绘）+ 10 把武器贴图，已在微信运行时验证渲染正常
- ✅ 武器外观系统 P1：分层贴图 + 握把锚点跟随 + 程序化刀光弧（主包 0.29MB / 4MB 限制）
- ⬜ 怪物美术（现在还是圆球）、地图底图、装备图标
- ⬜ 武器在背包/抽卡界面的图标展示
- ⬜ 数值模拟校准掉落率

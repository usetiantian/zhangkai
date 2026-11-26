# -*- coding: utf-8 -*-
"""《妖刀录》美术出图 —— 走本机 ComfyUI(8188) 的 Flux.1-dev 文生图工作流。

用法:
  python tools/gen_art.py 批次名            # 出完整一批
  python tools/gen_art.py --one 提示词 尺寸 # 临时出一张

产物: assets/<批次名>/<名字>.png
"""
import io
import json
import os
import shutil
import sys
import time
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)                    # game_yaodao/
WS_TOOLS = os.path.join(os.path.dirname(ROOT), 'tools')
sys.path.insert(0, WS_TOOLS)
import wf2api  # noqa: E402

COMFY = os.environ.get('COMFY_API', 'http://127.0.0.1:8188')
WF = r'D:\ComfyUI_windows_portable\ComfyUI\user\default\workflows\FLUX文生图.json'

# ---------------------------------------------------------------- 风格锚点
# 所有图共用这一段，否则角色/武器/怪物不是一个世界的
STYLE = ('chibi mobile game asset, Chinese xianxia fantasy style, '
         'Q-version proportions with large head and small body, '
         'cel-shaded thick painting, bold clean dark outlines, high saturation, '
         'vibrant harmonious colors, soft rim light, crisp details, '
         'single subject centered, plain light gray background, '
         'high detail, best quality')

NEG = ('low quality, blurry, noisy, jpeg artifacts, compression distortion, '
       'extra fingers, mutated hands, asymmetrical eyes, disfigured, '
       'multiple characters, crowd, text, watermark, logo, signature, '
       'realistic, photorealistic, 3d render, cgi, western cartoon, chibi 3d, '
       'busy background, scenery, landscape, ugly, deformed')

HERO_M = ('masterpiece, ' + STYLE + ', '
          'a brave young Chinese xianxia swordsman boy hero, '
          'short determined expression, '
          'dark teal and gold trim traditional hanfu battle robe, '
          'black hair tied in a high ponytail with a golden hairpin, '
          'red sash, jade pendant at the waist, '
          'brown leather boots, '
          'both hands empty, unarmed, no weapon in hands, '
          'standing idle pose, full body, both arms visible, '
          '3/4 top-down view')

HERO_F = ('masterpiece, ' + STYLE + ', '
          'a brave young Chinese xianxia heroine girl, '
          'short determined expression, '
          'white and pale blue hanfu dress with silver shoulder armor and '
          'red ribbon, '
          'long black hair with a red ribbon, '
          'jade pendant at the waist, '
          'standing idle pose, full body, both arms visible, '
          '3/4 top-down view')

# 武器：一把一件，斜 45 度，纯白背景，方便抠进手里
WEAPONS = [
    ('ws_blade_1', '青锋剑', 'a straight single edge chinese jian longsword, '
                            'jade green glowing blade, silver guard, dark wooden sheath'),
    ('ws_blade_2', '赤霄刀', 'a heavy chinese broad saber dao, '
                            'crimson red glowing blade with flame runes, black iron guard'),
    ('ws_sword_1', '流云剑', 'a slender elegant chinese straight sword, '
                             'cloud white and gold blade, ornate gold guard'),
    ('ws_sword_2', '紫电枪', 'a long chinese spear with a lightning shaped '
                             'purple energy blade tip, silver shaft'),
    ('ws_staff_1', '玄木杖', 'a gnarled dark wooden wizard staff standing '
                             'vertical with a floating cyan spirit orb on top '
                             'and carved runes'),
    ('ws_staff_2', '烈阳棍', 'a heavy iron staff standing vertical with a '
                             'burning golden fire orb on top'),
    ('ws_fist_1', '金刚拳套', 'a single heavy golden gauntlet fist with blue energy glow'),
    ('ws_fist_2', '血影爪', 'a single dark crimson claw blade with black smoke'),
    ('ws_dagger_1', '月影匕', 'a small curved silver chinese dagger with a '
                              'moon shaped crescent blade'),
    ('ws_dagger_2', '星辰镰', 'a curved chinese sickle with a violet starfield '
                              'blade and golden handle'),
]

WEAPON_TMPL = ('masterpiece, ' + STYLE + ', '
               'a game inventory weapon icon, ' + '{desc}, '
               'angled 45 degrees diagonally, '
               'whole weapon fully visible, centered, '
               'isolated on plain white background, '
               'crisp edges, no character, no hand')

# 杖要竖着出（斜 45 度的模板会让杖身横跨角色身体）
STAFF_TMPL = ('masterpiece, ' + STYLE + ', '
               'a game inventory weapon icon, ' + '{desc}, '
               'standing upright vertically, '
               'whole weapon fully visible, centered, '
               'isolated on plain white background, '
               'crisp edges, no character, no hand')

# 拳套：只要拳头本体，不要手臂/握把 —— 游戏里直接套在角色手上
FIST_TMPL = ('masterpiece, ' + STYLE + ', '
             'a game inventory item, ' + '{desc}, '
             'just the closed fist only, no arm, no handle, no sleeve, '
             'whole item fully visible, centered, '
             'isolated on plain white background, '
             'crisp edges, no character, no hand')

# 怪物：俯视角 3/4 视角，脚底对齐地面点
MOB_TMPL = ('masterpiece, ' + STYLE + ', '
            'a chibi monster game enemy, ' + '{desc}, '
            'cute but slightly menacing, standing on the ground, '
            'full body, whole creature fully visible, centered, '
            'top-down three-quarter view, '
            'plain light gray background, '
            'no character, no human, no weapon')

# 地图底：俯视地面纹理
MAP_TMPL = ('masterpiece, top-down game ground texture, ' + '{desc}, '
            'perfectly seamless tileable repeating texture, '
            'no path, no road, no borders, no edges, no vignette, '
            'no characters, no objects, no props, no buildings, '
            'flat even lighting, orthographic top view, '
            'high detail, best quality')

MONS_ART = [
    ('m1', 'a chubby brown mountain rat creature with big front teeth, '
           'round ears and a short tail'),
    ('m2', 'a gray blue wolf cub with sharp ears and glowing yellow eyes'),
    ('m3', 'a green vine plant monster with leafy tendrils and a flower bud head'),
    ('e1', 'a big brown bear with an iron gray armored back plate and thick arms'),
    ('b1', 'a menacing dark crimson demon king with black horns, '
           'glowing red eyes, long black cape and curved blades'),
]

# ⚠️ 必须是**均匀可平铺**的地面。之前出的是"一条路"的场景，平铺会出现重复的路。
MAPS_ART = [
    ('map1', 'uniform flat chinese village outskirts ground, packed dry dirt with '
             'small gray pebbles, sparse short dry grass tufts, even coverage everywhere'),
    ('map2', 'uniform flat ancient graveyard ground, dry cracked pale earth, '
             'scattered small bone fragments and dead leaves, even coverage everywhere'),
    ('map3', 'uniform flat bandit stronghold ground, dark packed soil with ash and '
             'small wood chips, even coverage everywhere'),
]

# 人物皮肤：4 套（男素衣/男青竹/女素衣/女绛紫），要跟定妆图同风格
SKIN_ART = [
    ('cs1', 'a brave young Chinese xianxia swordsman boy, '
            'plain simple gray-blue hanfu robe with minimal trim, '
            'short tidy black hair, calm expression'),
    ('cs2', 'a brave young Chinese xianxia swordsman boy, '
            'green bamboo themed hanfu robe with bamboo leaf patterns, '
            'black hair tied in a topknot, confident expression'),
    ('cs3', 'a brave young Chinese xianxia heroine girl, '
            'simple plain white and lavender hanfu dress, '
            'long black hair, calm expression'),
    ('cs4', 'a brave young Chinese xianxia heroine girl, '
            'deep crimson and dark purple hanfu dress with gold embroidery, '
            'long black hair with a purple ribbon, fierce expression'),
]

SKIN_TMPL = ('masterpiece, ' + STYLE + ', '
             'a game character costume design, ' + '{desc}, '
             'standing idle pose, full body, both hands empty, unarmed, '
             'whole character fully visible, centered, '
             'top-down three-quarter view, '
             'plain light gray background, '
             'crisp edges, no weapon, no text')

BATCHES = {
    'skin': [(n + '.png', SKIN_TMPL.format(desc=d), 768, 768) for n, d in SKIN_ART],
    'mob': [(n + '.png', MOB_TMPL.format(desc=d), 768, 768) for n, d in MONS_ART],
    'map': [(n + '.png', MAP_TMPL.format(desc=d), 1024, 1024) for n, d in MAPS_ART],
    'hero': [(n + '.png', p, 768, 768) for n, p in
             (('hero_m', HERO_M), ('hero_f', HERO_F))],
    'weapon': [(n + '.png', WEAPON_TMPL.format(desc=d), 768, 768)
               for n, _, d in WEAPONS],
    # 只重出姿态不对的那几把（杖要竖、拳套要单只）
    'weapon2': [(n + '.png', WEAPON_TMPL.format(desc=d), 768, 768)
                for n, _, d in WEAPONS
                if n in ('ws_staff_1', 'ws_staff_2', 'ws_fist_1', 'ws_fist_2')],
    # 杖单独出：竖立模板
    'staff': [(n + '.png', STAFF_TMPL.format(desc=d), 768, 768)
              for n, _, d in WEAPONS
              if n in ('ws_staff_1', 'ws_staff_2')],
    # 拳套单独出：只要拳头，不要手臂/握把（游戏里直接套在手上）
    'fist': [(n + '.png', FIST_TMPL.format(desc=d), 768, 768)
             for n, _, d in WEAPONS
             if n in ('ws_fist_1', 'ws_fist_2')],
}


def post(url, obj):
    req = urllib.request.Request(url, data=json.dumps(obj).encode('utf-8'),
                                 headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.load(r)


def get(url):
    with urllib.request.urlopen(url, timeout=60) as r:
        return json.load(r)


def build_prompt(oi, text, w, h, prefix):
    wf = json.load(io.open(WF, encoding='utf-8'))
    ov = {
        '13': {'text': text},
        '14': {'text': NEG},
        '16': {'width': w, 'height': h},
        '18': {'filename_prefix': prefix},
    }
    p, notes = wf2api.convert(wf, oi, ov)
    for n in notes:
        print('   ~', n)
    return p


def run(oi, name, text, w, h, outdir):
    prefix = 'yd/' + os.path.splitext(name)[0]
    p = build_prompt(oi, text, w, h, prefix)
    res = post(COMFY + '/prompt', {'prompt': p, 'client_id': 'cc-yaodao'})
    if 'error' in res:
        print('  ! 排队失败:', res['error'])
        return False
    pid = res['prompt_id']
    print('   排队', pid)
    t0 = time.time()
    while time.time() - t0 < 300:
        time.sleep(2)
        hist = get(COMFY + '/history/' + pid)
        if pid in hist:
            outs = hist[pid].get('outputs', {})
            for nid, o in outs.items():
                for im in o.get('images', []):
                    fn = im.get('filename')
                    sub = im.get('subfolder', '')
                    url = '%s/view?filename=%s&subfolder=%s&type=output' % (
                        COMFY, urllib.parse.quote(fn), urllib.parse.quote(sub))
                    data = urllib.request.urlopen(url, timeout=120).read()
                    dest = os.path.join(outdir, name)
                    os.makedirs(os.path.dirname(dest), exist_ok=True)
                    io.open(dest, 'wb').write(data)
                    print('   ✓', dest, '%.1fKB' % (len(data) / 1024))
            return True
    print('   ! 超时')
    return False


def main():
    args = sys.argv[1:]
    oi = get(COMFY + '/object_info')
    if args and args[0] == '--one':
        text = args[1]
        w = int(args[2]) if len(args) > 2 else 768
        h = int(args[3]) if len(args) > 3 else 768
        out = os.path.join(ROOT, 'assets', 'raw', 'tmp')
        os.makedirs(out, exist_ok=True)
        run(oi, 'one.png', text, w, h, out)
        return 0
    batch = args[0] if args else 'hero'
    if batch not in BATCHES:
        print('未知批次', batch, '| 可用:', list(BATCHES))
        return 1
    # 原图单独放 raw/ —— 之前和成品目录撞名，处理会把原图覆盖掉
    outdir = os.path.join(ROOT, 'assets', 'raw', batch)
    os.makedirs(outdir, exist_ok=True)
    items = BATCHES[batch]
    print('批次 %s：%d 张' % (batch, len(items)))
    ok = 0
    for name, text, w, h in items:
        print('->', name)
        if run(oi, name, text, w, h, outdir):
            ok += 1
    print('完成 %d/%d' % (ok, len(items)))
    return 0


if __name__ == '__main__':
    import urllib.parse
    sys.exit(main())

# -*- coding: utf-8 -*-
"""《妖刀录》美术资源后处理：抠背景 → 裁到内容 → 缩放到游戏尺寸。

ComfyUI 出的图是 768x768 白底，游戏里要的是透明小图。
背景抠法用「从四边泛洪」而不是简单阈值 —— 武器本身有银白/高光，
阈值会把刀身一起抠掉。

用法:
  python tools/prep_assets.py          # 处理全部
  python tools/prep_assets.py hero     # 只处理某个批次
"""
import io
import os
import sys

from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
ASSETS = os.path.join(ROOT, 'assets')

# 批次 -> (目标目录, 目标边长, 是否裁到内容)
#
# ⚠️ 主角**不能裁**：武器挂点/手部锚点是按原图的比例坐标算的
#    （原图 768x768，角色几乎占满高度），一裁比例就全错。
#    武器可以裁 —— 它的握把点是单独配的。
# 批次 -> (目标目录, 目标边长, 是否裁到内容, 存成 jpg 还是 png)
# 地面纹理没有透明通道 → 用 JPEG，体积小 10 倍（PNG 要 500KB+/张，JPEG 只要 50KB）
TARGETS = {
    'hero': ('run', 256, False, 'png'),
    'weapon': ('weapon', 128, True, 'png'),
    'mob': ('mob', 192, True, 'png'),
    'skin': ('run', 256, False, 'png'),
    'map': ('map', 512, True, 'jpg'),
}

# 武器贴图左右翻转。
# 出图时刀身是朝右上斜的，角色右手在画面左侧 → 刀会横跨角色脸。
# 翻转后刀尖朝左外侧，才是「握在手里、刃朝外」的正常站姿。
FLIP = {'weapon': True, 'hero': False, 'mob': False, 'map': False}


def _border_bg(px, w, h):
    """取四边像素的中位色当背景色。
    ComfyUI 出的背景不是纯白，是带渐变的浅灰 —— 用绝对阈值抠会剩一圈方块。"""
    samples = []
    for x in range(0, w, 3):
        samples.append(px[x, 0][:3]); samples.append(px[x, h - 1][:3])
    for y in range(0, h, 3):
        samples.append(px[0, y][:3]); samples.append(px[w - 1, y][:3])
    ch = []
    for c in range(3):
        vals = sorted(s[c] for s in samples)
        ch.append(vals[len(vals) // 2])
    return tuple(ch)


def bg_to_alpha(im, tol=58):
    """从四边泛洪，把**和背景色接近**的连通像素抠成透明。

    用「颜色接近背景」而不是「绝对亮度高」：
    - 背景带渐变时绝对阈值会剩一圈方块
    - 只抠**连通到边缘**的像素 → 角色身上的白色/银色部分不会被误伤
    """
    im = im.convert('RGBA')
    w, h = im.size
    px = im.load()
    bgc = _border_bg(px, w, h)
    seen = bytearray(w * h)

    def is_bg(x, y):
        r, g, b, _ = px[x, y]
        return (r - bgc[0]) ** 2 + (g - bgc[1]) ** 2 + (b - bgc[2]) ** 2 < tol * tol

    stack = []
    for x in range(w):
        stack.append((x, 0)); stack.append((x, h - 1))
    for y in range(h):
        stack.append((0, y)); stack.append((w - 1, y))
    while stack:
        x, y = stack.pop()
        if x < 0 or y < 0 or x >= w or y >= h:
            continue
        i = y * w + x
        if seen[i] or not is_bg(x, y):
            continue
        seen[i] = 1
        stack.append((x + 1, y)); stack.append((x - 1, y))
        stack.append((x, y + 1)); stack.append((x, y - 1))

    out = im.copy()
    op = out.load()
    for y in range(h):
        for x in range(w):
            if seen[y * w + x]:
                op[x, y] = (255, 255, 255, 0)
    return out


def trim(im):
    bbox = im.getbbox()
    return im.crop(bbox) if bbox else im


def fit(im, size):
    """等比缩放到 size 的最长边，保持透明边。"""
    w, h = im.size
    if w == 0 or h == 0:
        return im
    s = size / float(max(w, h))
    nw, nh = max(1, int(round(w * s))), max(1, int(round(h * s)))
    return im.resize((nw, nh), Image.LANCZOS)


def _flat_region(im, size=180):
    """在图里找一块**颜色变化最小**的区域（纯地面，没有路/树/建筑）。"""
    w, h = im.size
    best = None
    best_var = 1e18
    for y in range(0, max(1, h - size), 40):
        for x in range(0, max(1, w - size), 40):
            c = im.crop((x, y, x + size, y + size)).resize((16, 16), Image.BILINEAR)
            px = list(c.getdata())
            n = len(px)
            mv = sum(sum(p[:3]) for p in px) / float(n)
            var = sum((sum(p[:3]) / 3.0 - mv) ** 2 for p in px) / n
            if var < best_var:
                best_var = var
                best = (x, y)
    if best is None:
        best = (0, 0)
    print('    最平坦区域 @%s 方差 %.1f' % (str(best), best_var))
    return im.crop((best[0], best[1], best[0] + size, best[1] + size))


def seamless_ground(im, quarter_px=180):
    """造一张**无缝**的地面贴图。

    Flux 出的"地图"其实是带路带建筑的场景，平铺必然露出十字缝。
    办法：① 取左上角一块**没有路的纯地面** ② 四向镜像拼成 2x2。
    镜像后左右边、上下边天然对齐 → 严丝合缝，重复也看不出来。
    """
    w, h = im.size
    q = _flat_region(im, quarter_px)
    q = q.resize((256, 256), Image.LANCZOS)
    tile = Image.new('RGBA', (512, 512))
    tile.paste(q, (0, 0))
    tile.paste(q.transpose(Image.FLIP_LEFT_RIGHT), (256, 0))
    tile.paste(q.transpose(Image.FLIP_TOP_BOTTOM), (0, 256))
    tile.paste(q.transpose(Image.ROTATE_180), (256, 256))
    return tile


def process(batch):
    src_dir = os.path.join(ASSETS, 'raw', batch)
    if not os.path.isdir(src_dir):
        print('跳过（没有目录）', src_dir)
        return 0
    outdir, size, do_trim, fmt = TARGETS[batch]
    dst_dir = os.path.join(ASSETS, outdir)
    if not os.path.isdir(dst_dir):
        os.makedirs(dst_dir)
    n = 0
    for fn in sorted(os.listdir(src_dir)):
        if not fn.lower().endswith(('.png', '.jpg', '.jpeg')):
            continue
        src = os.path.join(src_dir, fn)
        im = Image.open(src)
        im = bg_to_alpha(im)
        if FLIP.get(batch):
            im = im.transpose(Image.FLIP_LEFT_RIGHT)
        if batch == 'map':
            im = seamless_ground(im)
        elif do_trim:
            im = trim(im)
            im = fit(im, size)
        else:
            # 不裁：等比缩到目标高度，保持画布比例（锚点比例才对得上）
            w, h = im.size
            nh = size
            nw = max(1, int(round(w * size / float(h))))
            im = im.resize((nw, nh), Image.LANCZOS)
        name = os.path.splitext(fn)[0] + '.' + fmt
        dst = os.path.join(dst_dir, name)
        if fmt == 'jpg':
            im.convert('RGB').save(dst, quality=84, optimize=True)
        else:
            im.save(dst, optimize=True)
        kb = os.path.getsize(dst) / 1024.0
        print('  %-22s %s %dx%d  %.1fKB' % (name, batch, im.size[0], im.size[1], kb))
        n += 1
    print('%s: 处理 %d 张 -> %s' % (batch, n, dst_dir))
    return n


if __name__ == '__main__':
    batches = sys.argv[1:] or list(TARGETS)
    total = 0
    for b in batches:
        total += process(b)
    print('合计 %d 张' % total)

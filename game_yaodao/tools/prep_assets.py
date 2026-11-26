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
TARGETS = {
    'hero': ('run', 256, False),
    'weapon': ('weapon', 128, True),
}

# 武器贴图左右翻转。
# 出图时刀身是朝右上斜的，角色右手在画面左侧 → 刀会横跨角色脸。
# 翻转后刀尖朝左外侧，才是「握在手里、刃朝外」的正常站姿。
FLIP = {'weapon': True, 'hero': False}


def bg_to_alpha(im, tol=26):
    """从四边泛洪，把连通的浅色背景抠成透明。"""
    im = im.convert('RGBA')
    w, h = im.size
    px = im.load()
    seen = bytearray(w * h)

    def is_bg(x, y):
        r, g, b, _ = px[x, y]
        return min(r, g, b) > 236 and (max(r, g, b) - min(r, g, b)) < 18

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


def process(batch):
    src_dir = os.path.join(ASSETS, 'raw', batch)
    if not os.path.isdir(src_dir):
        print('跳过（没有目录）', src_dir)
        return 0
    outdir, size, do_trim = TARGETS[batch]
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
        if do_trim:
            im = trim(im)
            im = fit(im, size)
        else:
            # 不裁：等比缩到目标高度，保持画布比例（锚点比例才对得上）
            w, h = im.size
            nh = size
            nw = max(1, int(round(w * size / float(h))))
            im = im.resize((nw, nh), Image.LANCZOS)
        name = os.path.splitext(fn)[0] + '.png'
        dst = os.path.join(dst_dir, name)
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

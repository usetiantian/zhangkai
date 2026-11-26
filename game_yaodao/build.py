# -*- coding: utf-8 -*-
"""《妖刀录》打包：H5 单文件 + 微信小游戏包。"""
import io, json, os, shutil, sys

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, 'src')
DIST = os.path.join(HERE, 'dist')
WX = os.path.join(HERE, 'wx')
APP = '妖刀录'
SCRIPTS = ['data.js', 'boot.js', 'game.js', 'main.js']
NL = '\n'


def rd(p):
    return io.open(p, encoding='utf-8').read()


def build_h5():
    if not os.path.isdir(DIST):
        os.makedirs(DIST)
    blocks = []
    for n in SCRIPTS:
        blocks.append('<script>' + NL + rd(os.path.join(SRC, n)) + '</script>')
    html = rd(os.path.join(HERE, 'index.html'))
    # 把 <script src="..."> 换成内联
    for n in SCRIPTS:
        html = html.replace('<script src="src/%s"></script>' % n,
                            '<script>' + NL + rd(os.path.join(SRC, n)) + '</script>')
    out = os.path.join(DIST, 'index.html')
    io.open(out, 'w', encoding='utf-8', newline='\n').write(html)
    print('H5   ->', out, os.path.getsize(out) // 1024, 'KB')


def build_wx():
    if not os.path.isdir(WX):
        os.makedirs(WX)
    alljs = NL.join(rd(os.path.join(SRC, n)) for n in SCRIPTS)
    io.open(os.path.join(WX, 'game.js'), 'w', encoding='utf-8', newline='\n').write(alljs)
    io.open(os.path.join(WX, 'game.json'), 'w', encoding='utf-8', newline='\n').write(json.dumps({
        "deviceOrientation": "portrait",
        "showStatusBar": False,
        "networkTimeout": {"request": 10000},
        "subpackages": []
    }, ensure_ascii=False, indent=1))
    io.open(os.path.join(WX, 'project.config.json'), 'w', encoding='utf-8', newline='\n').write(json.dumps({
        "description": "妖刀录 - 休闲Q版仙侠单机",
        "appid": "wxdb991cea3b78ea95",
        "projectname": "yaodao-lu",
        "setting": {"urlCheck": False, "es6": True, "minified": False},
        "compileType": "game",
        "libVersion": "3.7.0",
        "packOptions": {"ignore": [{"type": "file", "value": "project.config.json"}]}
    }, ensure_ascii=False, indent=1))
    print('微信包 ->', os.path.join(WX, 'game.js'), os.path.getsize(os.path.join(WX, 'game.js')) // 1024, 'KB')


if __name__ == '__main__':
    build_h5()
    if '--wx' in sys.argv:
        build_wx()

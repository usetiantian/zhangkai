# -*- coding: utf-8 -*-
"""《妖刀录》音效生成 —— 程序化合成，不引任何外部素材。

用 numpy 合成 22050Hz / 16bit / 单声道 WAV。
微信小游戏主包小，音效必须小：一个 0.3 秒的音效 ≈ 13KB。

用法:
  python tools/gen_sfx.py          # 生成到 assets/sfx/
"""
import io
import math
import os
import wave

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OUT = os.path.join(ROOT, 'assets', 'sfx')
SR = 22050


def env(n, attack=0.005, decay=0.15, sustain=0.0, release=0.05):
    """简单 ADSR 包络，避免爆音。"""
    a = max(1, int(attack * SR))
    d = max(1, int(decay * SR))
    r = max(1, int(release * SR))
    s = max(0, n - a - d - r)
    e = np.concatenate([
        np.linspace(0, 1, a),
        np.linspace(1, sustain if sustain else 0.0, d),
        np.full(s, sustain if sustain else 0.0),
        np.linspace(sustain if sustain else 0.0, 0, r),
    ])
    return e[:n]


def tone(freq, dur, kind='sine', vol=1.0, a=0.004, d=None, r=0.04):
    n = int(dur * SR)
    t = np.arange(n) / SR
    if kind == 'sine':
        w = np.sin(2 * np.pi * freq * t)
    elif kind == 'square':
        w = np.sign(np.sin(2 * np.pi * freq * t))
    elif kind == 'saw':
        w = 2 * ((freq * t) % 1) - 1
    elif kind == 'tri':
        x = (freq * t) % 1
        w = 4 * abs(x - 0.5) - 1
    else:
        w = np.zeros(n)
    return w * env(n, a, d if d is not None else dur * 0.9, 0, r) * vol


def noise(dur, vol=1.0, lp=0.3, a=0.001, d=None, r=0.05):
    n = int(dur * SR)
    w = np.random.RandomState(7).randn(n)
    # 一阶低通，把白噪声变闷
    k = max(1, int(lp * SR / 40))
    w = np.convolve(w, np.ones(k) / k, mode='same')
    return w * env(n, a, d if d is not None else dur * 0.9, 0, r) * vol


def mix(*parts):
    n = max(len(p) for p in parts)
    out = np.zeros(n)
    for p in parts:
        out[:len(p)] += p
    return out


def pad(dur, x):
    """把音频补到指定长度。"""
    n = int(dur * SR)
    out = np.zeros(n)
    out[:min(n, len(x))] = x[:min(n, len(x))]
    return out


def seq(notes, dur_each=0.11, kind='sine', vol=0.6):
    """一串音符（琶音）。"""
    parts = []
    for i, f in enumerate(notes):
        p = tone(f, dur_each, kind, vol)
        p = np.roll(p, int(i * dur_each * SR * 0.85))
        parts.append(p)
    return mix(*parts)


def save(name, data):
    data = np.clip(data, -1, 1)
    # 末尾淡出，避免咔哒声
    fade = min(400, len(data))
    data[-fade:] *= np.linspace(1, 0, fade)
    path = os.path.join(OUT, name + '.wav')
    with wave.open(path, 'wb') as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes((data * 32000).astype(np.int16).tobytes())
    print('  %-10s %5.1f KB' % (name + '.wav', os.path.getsize(path) / 1024.0))


def build():
    if not os.path.isdir(OUT):
        os.makedirs(OUT)

    # UI 点击：短促的"嗒"
    save('click', mix(tone(880, 0.05, 'sine', 0.5, 0.002, 0.04, 0.01),
                      tone(1320, 0.04, 'sine', 0.25, 0.002, 0.03, 0.01)))

    # 普通攻击命中：低沉的撞击 + 一点挥砍噪声
    save('hit', mix(tone(140, 0.12, 'sine', 0.6, 0.002, 0.09, 0.02),
                    tone(85, 0.10, 'tri', 0.45, 0.002, 0.08, 0.02),
                    noise(0.07, 0.22, 0.4, 0.001, 0.06, 0.015)))

    # 暴击：撞击 + 金属高鸣
    save('crit', mix(tone(150, 0.22, 'sine', 0.7, 0.002, 0.18, 0.04),
                     tone(1200, 0.22, 'sine', 0.22, 0.002, 0.19, 0.03),
                     tone(1800, 0.16, 'sine', 0.12, 0.002, 0.13, 0.03),
                     noise(0.08, 0.25, 0.8, 0.001, 0.07, 0.02)))

    # 掉装备：两声上行
    save('drop', mix(pad(0.24, np.roll(tone(660, 0.12, 'sine', 0.5), 0)),
                     np.roll(tone(990, 0.16, 'sine', 0.45), int(0.09 * SR))))

    # 出史诗以上：四音琶音 + 闪光
    save('rare', mix(seq([784, 988, 1175, 1568], 0.1, 'sine', 0.5),
                     np.roll(tone(2350, 0.3, 'sine', 0.16), int(0.1 * SR))))

    # 十连抽：呼的一声 + 铃
    save('pull', mix(noise(0.35, 0.3, 0.25, 0.06, 0.28, 0.05),
                     np.roll(seq([523, 784, 1047], 0.12, 'sine', 0.45), int(0.3 * SR))))

    # 强化成功：上行琶音
    save('upgrade', seq([523, 659, 784, 1047, 1319], 0.085, 'tri', 0.45))

    # 妖王登场：低频轰鸣 + 号角
    save('boss', mix(tone(65, 0.9, 'sine', 0.55, 0.08, 0.7, 0.15),
                     tone(98, 0.9, 'tri', 0.35, 0.1, 0.7, 0.15),
                     tone(131, 0.6, 'sine', 0.22, 0.06, 0.45, 0.12),
                     noise(0.5, 0.18, 0.15, 0.05, 0.4, 0.1)))

    # 宝石镶嵌：清脆的"叮"
    save('gem', mix(tone(1760, 0.26, 'sine', 0.5, 0.002, 0.23, 0.03),
                    tone(2640, 0.18, 'sine', 0.22, 0.002, 0.16, 0.02)))

    # 宠物获得：可爱的上行三音
    save('pet', seq([784, 1047, 1568], 0.09, 'sine', 0.45))


if __name__ == '__main__':
    build()
    print('音效已生成到', OUT)

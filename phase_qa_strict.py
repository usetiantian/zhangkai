#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
修真文5关严格验证
- 字数 >= 3000
- AI味 <= 3/千字 (严禁词表: 仿佛/宛如/犹如/蓦然/骤然/刹那/瞬间/缓缓/轻轻/深深/默默/静静/微微/淡淡/一抹/一丝/一股/熠熠/灼灼/皎皎)
- 句长std > 5
- 苏禾出场 >= 1次
- 章尾钩子
"""
import re
import sys
import math
from pathlib import Path

FORBIDDEN = ['仿佛','宛如','犹如','蓦然','骤然','刹那','瞬间','缓缓','轻轻','深深','默默','静静','微微','淡淡','一抹','一丝','一股','熠熠','灼灼','皎皎']
HOOK_PATTERNS = [
    r'这一夜的变故.{0,10}将如何',
    r'苏禾不知道.{0,20}接下来',
    r'她永远不会想到.{0,20}那少年',
    r'然而.{0,10}真正的考验',
    r'将如何影响',
    r'才刚刚开始',
    r'就在此时',
    r'忽然',
    r'却没有想到',
    r'真正的考验.{0,10}才刚刚开始',
    r'这.{0,8}变故',
    r'谁.{0,5}知道',
    r'谁.{0,5}能想到',
    r'不知.{0,5}道.{0,15}等.{0,5}她',
    r'下一刻',
]

def check(path):
    p = Path(path)
    text = p.read_text(encoding='utf-8', errors='ignore')
    # 去掉 markdown 标题/分隔/引用行
    lines = text.split('\n')
    body_lines = []
    for ln in lines:
        s = ln.strip()
        if not s: continue
        if s.startswith('#'): continue
        if s.startswith('---'): continue
        if s.startswith('>'): continue
        if re.match(r'^[\-=]{3,}$', s): continue
        body_lines.append(ln)
    body = '\n'.join(body_lines)

    # 字数（中文字符）
    cn_chars = re.findall(r'[\u4e00-\u9fff]', body)
    word_count = len(cn_chars)

    # AI味词计数
    ai_hits = []
    for w in FORBIDDEN:
        cnt = body.count(w)
        if cnt > 0:
            ai_hits.append((w, cnt))
    ai_total = sum(c for _, c in ai_hits)
    ai_per_k = ai_total * 1000 / max(word_count, 1)

    # 句长方差
    sentences = re.split(r'[。!?！？\n]+', body)
    sentences = [s for s in sentences if len(s.strip()) >= 2]
    if len(sentences) >= 2:
        lens = [len(s) for s in sentences]
        avg = sum(lens)/len(lens)
        var = sum((l-avg)**2 for l in lens)/len(lens)
        std = math.sqrt(var)
    else:
        std = 0

    # 苏禾出场
    suhe_count = body.count('苏禾')

    # 章尾钩子（看最后 500 字）
    tail = body[-500:] if len(body) > 500 else body
    hook_found = None
    for pat in HOOK_PATTERNS:
        m = re.search(pat, tail)
        if m:
            hook_found = pat
            break

    # 段落数
    paragraphs = [p for p in body.split('\n') if p.strip() and not p.strip().startswith('#')]
    para_count = len(paragraphs)
    para_lens = [len(p.strip()) for p in paragraphs]
    avg_para = sum(para_lens)/max(len(para_lens), 1) if para_lens else 0

    # 首行缩进
    indented = sum(1 for p in paragraphs if p.startswith('　　'))
    indent_rate = indented / max(len(paragraphs), 1)

    print(f'=== {p.name} ===')
    print(f'字数: {word_count} (要求 >=3000)  {"✅" if word_count>=3000 else "❌"}')
    print(f'AI味: {ai_per_k:.2f}/千字  命中: {ai_hits}  {"✅" if ai_per_k<=3 else "❌"}')
    print(f'句长std: {std:.2f}  {"✅" if std>5 else "❌"}')
    print(f'苏禾: {suhe_count}次  {"✅" if suhe_count>=1 else "❌"}')
    print(f'章尾钩子: {"✅ "+hook_found if hook_found else "❌ 未找到"}')
    print(f'段落: {para_count}段, 平均段长 {avg_para:.1f}字符, 首行缩进率 {indent_rate*100:.0f}%')

    ok = word_count>=3000 and ai_per_k<=3 and std>5 and suhe_count>=1 and hook_found
    print(f'5关全过: {"✅ 是" if ok else "❌ 否"}')
    return ok

if __name__ == '__main__':
    for arg in sys.argv[1:]:
        check(arg)
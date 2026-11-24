"""从参考书抽"文风样例"，直接喂给 Writer 当范例。

抽象指标模型学不会（"少写动作"它只会写短），**给真片段**才学得会质感。
"""
import io
import os
import re
import sys

SAMPLE = ("D:/node/阅读笔记/七猫免费小说/方法论/_学习样本/"
          "凡人修仙传同流派小说集_9本")
IND = chr(0x3000) * 2
QL = chr(0x201C)


def pick(book="仙逆", n_ch=3):
    fn = "仙逆.txt" if book == "仙逆" else "凡人修仙传人界篇.txt"
    raw = io.open(os.path.join(SAMPLE, fn), encoding="utf-8", errors="replace").read()
    parts = re.split(r"(?m)^\s*(第[一二三四五六七八九十百千零0-9]+章.*)$", raw)
    chaps = [(parts[i].strip(), parts[i + 1].strip()) for i in range(1, len(parts), 2)]
    # 取中段章节（开篇有介绍性，中段更像正文的叙述质地）
    mid = chaps[len(chaps) // 4: len(chaps) // 4 + n_ch]
    out = []
    for title, body in mid:
        lines = [l.rstrip() for l in body.split(chr(10)) if l.strip()]
        paras = [l for l in lines if l.startswith(IND)]
        dlg = [l for l in paras if QL in l]
        nar = [l for l in paras if QL not in l]
        # 取中段连续的叙述 + 对白，避开开头的介绍段和结尾的钩子
        s = len(paras) // 3
        out.append(("开篇叙述", paras[:3]))
        out.append(("中段叙述", nar[len(nar) // 4: len(nar) // 4 + 4]))
        out.append(("对白片段", dlg[:4]))
        out.append(("收束", paras[-3:]))
    return out


def main():
    book = sys.argv[1] if len(sys.argv) > 1 else "仙逆"
    n = int(sys.argv[2]) if len(sys.argv) > 2 else 2
    for title, paras in pick(book, n):
        print("【%s】" % title)
        for p in paras:
            print(p)
        print()


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    main()

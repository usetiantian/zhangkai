"""参考书实测：任何一本你认可的网文都能当标尺。

抽样若干章，算出文风指纹，用来生成这本书的目标带。
用法: python tools/novel/refs.py <参考书.txt> [抽样章数]
"""
import io
import os
import random
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import style_check as sc

CHAP_RE = re.compile(r"(?m)^\s*第[一二三四五六七八九十百千零0-9]+章.*$")


def split_chapters(text):
    return [c.strip() for c in CHAP_RE.split(text) if len(c.strip()) > 1200]


def measure(path, n=40, seed=11):
    raw = io.open(path, encoding="utf-8", errors="replace").read()
    chs = split_chapters(raw)
    if not chs:
        raise SystemExit("没切出章节：%s" % path)
    random.seed(seed)
    pick = random.sample(chs, min(n, len(chs)))
    samples, lens = {}, []
    tmp = os.path.join(HERE, "_tmp_ref.md")
    for c in pick:
        io.open(tmp, "w", encoding="utf-8").write(c)
        fp = sc.fingerprint(tmp)
        lens.append(len(c))
        for k, v in fp.items():
            if isinstance(v, (int, float)):
                samples.setdefault(k, []).append(v)
        count = len(pick)
    os.remove(tmp)
    out = {}
    for k, vals in samples.items():
        vals = sorted(vals)
        n = len(vals)
        out[k] = vals[n // 2]
        out[k + "_p25"] = vals[max(0, int(n * 0.25) - 1)]
        out[k + "_p75"] = vals[min(n - 1, int(n * 0.75))]
        out[k + "_p90"] = vals[min(n - 1, int(n * 0.90))]
    out["单章总字符"] = sorted(lens)[len(lens) // 2]
    out["单章总字符_p25"] = sorted(lens)[max(0, int(len(lens) * 0.25) - 1)]
    out["单章总字符_p75"] = sorted(lens)[min(len(lens) - 1, int(len(lens) * 0.75))]
    out["抽样章数"] = count
    return out


def main():
    path = sys.argv[1]
    n = int(sys.argv[2]) if len(sys.argv) > 2 else 40
    st = measure(path, n)
    for k in ("平均句长", "平均段长", "短句率(<15)", "长句率(>30)", "短段率(<60)",
              "长段率(>100)", "对白段率", "台词均字", "水词", "套路词", "单章总字符"):
        print("%-14s %.1f" % (k, st.get(k, 0)))


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    main()

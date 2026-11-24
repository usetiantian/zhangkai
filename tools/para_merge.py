"""把正文里过碎的叙述段并成一段一个信息单元（学凡人/仙逆的排版）。

- 只并叙述段（不含引号的正文段），对话段保持独立
- 目标段长 limit 字左右（凡人 53.6 / 仙逆 47.4）
- 段落缩进用全角空格 U+3000 两个（中文网文标准排版）

用法: python tools/para_merge.py <正文.md> [--limit 58]
"""
import io
import sys

IND = chr(0x3000) * 2
NL = chr(10)


def is_narration(raw):
    t = raw.rstrip()
    if not t.startswith(IND):
        return False
    if "“" in t or "\"" in t:
        return False
    if t.lstrip(IND).startswith("——"):
        return False
    return True


def merge(text, limit=58):
    blocks = text.split(NL + NL)
    out, buf = [], []
    for b in blocks:
        raw = b.rstrip()
        if (is_narration(raw) and buf and is_narration(buf[-1])
                and not buf[-1].lstrip(IND).startswith("——")):
            merged = buf[-1] + raw
            if len(merged) <= limit:
                buf[-1] = merged
                continue
        if buf:
            out.append(NL + NL.join(buf))
            buf = []
        buf.append(raw)
    if buf:
        out.append(NL + NL.join(buf))
    return NL + NL.join(out)


def main():
    args = sys.argv[1:]
    path = args[0]
    limit = 58
    if "--limit" in args:
        limit = int(args[args.index("--limit") + 1])
    s = io.open(path, encoding="utf-8").read()
    out = merge(s, limit)
    io.open(path, "w", encoding="utf-8").write(out)
    print("%s | 上限 %d | 段数 %d -> %d" % (path, limit, len(s.split(NL + NL)), len(out.split(NL + NL))))


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    main()

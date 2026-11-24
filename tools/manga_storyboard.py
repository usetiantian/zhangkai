"""分镜任务书 -> H3 官方三字段分镜，带**自动重试修复**。

插件的 prepareOfficialStoryboardOutput 会返回 repairPrompt（它写清楚了哪里不合规），
但导演台前端从来没用过它。这里把它接上：不合格就带着修复指令重问，最多 3 轮。

用法:
  python tools/manga_storyboard.py <分镜任务书.txt> [-o out.txt] [--context 定妆.txt] [--ep "第一集 xxx"]
"""
import io
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import guofeng_manga as gm

MAX_ROUND = 3


def _quant_fix(error):
    """插件的修复指令只说"保持总时长"，模型不知道超了多少。补上量化约束。"""
    import re
    m = re.search(r"源时长\s*([\d.]+)\s*秒与导入时长\s*([\d.]+)\s*秒不守恒", error)
    if not m:
        return ""
    src = float(m.group(1))
    got = float(m.group(2))
    delta = got - src
    ratio = src / got if got else 1.0
    return (
        "\n【本次必须修正的具体数字】\n"
        "当前分镜的镜头总跨度是 %.3f 秒，但本集目标总时长是 %.3f 秒，超出 %.3f 秒。\n"
        "请按下面的硬约束重排时间轴：\n"
        "1. 全片 Shot 总数不超过 %d 个，每个 Shot 2–6 秒。\n"
        "2. 把多余的时长压掉：可以合并相邻的同场次 Shot、删掉与剧情无关的镜头、"
        "或把连续动作合并成一个 Shot；**不得删改台词和剧情顺序**。\n"
        "3. 所有 At 时间戳按比例收缩到目标时长（约 %.3f 倍），"
        "最后一个 Shot 的结束时间必须正好是 %.3f 秒。\n"
        "4. director_import_manifest.source_total_duration_seconds 必须写 %.3f。\n"
        "5. 每个 Shot 的台词字数仍要满足「该 Shot 秒数 × 4」，"
        "时间被压缩后台词超速的 Shot 必须再拆成两个 Shot。\n"
        % (got, src, delta, max(12, int(src / 4)), ratio, src, src))


def validate(board, original_input, seed=0):
    payload = {"storyboard": board, "original_input": original_input, "seed": seed}
    proc = subprocess.run(["node", os.path.join(HERE, "h3_segments.mjs")],
                          input=json.dumps(payload, ensure_ascii=False),
                          capture_output=True, text=True, encoding="utf-8", errors="replace")
    if proc.returncode != 0:
        return {"ok": False, "error": "节点脚本失败: " + proc.stderr[:300], "repair_prompt": ""}
    try:
        return json.loads(proc.stdout)
    except Exception as e:
        return {"ok": False, "error": "返回不是 JSON: " + str(e), "repair_prompt": ""}


def main():
    args = sys.argv[1:]
    src = args[0]
    out = None
    context = ""
    episode = ""
    for i, a in enumerate(args):
        if a == "-o" and i + 1 < len(args):
            out = args[i + 1]
        elif a == "--context" and i + 1 < len(args):
            context = gm._read(args[i + 1])
        elif a == "--ep" and i + 1 < len(args):
            episode = args[i + 1]
    beat = gm._read(src)
    user = beat.strip()
    if context:
        user = context.strip() + gm.NL2 + gm.NL2 + user
    user = user + gm.NL2 + gm.NL2 + "风格要求：" + gm.GUOFENG_STYLE
    system = gm.sys_prompt("create_storyboard")

    board = ""
    for rnd in range(1, MAX_ROUND + 1):
        print("[第%d轮] 生成分镜 ..." % rnd, flush=True)
        board = gm.ai_call(system, user, max_tokens=6000)
        res = validate(board, beat)
        if res.get("ok"):
            dest = out or src
            gm._write(dest, board)
            print("段数:", len(res["segments"]), "| 总时长:", res.get("source_duration"))
            return 0
        print("  不合格:", res.get("error"))
        repair = res.get("repair_prompt") or ""
        if not repair:
            print("  没有修复指令，放弃重试")
            gm._write(out or src, board)
            return 1
        print("  带着修复指令重问 ...")
        extra = _quant_fix(res.get("error") or "")
        user = (repair + extra + gm.NL2 + gm.NL2 + user)
    gm._write(out or src, board)
    print("%d 轮都没通过，最后一版已保存待人工检查" % MAX_ROUND)
    return 1


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.exit(main())

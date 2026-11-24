"""漫剧成片体检报告 —— 每段一份量化体检，替代"人眼看 + 听"。
用法: python qa_report.py <项目目录> [--no-video]
输出: 每段的视频规格 / 音频指标 / 台词体检 / 语音-画面时间对齐
"""
import av, numpy as np, os, re, sys, json, glob, io

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# 台词语速规则（与插件提示词一致）
SLOW, NORMAL, FAST = 2.5, 4.0, 5.5


def load_audio(path):
    chunks = []
    with av.open(path) as c:
        if not c.streams.audio:
            return None, 0
        sr = c.streams.audio[0].codec_context.sample_rate
        for fr in c.decode(audio=0):
            a = fr.to_ndarray()
            a = a.astype(np.float32) / 32768.0 if a.dtype == np.int16 else a.astype(np.float32)
            if a.ndim > 1:
                a = a.mean(axis=0)
            chunks.append(a)
    return (np.concatenate(chunks) if chunks else None), sr


def video_info(path):
    with av.open(path) as c:
        v = c.streams.video[0]
        dur = float(c.duration) / av.time_base if c.duration else 0.0
        return dur, v.codec_context.width, v.codec_context.height, float(v.average_rate or 24)


def shot_windows(prompt):
    """从段提示词里解析出每个 Shot 的绝对时间窗，以及台词所属 Shot。"""
    out = []
    for m in re.finditer(r"\[Shot\s+(\d+)\]\s*(?:At\s+(\d+):(\d+):(\d+)\.(\d+))?(.*?)(?=\[Shot\s+\d+\]|\Z)",
                         prompt, re.S):
        n = int(m.group(1))
        start = (int(m.group(2)) * 3600 + int(m.group(3)) * 60 + int(m.group(4))
                 + int(m.group(5)) / 1000.0) if m.group(2) else None
        body = m.group(6)
        lines = re.findall(r"<d>\[Chinese\](.*?)</d>", body)
        out.append({"n": n, "start": start, "lines": lines})
    # 没带 At 的 Shot 用前一个的起点兜底
    prev = 0.0
    for s in out:
        if s["start"] is None:
            s["start"] = prev
        prev = s["start"]
    return out


def estimate_speech(line):
    """估算一句台词的自然朗读时长（秒）。"""
    core = re.sub(r"[，。！？、；：…—\s]", "", line)
    n = len(core)
    t = n / 3.5
    t += 0.15 * line.count("，") + 0.15 * line.count("、")
    t += 0.30 * (line.count("。") + line.count("！") + line.count("？") + line.count("…"))
    return max(1.2, t)


def analyze_audio(a, sr):
    peak = 20 * np.log10(max(float(np.abs(a).max()), 1e-9))
    rms = 20 * np.log10(max(float(np.sqrt((a ** 2).mean())), 1e-9))
    zcr = float((np.diff(np.sign(a)) != 0).mean())
    fl = max(1, int(sr * 0.1))
    n = len(a) // fl
    env = 20 * np.log10(np.maximum(np.sqrt((a[:n * fl].reshape(n, fl) ** 2).mean(axis=1)), 1e-6))
    clipped = int((np.abs(a) >= 0.999).sum())
    # 音节率：RMS 包络的 2-12Hz 调制峰
    e = env - env.mean()
    sp = np.abs(np.fft.rfft(e * np.hanning(len(e))))
    fr = np.fft.rfftfreq(len(e), 0.1)
    band = (fr >= 2) & (fr <= 12)
    syl = float(fr[band][np.argmax(sp[band])]) if band.any() else 0.0
    band_pct = float(sp[band].sum() / (sp.sum() + 1e-12)) if band.any() else 0.0
    # 语音带能量占比
    win = 1024
    lo = mid = hi = 0.0
    k = 0
    for i in range(0, len(a) - win, win * 4):
        s = np.abs(np.fft.rfft(a[i:i + win] * np.hanning(win)))
        f = np.fft.rfftfreq(win, 1.0 / sr)
        tot = s.sum() + 1e-12
        lo += s[f < 300].sum() / tot
        mid += s[(f >= 300) & (f < 3400)].sum() / tot
        hi += s[f >= 3400].sum() / tot
        k += 1
    k = max(1, k)
    return {"peak": peak, "rms": rms, "zcr": zcr, "clipped": clipped,
            "syl": syl, "band_pct": band_pct, "lo": lo / k, "mid": mid / k, "hi": hi / k,
            "env": env, "sr": sr}


def report(project):
    seg_vids = sorted(glob.glob(os.path.join(project, "漫剧_seg*_一次采样.mp4")))
    print("=" * 78)
    print("漫剧成片体检报告")
    print("项目:", os.path.basename(project))
    print("=" * 78)
    totals = {"over": 0, "clip": 0, "lines": 0, "seg": 0}
    for vp in seg_vids:
        tag = os.path.basename(vp)
        m = re.search(r"seg(\d+)", tag)
        segn = m.group(1) if m else "?"
        meta_p = os.path.join(project, "漫剧_seg%s_00001_.json" % segn)
        prompt = ""
        if os.path.exists(meta_p):
            try:
                with io.open(meta_p, encoding="utf-8", errors="replace") as fh:
                    prompt = json.load(fh).get("prompt", "")
            except Exception as exc:
                print("  [元数据读取失败] %s: %s" % (os.path.basename(meta_p), exc))
                prompt = ""
        print("  [调试] meta=%s prompt长度=%d" % (os.path.basename(meta_p), len(prompt)))
        dur, w, h, fps = video_info(vp)
        print("\n--- %s ---" % tag)
        print("  视频: %.2fs | %dx%d | %.1ffps" % (dur, w, h, fps))
        wav = vp + ".h3audio.delivery.wav"
        src = wav if os.path.exists(wav) else vp
        a, sr = load_audio(src)
        if a is None:
            print("  音频: 无")
            continue
        m2 = analyze_audio(a, sr)
        print("  音频: 峰值%.1fdB 均%.1fdB 削波样本%d | 音节率%.1fHz | 低频%.2f 语音带%.2f 高频%.2f"
              % (m2["peak"], m2["rms"], m2["clipped"], m2["syl"], m2["lo"], m2["mid"], m2["hi"]))
        if m2["clipped"] > 0:
            totals["clip"] += 1
        shots = shot_windows(prompt)
        over = []
        lines_total = 0
        for i, s in enumerate(shots):
            if not s["lines"]:
                continue
            nxt = shots[i + 1]["start"] if i + 1 < len(shots) else dur
            span = max(0.1, nxt - s["start"])
            need = sum(estimate_speech(l) for l in s["lines"])
            lines_total += len(s["lines"])
            rate = sum(len(re.sub(r"[^一-鿿]", "", l)) for l in s["lines"]) / max(0.1, span)
            flag = ""
            if need > span + 0.05:
                flag = "  <-- 超速"
                over.append((s["n"], len(s["lines"]), round(span, 1), round(need, 1), round(rate, 1)))
            print("    Shot %-3d %5.1f-%5.1fs  台词%d句 需%5.1fs 实%5.1fs %.1f字/秒%s"
                  % (s["n"], s["start"], nxt, len(s["lines"]), need, span, rate, flag))
        totals["seg"] += 1
        totals["lines"] += lines_total
        totals["over"] += len(over)
    print("\n" + "=" * 78)
    print("汇总: %d 段 | 台词 %d 句 | 超速 %d 处 | 削波 %d 段" % (
        totals["seg"], totals["lines"], totals["over"], totals["clip"]))
    print("=" * 78)


if __name__ == "__main__":
    proj = sys.argv[1]
    report(proj)


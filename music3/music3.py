#!/usr/bin/env python3
"""music3.py -- one sentence to music (CLI). ComfyUI + MiniMax Music3, local."""
import argparse, os, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import engine


def main():
    ap = argparse.ArgumentParser(description="一句话生成音乐（ComfyUI + MiniMax Music3）")
    ap.add_argument("caption", help="风格/情绪/乐器/场景，写成制作特征而非指令")
    ap.add_argument("--lyrics", default="", help="歌词，留空则纯器乐")
    ap.add_argument("--lyrics-file")
    ap.add_argument("--auto-lyrics", action="store_true", help="调 MiniMax API 自动写歌词")
    ap.add_argument("--lyric-hint", default="", help="自动歌词的主题（默认用 caption）")
    ap.add_argument("-d", "--duration", type=float, default=60.0, help="最长秒数 0.04~360")
    ap.add_argument("-s", "--seed", type=int, default=None, help="随机种子，默认随机")
    ap.add_argument("--steps", type=int, default=20)
    ap.add_argument("--cfg", type=float, default=1.7)
    ap.add_argument("--top-k", type=int, default=50)
    ap.add_argument("--format", default="mp3", choices=["mp3", "flac"])
    ap.add_argument("--quality", default="320k")
    ap.add_argument("--out", default="out")
    ap.add_argument("--server", default=engine.DEFAULT_SERVER, help="ComfyUI 地址")
    ap.add_argument("--lowvram", action="store_true", help="用 int8 版 DiT，省显存")
    args = ap.parse_args()

    seed = args.seed if args.seed is not None else int.from_bytes(os.urandom(4), "big")

    lyrics = args.lyrics
    if args.lyrics_file:
        lyrics = open(args.lyrics_file, encoding="utf-8").read()
    elif args.auto_lyrics:
        try:
            lyrics = engine.ai_lyrics(args.lyric_hint or args.caption,
                                      os.environ.get("MINIMAX_API_KEY", ""), args.caption)
        except engine.TextError as e:
            print("[music3] 自动歌词失败(%s)，改为纯器乐" % e, file=sys.stderr)
            lyrics = ""

    os.makedirs(args.out, exist_ok=True)
    tag = "".join(c if (c.isalnum() or c in "-_") else "_" for c in args.caption)[:28]
    wf = engine.build_workflow(
        caption=args.caption, lyrics=lyrics, seed=seed,
        duration=args.duration, cfg_scale=args.cfg, top_k=args.top_k, steps=args.steps,
        unet=engine.MODELS["unet_lowvram"] if args.lowvram else engine.MODELS["unet"],
        prefix="music3/" + (tag or "song"),
        fmt=args.format, quality=args.quality)

    print("[music3] %s" % args.caption)
    print("[music3] 歌词:%s | 时长上限 %ss | seed %s" % ("有" if lyrics else "无(纯器乐)", args.duration, seed))

    c = engine.ComfyClient(args.server)
    if not c.alive():
        sys.exit("连不上 ComfyUI (%s)\n先启动 run_nvidia_gpu.bat" % args.server)
    try:
        audio, fname = c.run(wf)
    except engine.ComfyError as e:
        sys.exit("[music3] 失败: %s" % e)

    out_path = os.path.join(args.out, os.path.basename(fname))
    open(out_path, "wb").write(audio)
    print("[music3] 完成 -> %s (%.0f KB)" % (out_path, len(audio) / 1024))


if __name__ == "__main__":
    main()

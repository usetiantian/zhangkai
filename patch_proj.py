# -*- coding: utf-8 -*-
D = "D:/ComfyUI_windows_portable/ComfyUI/output/问剑长生_漫剧/03_分镜脚本/"
F = D + "produce_ep.py"
t = open(F, encoding="utf-8").read()
t = t.replace('def produce(ep_no, quality="hd", tts_backend=None, force_storyboard=False,\n            skip_tts=False, log=print):',
              'def produce(ep_no, quality="hd", tts_backend=None, force_storyboard=False,\n            skip_tts=False, log=print, proj=None):')
t = t.replace('    proj = "wjcs_ep%03d" % ep_no', '    proj = proj or ("wjcs_ep%03d" % ep_no)')
open(F, "w", encoding="utf-8").write(t)

F2 = D + "batch_run.py"
t2 = open(F2, encoding="utf-8").read()
t2 = t2.replace('    ap.add_argument("--retry-failed", action="store_true")',
                '    ap.add_argument("--retry-failed", action="store_true")\n    ap.add_argument("--proj-suffix", default=None, help="工程号后缀，用于重跑不覆盖旧结果")')
t2 = t2.replace('            res = produce(ep, quality=a.quality, skip_tts=a.no_tts,\n                          log=lambda m: log_line("  " + m))',
                '            res = produce(ep, quality=a.quality, skip_tts=a.no_tts,\n                          log=lambda m: log_line("  " + m),\n                          proj=("wjcs_ep%03d_%s" % (ep, a.proj_suffix)) if a.proj_suffix else None)')
open(F2, "w", encoding="utf-8").write(t2)
print("proj 参数已加")

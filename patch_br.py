# -*- coding: utf-8 -*-
D = "D:/ComfyUI_windows_portable/ComfyUI/output/问剑长生_漫剧/03_分镜脚本/"
F = D + "batch_run.py"
t = open(F, encoding="utf-8").read()
t = t.replace('    ap.add_argument("--proj-suffix", default=None, help="工程号后缀，用于重跑不覆盖旧结果")',
              '    ap.add_argument("--proj-suffix", default=None, help="工程号后缀，用于重跑不覆盖旧结果")\n'
              '    ap.add_argument("--only-shots", default=None, help="只重跑指定镜号, 逗号分隔")')
t = t.replace('''                          log=lambda m: log_line("  " + m),
                          proj=("wjcs_ep%03d_%s" % (ep, a.proj_suffix)) if a.proj_suffix else None)''',
              '''                          log=lambda m: log_line("  " + m),
                          only_shots=only,
                          proj=("wjcs_ep%03d_%s" % (ep, a.proj_suffix)) if a.proj_suffix else None)''')
t = t.replace('    m = load_manifest()',
              '    only = None\n'
              '    if a.only_shots:\n'
              '        only = [int(x) for x in a.only_shots.split(",") if x.strip()]\n'
              '    m = load_manifest()')
open(F, "w", encoding="utf-8").write(t)
print("batch_run.py patched")

# -*- coding: utf-8 -*-
F = "D:/ComfyUI_windows_portable/ComfyUI/output/问剑长生_漫剧/03_分镜脚本/produce_ep.py"
t = open(F, encoding="utf-8").read()
t = t.replace('def build_h3_prompt(sh, pairs):', 'def build_h3_prompt(sh, pairs, overrides=None):')
t = t.replace('''        app = ""
        meta = idx.get(name) or {}
        if meta.get("appearance"):
            app = "（%s）" % meta["appearance"]''',
'''        app = ""
        meta = idx.get(name) or {}
        ov = (overrides or {}).get(name)
        if ov:
            app = "（%s）" % ov
        elif meta.get("appearance"):
            app = "（%s）" % meta["appearance"]''')
t = t.replace('def build_segments(sb, pairs, only=None):',
              'def build_segments(sb, pairs, only=None, overrides=None):')
t = t.replace('H.make_segment(build_h3_prompt(sh, p), 880211 + sh["idx"],\n                            duration=SHOT_DUR,',
              'H.make_segment(build_h3_prompt(sh, p, overrides), 880211 + sh["idx"],\n                            duration=SHOT_DUR,')
t = t.replace('    segs = build_segments(sb, pairs, only=only_shots)',
              '    ov = sb.get("char_overrides") or {}\n    segs = build_segments(sb, pairs, only=only_shots, overrides=ov)')
t = t.replace('H.make_segment(build_h3_prompt(sh, p), 880211 + sh["idx"],\n                                    duration=SHOT_DUR, refs=[f for _, f in p],',
              'H.make_segment(build_h3_prompt(sh, p, ov), 880211 + sh["idx"],\n                                    duration=SHOT_DUR, refs=[f for _, f in p],')
open(F, "w", encoding="utf-8").write(t)
print("char_overrides 支持已加")

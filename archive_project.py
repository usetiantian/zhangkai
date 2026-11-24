# -*- coding: utf-8 -*-
"""把《问剑长生》漫剧工程的全部资料归档到 ComfyUI/output/问剑长生_漫剧"""
import os, shutil, glob, re
OUT  = r"D:\ComfyUI_windows_portable\ComfyUI\output"
PROJ = os.path.join(OUT, "问剑长生_漫剧")
WS   = r"C:\Users\87999\claude-workspace"
HD   = r"D:\ComfyUI_windows_portable\ComfyUI"
DIRS = {k: os.path.join(PROJ, k) for k in
        ["01_成片", "02_分镜图", "03_分镜脚本", "04_参考图", "05_分段素材", "06_文档"]}
for d in DIRS.values(): os.makedirs(d, exist_ok=True)

def cp(src, dst):
    if os.path.isfile(src):
        shutil.copy2(src, dst); print("  +", os.path.basename(dst))
    else:
        print("  ! MISSING", os.path.basename(src))

print("[1] 成片")
cp(os.path.join(WS, "问剑长生_血祭古剑_EP01.mp4"),
   os.path.join(DIRS["01_成片"], "问剑长生_EP01_血祭古剑_20s.mp4"))

print("[2] 分镜图")
cp(os.path.join(WS, "sheet_out", "contact_sheet.png"),
   os.path.join(DIRS["02_分镜图"], "EP01_四镜分镜图.png"))
for n, s in [("EP01_镜1_云海之巅.png","shot1.png"), ("EP01_镜2_青光入体.png","shot2.png"),
             ("EP01_镜3_铁匠打铁.png","shot3.png"), ("EP01_镜4_血祭触剑.png","shot4.png")]:
    cp(os.path.join(WS,"sheet_out",s), os.path.join(DIRS["02_分镜图"], n))

print("[3] 脚本 (去硬编码 -> 自包含)")
SCRIPTS = ["h3_driver.py","gen_wjcs_ep01.py","gen_wjcs_seg2fix.py","gen_wjcs_2ndpass.py",
           "assemble_ep01.py","make_ref.py","make_ref2b.py","wjcs_submit.py","wjcs_poll.py",
           "wjcs_concat.py","archive_project.py"]
WS_RE   = re.compile(r'r"C:\Users\87999\claude-workspace\([^"]+)"')
WS_RE2  = re.compile(r'r"C:\Users\87999\claude-workspace"')
SELF    = 'os.path.dirname(os.path.abspath(__file__))'
for s in SCRIPTS:
    p = os.path.join(WS, s)
    if not os.path.isfile(p):
        print("  ! MISSING", s); continue
    t = open(p, encoding="utf-8").read()
    t = WS_RE.sub(lambda m: 'os.path.join(%s, "%s")' % (SELF, m.group(1)), t)
    t = WS_RE2.sub(SELF, t)
    if "import os" not in t: t = "import os\n" + t
    open(os.path.join(DIRS["03_分镜脚本"], s), "w", encoding="utf-8").write(t)
    print("  +", s)

print("[4] 参考图")
for n, s in [("wjcs_linwen_林问定妆照.png","wjcs_linwen.png"),
             ("wjcs_linwen_m2_林问卧房版.png","wjcs_linwen_m2.png")]:
    cp(os.path.join(HD,"input",s), os.path.join(DIRS["04_参考图"], n))

print("[5] 分段素材")
BASE = os.path.join(HD,"output","video","h3director")
for proj, seg, name in [("wjcs_xueji_v1",1,"镜1_云海之巅.mp4"), ("wjcs_xueji_v2",1,"镜2_青光入体.mp4"),
                        ("wjcs_xueji_v1",3,"镜3_铁匠打铁.mp4"), ("wjcs_xueji_v1",4,"镜4_血祭触剑.mp4")]:
    g = sorted(glob.glob(os.path.join(BASE, proj, "漫剧_seg%d_*二次采样*.mp4" % seg)))
    if g: cp(g[-1], os.path.join(DIRS["05_分段素材"], name))
    else: print("  ! MISSING seg", proj, seg)
print("done ->", PROJ)

# -*- coding: utf-8 -*-
D = "D:/ComfyUI_windows_portable/ComfyUI/output/问剑长生_漫剧/03_分镜脚本/"

# ---------- ref_lib: 强化年龄/性别 ----------
F = D + "ref_lib.py"
t = open(F, encoding="utf-8").read()

helper = '''
FEMALE_HINT = ("女", "娘", "姐", "妹", "妃", "后", "婆", "姑", "姨", "婶", "母", "妻", "女儿", "姑娘")
MALE_HINT = ("男", "翁", "老", "父", "兄", "弟", "汉", "爷", "叔", "公", "先生", "少年", "公子", "和尚")
ELDER_HINT = ("翁", "老", "白须", "花白", "山羊胡", "苍老", "长者", "老者", "皴", "六十", "七十", "五十", "八十")


def _infer_gender(text):
    s = str(text or "")
    f_hits = sum(1 for k in FEMALE_HINT if k in s)
    m_hits = sum(1 for k in MALE_HINT if k in s)
    if f_hits > m_hits:
        return "female"
    if m_hits > f_hits:
        return "male"
    return ""


def _is_elder(text):
    s = str(text or "")
    return any(k in s for k in ELDER_HINT)


def age_gender_tokens(text):
    """从外貌描述里推断并返回 (正向强化词, 反向排除词)。"""
    g = _infer_gender(text)
    old = _is_elder(text)
    pos, neg = "", ""
    if g == "female":
        pos = "a woman, female character"
        neg = ", man, male, boy, young man"
    elif g == "male":
        pos = "a man, male character"
        neg = ", woman, female, girl"
    if old:
        pos += ", elderly, visibly old, deep wrinkles, white hair, aged face"
        neg += ", young, youthful, teenager, smooth skin, baby face"
    return pos, neg


'''
anchor = "def load_index():"
assert anchor in t
t = t.replace(anchor, helper + anchor)

old = '''    pos = POS_TMPL.format(appearance=appearance or role_desc or ("%s" % role),
                           role=role_desc or "a character in a Chinese xianxia story")'''
new = '''    ap = appearance or role_desc or ("%s" % role)
    extra_pos, extra_neg = age_gender_tokens(ap + " " + role_desc)
    pos = POS_TMPL.format(appearance=ap,
                           role=(role_desc or "a character in a Chinese xianxia story") + ", " + extra_pos)
    neg = NEG + extra_neg'''
assert old in t
t = t.replace(old, new)
open(F, "w", encoding="utf-8").write(t)
print("ref_lib.py 强化完成")

# ---------- postproduce: 角色名标签移到字幕上方 ----------
F2 = D + "postproduce.py"
t2 = open(F2, encoding="utf-8").read()
old2 = '"Style: Role,%s,26,&H00C8E6FF,&H000000FF,&H00202020,&H80000000,0,1,0,0,"'
new2 = '"Style: Role,%s,26,&H00C8E6FF,&H000000FF,&H00202020,&H80000000,0,0,0,0,"'
assert old2 in t2
t2 = t2.replace(old2, new2)
old3 = '"100,100,0,0,1,2,0.4,8,60,60,10,1'
new3 = '"100,100,0,0,1,2,0.4,2,60,60,96,1'
assert old3 in t2
t2 = t2.replace(old3, new3)
open(F2, "w", encoding="utf-8").write(t2)
print("postproduce.py 角色名样式已修")

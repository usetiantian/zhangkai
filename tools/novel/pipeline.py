"""一本网文的单章生产流水线（可复用于任何书）。

借鉴 NovelForge 的六步 agent 流水线、MuMuAINovel 的风格/伏笔/一致性/评分、
Tonade 的知识库回写、马良AI的剧情推演抽卡。

流程：
  plan    Planner   → 场次计划（时间轴 + 每场一个动作 + 钩子）
  cards   Characters→ 角色意图卡（要什么/知道什么/情绪/怎么开口）→ 对话才有潜台词
  write   Writer    → 正文（风格指南 + 计划 + 意图卡 + 台账）
  review  Reviewer  → 硬指标 + 重复检测 + 一致性 → S/A/B/C/D
  record  回写台账（新增事实 + 角色状态变化 + 进度表）

用法:
  python tools/novel/pipeline.py <书目录> --chapter 03 --source 章节原文.txt
  python tools/novel/pipeline.py <书目录> --chapter 03 --source x.txt --only plan
  python tools/novel/pipeline.py <书目录> --chapter 03 --check-only
"""
import io
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
for _p in (HERE, ROOT, os.path.join(ROOT, "tools")):
    if _p not in sys.path:
        sys.path.insert(0, _p)
import guofeng_manga as gm
import review_chapter as rc
import style_model as smod

NL = chr(10)
IND = chr(0x3000) * 2


def paths(book):
    return {
        "ledger": os.path.join(book, "00_写作台账.md"),
        "guide": os.path.join(book, "风格指南.md"),
        "plan": os.path.join(book, "计划"),
        "text": os.path.join(book, "正文"),
        "review": os.path.join(book, "审稿"),
    }


def ensure(book):
    p = paths(book)
    for k in ("plan", "text", "review"):
        os.makedirs(p[k], exist_ok=True)
    return p


def read(path, default=""):
    if os.path.exists(path):
        return io.open(path, encoding="utf-8").read()
    return default


PLANNER_RULES = """
【铁律：一章只能有一件事】
- 先用一句话写清"本章主线"（格式：主线：xxx），后面每个场次都必须推进这一件事。
- **场次数量 12-18 个**，每场 3-6 秒，每场只做一个动作。
  参考书一章是 55-68 段小节拍（每段 45-60 字），所以场次要细，不要把一整场压成一段。
- 不要在一章里同时写"旧窑""缺口碗""货郎""买釉""拜师"这种五件事；
  一章只推进一件事，其余的留到后面章节。
- 不要在正文里引入与主线无关的新人物、新地点、新道具、新规矩。新概念一章最多一个。
- 配角是来"切一刀"的：来了说一句关键的话就走，不要展开他的身世、背景和内心。
- 用时间跳跃推进："第二天傍晚""夜里""第三天清晨"，不要把每一刻都写出来。

【场次计划格式】
主线：一句话写清本章唯一的一件事
目标总时长：X秒
场次1
0.000–6.000秒
场景与时间：（古风场景，写到材质/层次/光源/氛围/规模感）
出场人物：
△（一个主要动作 + 一个信息变化 + 一个清晰结束状态）
角色名：（完整台词，18 字以上）

要求：
- 场次时间首尾相接，最后一个结束正好等于 X 秒
- 每场 3–6 秒，最多 15 秒；全章 12-18 个场次
- 每场只承担一个主要动作
- 台词字数 ≤ 该场秒数 × 4
- 每场结尾留一个未兑现的动作或没问出口的话
- 不要出现"爽点:"「伏笔:」这类标注
"""

CARD_RULES = """
【只输出角色意图卡，不要重写计划，不要写场次，不要写正文】
每张卡一个"场次N / 角色名"，卡片字段如下：

场次1 / 林渺
要什么：此刻想达成的一件事
知道什么：此刻掌握的信息（读者可能知道得更多）
情绪：一到两个词（写"压着火"，不写"很愤怒"）
怎么开口：说话方式（长短/省略/反问/不接话/先问后答）
潜台词：这句话真正想让对方听懂的，和字面不同

角色多就多写几张，一张都不要省。
"""


NEUTRAL_SYS = ("你是资深中文网文策划。只按用户给的格式输出，不加解释、不加标题、"
               "不重复用户给的内容、不使用插件式的固定前言。")


def do_plan(book, chapter, source, duration, ctx):
    p = ensure(book)
    src = read(source)
    user = ("为第%d章写场次计划。目标总时长 %d 秒。" % (chapter, duration) + NL + NL + src + NL + NL + PLANNER_RULES)
    user = ctx + NL + NL + user
    out = gm.ai_call(NEUTRAL_SYS, user, max_tokens=5000)
    fp = os.path.join(p["plan"], "第%02d章_场次计划.md" % chapter)
    io.open(fp, "w", encoding="utf-8").write(out)
    print("[plan] 已写", fp)
    return fp


PROSE_SYS = """你是中文网文作者，写的是能让人连着读下去的长篇连载。

输出格式：
- 第一行是章节标题，形如「第3章 没风」，不要加 # 或任何 markdown 记号
- **一章只写一件事**。开头三句之内就要让读者知道这一章在干什么；
  不要在章里另起炉灶开新的话题、新的人物或新的背景介绍
- **配角来一刀就走**：配角说一句话或做一个动作就退场，不要写他的身世、来历、心理
- **用时间跳跃推进**，不要流水账式地把每一刻都写出来
- 不要在正文里解释设定，设定要靠动作和对话带出来
- 之后直接进正文，不要出现"场次""时间轴""出场人物"这类字段名
- 每一段开头两个全角空格，段与段之间**只用一个换行**，不要空行

节奏（照下面的示范写，这是最关键的部分）：
- 段落要有长短变化：大部分段落 45-55 字，但每三段里要有一段 70-120 字的场景铺陈。
  不能每段都一样长
- **每个场次至少写 3 段**：一段铺场面，一段动作，一段对白或余味。
  不要一个动作写一段就跳到下一个场次
- 句子也要有长短变化：大部分句子 28-32 字，但每五句里要有一两句 15 字以下的短句，
  短句单独成段，用来砸重音
- **对白段只占三成左右**，其余是叙述。一句对白后面必须跟一到两段叙述承接，
  不要连着三句对白往下写
- **叙述段必须改变一个状态**，不能只是"他做了什么动作"就结束。每一段叙述至少要让
  下面一样发生变化：物理状态（泡破了、柴少了、灰被烧黑了、手上沾了灰）、
  时间（天黑了、两天后）、空间（走到坡底、进了灶屋）、认知（他忽然想明白一件事）、
  别人的状态（他爹停下了手）。动作本身不是终点，**动作造成的变化才是**。
- **禁止无信息的动作循环**：不许写"他放下X""他又捡起X""他拍了拍手上的灰"
  这种来回重复的小动作，写了就是废话。
- **相邻两段不许重复同一个动作**。
- 段落里要有具体的东西、材质、光线、动作、声音，不能只写情绪
- **对白要短，要碎**（这是《仙逆》的对白方式，最容易做错的地方）：
  - **对白要长短混合，不是全都短**。参照书：37% 在 10 字以内（反问、命令、感叹），
    38% 超过 25 字（角色把一件完整的事说清楚）。你要的是这个比例，不要一律压短。
  - 台词中位数控制在 16-20 字
  - 一句台词只给一截信息，**不许把事情、理由、态度、铺垫一次说完**
  - 删掉解释性成分（"是因为…""我记在墙上""我这么做是为了…"）
  - 允许省略和半句（"无缘，无缘啊……""问。""你困了。"）
  - 不要让角色替叙述者解释自己的心理
  - 台词必须符合意图卡里的语气和潜台词，但语气靠用词，不靠长句

节奏示范（照这个感觉写）：

　　他蹲下去，手背贴住窑壁。一息，两息，三息。壁里还留着余温，顺着指节上的旧烫疤往骨头里钻，钻到一半停住了，像有人隔着墙按住他的手。

　　他把手收回来。

　　窑口那行木炭账被露水洇过一遍，边角发毛，"釉无"两个字最重，已经糊成一团。

　　"这窑还能烧。"他对着空窑说，声音不大，尾音被窑洞吞了半截，"柴十一斤够六天，泥半筐够二十七件坯，缺的只有釉。"

　　他说完自己愣住，像是被"只有"两个字硌了牙。半筐泥靠墙立着，泥面干裂成龟背纹，缝里能塞进一根指头。

其他：
- 情绪靠动作和物件传达，不直接写"他很难过"。
  **参考书的做法：心理直述只用来写配角，主角的情绪一律用动作带过。**
- 全章要有 1-2 段 100 字以上的场景铺陈
- **全章段数要写够**：目标 3000 字左右 = 55 段左右（每段 45-60 字）。
  参考书一章就是 55-68 段，不要只写 30 多段就收尾
- 全章总字数 3050 字上下，绝对不要超过 3300 字
- 章末落在未兑现的动作或没问出口的话上
- 只写正文，不要任何解释或标注。"""

def do_cards(book, chapter, plan_path, ctx):
    p = paths(book)
    plan = read(plan_path)
    out = gm.ai_call(NEUTRAL_SYS,
                     "下面这份场次计划已经定稿，不要改动它。请为其中每一个场次、每一个出场角色"
                     "各写一张意图卡。" + NL + NL + plan + NL + NL + CARD_RULES,
                     max_tokens=4000)
    fp = os.path.join(p["plan"], "第%02d章_角色意图卡.md" % chapter)
    io.open(fp, "w", encoding="utf-8").write(out)
    print("[cards] 已写", fp)
    return fp


def _fix_title(text, chapter, title):
    """强制首行为「第N章 标题」。

    模型经常从上下文（台账进度表、伏笔表）里抓错标题，所以这一步必须确定性地做。
    """
    want = "第%d章 %s" % (chapter, title)
    lines = text.split(NL)
    for i, l in enumerate(lines[:4]):
        t = l.strip()
        if not t:
            continue
        if re.match(r"^#{0,3}\s*第[一二三四五六七八九十百千零0-9\d]+章", t):
            lines[i] = want
            return NL.join(lines)
        break
    return want + NL + text


def _deviation(fp, raw_len, book=None):
    """所有硬指标的归一化偏离度，越小越好（用来在多轮里选最好的一稿）。"""
    total = 0.0
    for name, lo, hi in rc.load_bands(book):
        v = fp.get(name)
        if v is None:
            continue
        span = max(1.0, hi - lo)
        if v < lo:
            total += (lo - v) / span
        elif v > hi:
            total += (v - hi) / span
    lo = hi = None
    for name, a, b in rc.load_bands(book):
        if name == "单章总字符":
            lo, hi = a, b
    if lo is None:
        lo, hi = 2731, 3265
    span = max(1.0, hi - lo)
    total += abs(raw_len - (lo + hi) / 2.0) / span
    return total


def build_feedback(fp, issues, raw_len, sm=None):
    """把不达标的项翻译成给 Writer 的具体指令（自动重试的关键）。

    fp 是 style_check 的指纹，sm 是 style_model 的文体模型结果（动作/比喻/连接词等）。
    """
    out = []
    g = lambda k: fp.get(k, 0)
    if sm is None:
        sm = {}

    def s2(k, default=0.0):
        v = sm.get(k)
        return v if isinstance(v, (int, float)) else default
    if "平均段长" in str(issues) or g("平均段长") > 60:
        out.append("你的段落太长（平均 %.1f 字），每段控制在 45-59 字，"
                   "把一个长段拆成两段，每段都要有完整的信息" % g("平均段长"))
    if g("平均段长") < 44:
        out.append("你的段落太碎（平均 %.1f 字），把相邻的两三段叙述合成一段" % g("平均段长"))
    if g("台词均字") < 28:
        out.append("你的台词太短（平均 %.1f 字），每句台词要写成完整的一句话，"
                   "带上动作、语气和具体内容，至少 28 字" % g("台词均字"))
    if s2("动作动词") > 11:
        out.append("动作动词太多（每千字 %.1f 个，仙逆 6.2）。一句话只做一个动作，"
                   "不要把一个动作拆成三段写；写完这个动作就落到它造成的变化上。"
                   % s2("动作动词"))
    if s2("比喻") > 2.6:
        out.append("比喻太多（每千字 %.1f 个，仙逆 1.6）。全章最多留两三个比喻，"
                   "其余地方用平白的话写。" % s2("比喻"))
    if s2("叙述具体物/段") > 1.0:
        out.append("叙述段里堆的具体物太多（每段 %.2f 个，仙逆 0.38）。"
                   "一段里点两三个物件就够，其余交给动作和变化。"
                   % s2("叙述具体物/段"))
    if s2("身体部位") > 20:
        out.append("身体部位词太多（每千字 %.1f 个，仙逆 12.6）。"
                   "别反复点手、肩膀、指节；身体只留一处最关键的。" % s2("身体部位"))
    if s2("连接词") > 0 and s2("连接词") < 6:
        out.append("段落之间缺逻辑连接（每千字 %.1f 个连接词，仙逆 9.2）。"
                   "用「可/但/只是/于是/然而/所以」把因果递进挑明，"
                   "别让段落只是并排摆着。" % s2("连接词"))
    if s2("对白叙述交替%") > 40:
        out.append("叙述和对白切得太碎（交替率 %.0f%%，仙逆 31%%）。"
                   "写成三到五段叙述，再来一句对白，再接三到五段叙述。"
                   % s2("对白叙述交替%"))
    if g("长段率(>100)") < 3:
        out.append("没有长段（现在 %.1f%%，要 3%%-17%%）。每三段里必须有一段 70-120 字的场景铺陈："
                   "把两个相邻的叙述段并成一段，中间不停，在里面加一层"
                   "材质、光线、声音、远处景物的细节" % g("长段率(>100)"))
    if g("对白段率") > 52:
        out.append("对白太多（占 %.1f%% 的段落），把一半以上的台词改成叙述，"
                   "用动作和物件把说话的内容演出来" % g("对白段率"))
    if g("对白段率") < 27:
        out.append("对白太少（占 %.1f%%），该说话的地方要说出声来" % g("对白段率"))
    if g("短句率(<15)") > 32:
        out.append("短句太多（%.1f%%），把相邻的短句用逗号连成长句" % g("短句率(<15)"))
    elif g("短句率(<15)") < 15:
        out.append("几乎没有短句（%.1f%%，要 16%%-28%%）。具体做法："
                   "每三段里挑出一段，把它的最后一句改成一个 15 字以下的短句，"
                   "单独成段，用来砸重音。例如把「他伸手去够，手伸到一半又停了。」"
                   "改成「他伸手去够。」「手伸到一半，又停了。」这种；"
                   "或者在叙述段末尾单独加一句「他没答。」「不试了。」"
                   % g("短句率(<15)"))
    if g("平均段长") < 45:
        out.append("段落偏短（平均 %.1f 字，目标 45-60），把叙述段写厚一点："
                   "多加一层具体的东西、材质、光线、声音的细节" % g("平均段长"))
    if 43 <= g("平均段长") < 45:
        out.append("段长 %.1f 字，再把相邻两段并一点点，凑到 48-55 字" % g("平均段长"))
    if g("平均段长") > 61 and g("平均句长") > 33:
        out.append("你的句子太长了（平均 %.1f 字）导致段也长。句子要压到 26-32 字，"
                   "每段只写 1.5 到 2 句" % g("平均句长"))
    if g("平均句长") >= 26 and g("平均段长") < 45:
        out.append("句子长度对了，但每段只写了一句，所以段太短。每段写 2 句，"
                   "段长自然就到 52-60 字了")
    if g("对白段率") > 51:
        out.append("对白段占 %.1f%%，再把一两句台词改成叙述——说话的内容可以用动作演出来"
                   % g("对白段率"))
    if g("长句率(>30)") < 31:
        out.append("长句太少（%.1f%%），用逗号把两三个分句串成一句 30 字以上的话" % g("长句率(>30)"))
    if g("平均句长") > 34:
        out.append("句子太长了（平均 %.1f 字），控制在 26-32 字；"
                   "一句话讲一件事，别把所有细节塞进一句" % g("平均句长"))
    elif g("平均句长") < 26:
        out.append("你的句子太短（平均 %.1f 字，要 26-32 字）。"
                   "用逗号把两三个分句串成一句，不要用句号断开。"
                   "照这个例子写：「壁里还留着余温，顺着指节上的旧烫疤往骨头里钻，"
                   "钻到一半停住了，像有人隔着墙按住他的手。」——这样一句就四十多字。"
                   "一段写成一到两句，不要一句一段" % g("平均句长"))
    if raw_len > 3300:
        cut = int(round((raw_len - 3050) * 100.0 / raw_len))
        out.append("全章 %d 字，超出目标约 %d%%，必须删到 3050 字上下。"
                   "删的时候只删这些：重复的形容词、连着用的比喻、解释人物心情的句子、"
                   "同一件事的第二遍描写、重复交代已经说过的背景。"
                   "所有台词、关键动作、情节节点一个都不能删。" % (raw_len, cut))
    elif raw_len < 2730:
        out.append("全章 %d 字，太少，补到 3050 字上下（补场景、材质、光线、动作细节，"
                   "不要注水，不要重复已有的信息）" % raw_len)
    if not out:
        out.append("把上面的要求再严格执行一遍，注意每段的字数和对白的完整度。")
    # 一次只给最严重的两条：给太多模型会顾此失彼，反而横跳
    out = out[:2]
    return (NL + "**这两轮只改下面两件事，其他方面保持原样。**" + NL
            + NL.join("- " + x for x in out))


def do_write(book, chapter, plan_path, card_path, title, ctx, rounds=4):
    p = paths(book)
    plan = read(plan_path)
    cards = read(card_path)
    samples = ""
    sp = os.path.join(book, "00_素材", "文风示范_自写.md")
    if os.path.exists(sp):
        st = io.open(sp, encoding="utf-8").read()
        samples = (NL + NL + "【文风示范 — 下面是我按目标质感手写的几段，用来示范节奏，"
                   "不要抄内容，只学它的句子长度、段落密度和推进方式】" + NL + NL
                   + st[:4000] + NL)
    user = (ctx + NL + NL + plan + NL + NL + cards + NL + NL + samples + NL
            + "把上面的场次计划写成正文。硬指标（写完会被机器检查）：" + NL
            + "- 每个场次至少 3 段（一段铺场、一段动作、一段对白或余味）" + NL
            + "- 每段 45-59 字，不要超过 70 字" + NL
            + "- 对白段只占三成左右，一句对白后必须跟一到两段叙述" + NL
            + "- 叙述段必须改变一个状态（物理/时间/空间/认知/他人），"
                   "不能只写“他做了个动作”" + NL
            + "- 禁止“放下—又捡起—再放下”这种无信息动作循环" + NL
            + "- 相邻两段不许重复同一个动作" + NL
            + "- 台词长短混合：中位 16-20 字，约三分之一在 10 字以内，"
                   "但也要有几处 30-50 字的长句把一件事说透，不要一律压短" + NL
            + "- 句子 28-42 字，每五句里有一两句 15 字以下的短句做节奏点" + NL
            + "- 全章 1-2 段 100 字以上的场景铺陈" + NL
            + "- 全章要写 55 段左右（每段 45-60 字），总字数 3000 字上下，"
                   "绝对不要超过 3300 字。"
                   "写之前先想好哪些细节可以省，不要写完再删" + NL
            + "- 句子平均 26-33 字，三成以上超过 30 字；把短句用逗号连起来" + NL
            + "- 每三段里有一段超过 60 字" + NL
            + "要求：" + NL
            + "把上面的场次计划写成正文。要求：\n"
            + "1. 严格照计划的时间和场次顺序，不要自行增删场次\n"
            + "2. 每段开头两个全角空格，段与段之间**只用一个换行**，不要空行\n"
            + "3. 对白用中文引号；每个角色说话要符合他意图卡里的语气和潜台词\n"
            + "4. 每场补上具体的物、材质、光线、动作细节\n"
            + "5. 章末落在未兑现的动作或没问出口的话上\n"
            + "6. 只输出正文，第一行是「第%d章 %s」" % (chapter, title))
    fp = os.path.join(p["text"], "第%02d章_%s.md" % (chapter, title))
    feedback = ""
    best = None
    for rnd in range(1, rounds + 1):
        out = gm.ai_call(PROSE_SYS, user + feedback, max_tokens=8000)
        out = _fix_title(out, chapter, title)
        io.open(fp, "w", encoding="utf-8").write(out)
        fpi, issues, notes = rc.check(fp, None, p["ledger"], book)
        sm = smod.analyze(out)
        grade = rc.grade(issues, notes, fpi)[0]
        print("[write] 第%d轮 评级 %s | 段长 %.1f 句长 %.1f 台词均 %.1f 对白 %.1f%% 字数 %d"
              % (rnd, grade, fpi["平均段长"], fpi["平均句长"], fpi["台词均字"],
                 fpi["对白段率"], len(out)))
        if grade in ("S", "A"):
            print("[write] 已写", fp)
            return fp
        dev = _deviation(fpi, len(out), book)
        if best is None or dev < best[3]:
            best = (out, issues, fpi, dev)
        feedback = (NL + NL + "【上一稿的实测问题，必须逐条改掉】" + NL
                    + build_feedback(fpi, issues, len(out), sm) + NL)
    if best:
        io.open(fp, "w", encoding="utf-8").write(best[0])
        print("[write] %d 轮未达标，保留最好的一稿" % rounds)
    print("[write] 已写", fp)
    return fp


def do_review(book, chapter, text_path, prev_path):
    p = paths(book)
    fp, issues, notes = rc.check(text_path, prev_path, p["ledger"], book)
    L = ["# 第%02d章 审稿报告" % chapter, ""]
    L.append("- 评级：**%s**" % rc.grade(issues, notes, fp)[0])
    L.append("- 字数 %d | 句长 %.1f | 段长 %.1f | 台词均 %.1f | 对白 %.1f%% | 长段 %.1f%% | 水词 %d"
             % (len(read(text_path)), fp["平均句长"], fp["平均段长"], fp["台词均字"],
                fp["对白段率"], fp["长段率(>100)"], fp["水词"]))
    L.append("")
    if notes:
        L.append("## 提示")
        L += ["- " + n for n in notes]
        L.append("")
    if issues:
        L.append("## 必须改")
        L += ["- " + i for i in issues]
    else:
        L.append("## 结论\n全部通过，可进下一章。")
    rp = os.path.join(p["review"], "第%02d章_审稿.md" % chapter)
    io.open(rp, "w", encoding="utf-8").write(NL.join(L))
    for i in issues:
        print("  !", i)
    print("[review] 已写", rp, "| 评级", rc.grade(issues, notes, fp)[0])
    return rp


def do_record(book, chapter, text_path, title):
    p = paths(book)
    led = p["ledger"]
    if not os.path.exists(led):
        print("[record] 没有台账，跳过")
        return
    s = read(led)
    n = len(read(text_path))
    row = "| %02d | %s | %d |  | ✅ |  |" % (chapter, title, n)
    s = re.sub(r"(?m)^\| 0?1 \|.*$", "", s, count=0)
    if "| 章 | 标题 | 字数 | 评级 | 状态 | 一句话 |" in s:
        parts = s.split("| 章 | 标题 | 字数 | 评级 | 状态 | 一句话 |")
        s = (parts[0] + "| 章 | 标题 | 字数 | 评级 | 状态 | 一句话 |" + parts[1]
             + NL + row + NL + parts[2])
    io.open(led, "w", encoding="utf-8").write(s)
    print("[record] 台账已回写")


def main():
    args = sys.argv[1:]
    book = args[0]
    chapter = 0
    source = None
    title = ""
    duration = 75
    only = None
    check_only = False
    for i, a in enumerate(args):
        if a == "--chapter":
            chapter = int(args[i + 1])
        elif a == "--source":
            source = args[i + 1]
        elif a == "--title":
            title = args[i + 1]
        elif a == "--duration":
            duration = int(args[i + 1])
        elif a == "--only":
            only = args[i + 1]
        elif a == "--check-only":
            check_only = True
    p = ensure(book)
    ledger = read(p["ledger"])
    # 进度表会让模型抓错标题，从上下文里剔掉
    ledger = re.sub(r"(?ms)^\| 章 \| 标题 \| 字数 \| 评级 \| 状态 \| 一句话 \|.*?" + NL + NL, "", ledger)
    ctx = (read(p["guide"]) + NL + NL + "【本书台账】" + NL + ledger)[:12000]

    if check_only:
        for fn in sorted(os.listdir(p["text"])):
            if fn.startswith("第%02d章" % chapter):
                do_review(book, chapter, os.path.join(p["text"], fn), None)
        return 0

    steps = [only] if only else ["plan", "cards", "write", "review"]
    plan_path = os.path.join(p["plan"], "第%02d章_场次计划.md" % chapter)
    card_path = os.path.join(p["plan"], "第%02d章_角色意图卡.md" % chapter)
    text_path = None
    for fn in sorted(os.listdir(p["text"])):
        if fn.startswith("第%02d章" % chapter):
            text_path = os.path.join(p["text"], fn)
    if "plan" in steps:
        plan_path = do_plan(book, chapter, source, duration, ctx)
        print("[plan] 目标时长", duration, "秒")
    if "cards" in steps:
        card_path = do_cards(book, chapter, plan_path, ctx)
    if "write" in steps:
        text_path = do_write(book, chapter, plan_path, card_path, title, ctx)
    if "review" in steps and text_path:
        do_review(book, chapter, text_path, None)
        do_record(book, chapter, text_path, title)
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.exit(main())

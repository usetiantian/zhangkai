# -*- coding: utf-8 -*-
import sys, json
sys.path.insert(0, "D:/ComfyUI_windows_portable/ComfyUI/output/问剑长生_漫剧/03_分镜脚本")
import llm_storyboard as L
from produce_ep import read_chapter
ch, fn = read_chapter(1)

def trial(label, msgs, mt=8000):
    try:
        raw = L.call_llm(msgs, max_tokens=mt)
        c = L._clean_json(raw)
        ok = c.startswith("{")
        print("%-18s rawlen=%-6d json=%s" % (label, len(raw), ok))
        if ok:
            d = json.loads(c)
            print("   title=%s shots=%d chars=%d" % (d.get("title"), len(d.get("shots",[])), len(d.get("characters",[]))))
            print("   shot1:", json.dumps(d["shots"][0], ensure_ascii=False)[:300])
            return True
    except Exception as e:
        print("%-18s ERR %s" % (label, e))
    return False

S2 = ("你是国漫分镜师。把小说章节改成 4-6 镜头的漫剧分镜 JSON。"
      "只输出 JSON 对象，首字符必须是 {。\n"
      "JSON: {\"title\":\"标题\",\"global_prompt\":\"氛围描述\","
      "\"shots\":[{\"shot_size\":\"景别\",\"visual\":\"画面描述\",\"camera\":\"运镜\","
      "\"ambience\":\"音效\",\"dialogue\":[{\"role\":\"角色\",\"text\":\"台词\",\"emotion\":\"情绪\"}]}],"
      "\"characters\":[{\"name\":\"角色名\",\"role\":\"身份\",\"appearance\":\"外貌\",\"shot\":镜号}]}\n"
      "景别只能取: 大全景 全景 中景 中近景 近景 特写 大特写 中近景·仰角 中景·俯角\n"
      "visual: 人物→动作→场景→细节；一镜只写一个动作\n"
      "camera: 必须含推/拉/摇/移/跟/升/降/环绕\n"
      "ambience: 3-5个音效用、分隔\n"
      "dialogue: 0-3句，每句不超过25字\n"
      "风格: 中国仙侠3D国漫动画，赛璐璐着色，强边缘光")

trial("A-prefill-full", [{"role":"system","content":L.SYSTEM},
                         {"role":"user","content":"第 1 章正文：\n\n"+ch},
                         {"role":"assistant","content":"{"}])
trial("B-prefill-simple", [{"role":"system","content":S2},
                           {"role":"user","content":"第 1 章正文：\n\n"+ch},
                           {"role":"assistant","content":"{"}])

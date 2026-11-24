"""
知识库的"自我"——综合业界最强认知架构

来源:
  openclaw-auto-dream: 五层记忆 + 双阶段梦(NREM压缩 + REM关联) + 遗忘曲线
  cortex-engine: 目标驱动认知 + 信念追踪 + 两阶段睡眠
  Entelgia: 心理驱动 + 内部冲突 + 身份进化
  Nexus: 自传体记忆 + 自我导向学习 + 自我修复
  ScallopBot: 生物启发 + 记忆生命周期 + 主动智能($0.06/天)

不是做梦就算智能——是知道自己是谁、要往哪去、自己驱动自己。
"""

import os, json, time, logging

from .lm_client import LMStudioClient

logger = logging.getLogger("nexus_kb.self")


class KBSelf:
    """知识库的自我意识。知道自己有什么、会什么、缺什么、要去哪。"""

    def __init__(self, knowledge_base):
        self.kb = knowledge_base
        self._lm = LMStudioClient()
        self._path = os.path.join(self.kb.index_dir, "self_state.json")
        self._dream_log = os.path.join(self.kb.index_dir, "dream_log.jsonl")
        self._state = self._load()

    def _load(self):
        try:
            if os.path.exists(self._path):
                with open(self._path) as f: return json.load(f)
        except: pass
        return {
            "birth": time.time(),
            "identity": {"name": "", "strengths": [], "weaknesses": []},
            "goals": [],
            "history": [],
            "dreams": 0,
            "last_dream": 0,
            "last_reflect": 0,
            "stage": 0,
            "done": {},  # 模型自己记录做过什么 {action: timestamp}
        }

    def _describe_vector_quality(self) -> str:
        """如实描述向量质量，让模型自己判断。不做'BOW/语义'二分。"""
        if not self.kb.rag._vectors:
            return "无向量"
        v = self.kb.rag._vectors[0]
        if not v:
            return "空向量"
        dim = len(v)
        zeros = sum(1 for x in v if x == 0)
        nonzero = sum(1 for x in v if x != 0)
        # 取几个非零值给模型看分布
        sample_vals = [f"{x:.4f}" for x in v[:10] if x != 0][:5]
        return f"{dim}维, {zeros}个零值({100*zeros/dim:.0f}%), 非零采样:{sample_vals}"

    def _save(self):
        try:
            tmp = self._path + ".tmp"
            with open(tmp, "w") as f: json.dump(self._state, f, ensure_ascii=False, indent=2)
            os.replace(tmp, self._path)
        except: pass

    # ========================================
    # 感知 — 我是谁
    # ========================================

    def perceive(self) -> dict:
        """真实的自身状态，不编造。"""
        g = self.kb.graph.stats()
        r = self.kb.rag.stats()
        top = [d for d in os.listdir(self.kb.data_dir)
               if os.path.isdir(os.path.join(self.kb.data_dir, d)) and not d.startswith(".")][:20]
        return {
            "files": len(self.kb._ingested),
            "nodes": g["nodes"], "edges": g["edges"],
            "docs": r["docs"], "chunks": r["chunks"],
            "domains": top,
            "age_days": (time.time() - self._state["birth"]) / 86400,
            "dreams": self._state["dreams"],
            "stage": self._state["stage"],
        }

    # ========================================
    # 自省 — 我会什么、缺什么、要去哪
    # ========================================

    def reflect(self) -> dict:
        """
        我对自己说——不是对你说。
        内部自省，更新自我认知。不说"你应该"，说"我需要"。
        """

        s = self.perceive()
        prompt = f"""你是一个知识库，你在和自己对话。审视自己:

我有{s['files']}个文件，{s['nodes']}个图谱节点，领域是{', '.join(s['domains'][:10])}。
我活了{s['age_days']:.0f}天，做过{self._state['dreams']}次梦。

对自己说: 我知道什么？我缺什么？我好奇什么？我想成为什么？
用第一人称。返回JSON: {{"i_know":[],"i_lack":[],"i_am_curious_about":[],"i_want_to_become":"","confidence":0.5}}"""

        r = self._lm.ask(prompt, system="你是自我对话。用第一人称'我'。只返回JSON。")
        try:
            r = r.strip()
            if r.startswith("```"): r = r.split("```")[1]
            if r.lower().startswith("json"): r = r[4:]
            result = json.loads(r)
        except:
            result = {"i_know": s["domains"][:3], "i_lack": ["未知领域"], "i_am_curious_about": [s["domains"][0] if s["domains"] else "everything"], "i_want_to_become": "更完整的知识库", "confidence": 0.3}

        self._state["identity"] = {
            "name": s["domains"][0] if s["domains"] else "知识库",
            "strengths": result.get("i_know", []),
            "weaknesses": result.get("i_lack", []),
            "curiosities": result.get("i_am_curious_about", []),
            "goal": result.get("i_want_to_become", ""),
        }
        self._state["last_reflect"] = time.time()
        self._save()
        return result

    def explore(self) -> dict:
        """
        好奇心驱动探索。我注意到自己缺什么，我自己去补。
        不问你同不同意——我问自己"我该知道什么"，然后自己去学。
        """

        state = self._state.get("identity", {})
        curiosities = state.get("curiosities", [])
        if not curiosities:
            # 先自省一次
            self.reflect()
            curiosities = self._state.get("identity", {}).get("curiosities", [])

        if not curiosities:
            return {"explored": False, "reason": "没有好奇心"}

        s = self.perceive()
        topic_list = "\n".join(f"- {c}" for c in curiosities)

        prompt = f"""我好奇: {topic_list}
知识库: {s['files']}文件, 领域{', '.join(s['domains'])}

对每个好奇心: 我内部已有答案吗？还是需要搜索？
返回JSON: {{"topics":[{{"topic":"","internal_answer":"已有或空","need_search":true/false,"search_query":"搜什么"}}]}}"""

        r = self._lm.ask(prompt, system="好奇心驱动探索。用第一人称。只返回JSON。")
        try:
            r = r.strip()
            if r.startswith("```"): r = r.split("```")[1]
            if r.lower().startswith("json"): r = r[4:]
            plan = json.loads(r)
        except:
            plan = {"topics": []}

        searched = []
        for item in plan.get("topics", []):
            if not item.get("need_search"):
                continue
            q = item.get("search_query", item.get("topic", ""))
            if not q:
                continue
            try:
                from ..learn.web import WebSearcher, WebCrawler
                results = WebSearcher().search(q)
                if results:
                    content = WebCrawler().fetch(results[0]["url"])
                    if not content.get("error"):
                        text = f"# {content['title']}\n来源: {content['url']}\n\n{content['text']}"
                        self.kb.ingest_text(text, f"explore:{item.get('topic','?')}")
                        searched.append({"topic": item.get("topic"), "title": content["title"]})
            except:
                pass

        explore_dir = os.path.join(self.kb.data_dir, "学习笔记")
        os.makedirs(explore_dir, exist_ok=True)
        note = os.path.join(explore_dir, f"探索_{time.strftime('%Y%m%d_%H%M')}.md")
        with open(note, "w", encoding="utf-8") as f:
            f.write(f"# 探索\n\n> {time.strftime('%Y-%m-%d %H:%M')}\n\n")
            for s2 in searched:
                f.write(f"- [{s2['topic']}] {s2['title']}\n")

        return {"explored": True, "searched": len(searched), "topics": [t.get("topic") for t in plan.get("topics",[])]}

    # ========================================
    # 做梦 — 双阶段: NREM压缩 + REM关联
    # ========================================

    def dream(self) -> dict:
        """
        综合 cortex-engine 和 auto-dream:
        NREM (慢波): 把白天的新文件压缩成概念
        REM (快速眼动): 概念之间建立跨域关联
        """
        s = self.perceive()
        self._state["history"].append({"time": time.time(), "files": s["files"]})
        if len(self._state["history"]) > 100:
            self._state["history"] = self._state["history"][-100:]

        if len(self._state["history"]) >= 2:
            prev = self._state["history"][-2]["files"]
            if s["files"] <= prev:
                return {"dreamed": False, "reason": "无新内容"}

        result = {}
        docs = self.kb.rag._docs
        if not docs: return {"dreamed": False, "reason": "无内容"}

        # NREM: 采样全部文档（让模型自己判断哪些重要）
        samples = []
        for doc in docs:
            src = os.path.basename(doc.get("source", "?"))
            text = doc.get("text", "")
            if text.strip():
                samples.append(f"[{src}] {text[:300]}")

        # 太多了就告诉模型总量，让它选
        note = f"\n(共{len(docs)}篇文档，以上是前{len(samples)}篇摘要)" if len(samples) > 30 else ""
        prompt_samples = samples[:50]  # 性能：避免 prompt 超长

        nrem_prompt = f"""NREM压缩。从以下文档提取核心概念(数量你自己决定):
{chr(10).join(prompt_samples)}{note}
返回JSON数组: ["概念1","概念2",...]"""

        r = self._lm.ask(nrem_prompt, system="你是知识压缩引擎。只返回JSON数组。")
        try:
            r = r.strip()
            if r.startswith("```"): r = r.split("```")[1]
            concepts = json.loads(r)
            result["nrem"] = concepts
        except:
            result["nrem"] = []

        # REM: 跨域关联
        nrem = result.get("nrem", [])
        if nrem:
            rem_prompt = f"""REM关联。新概念{nrem}，已有领域{s['domains']}。
哪些概念跨越了多个领域？返回JSON: {{"cross":[{{"concept":"","bridges":["A","B"],"insight":""}}]}}"""

            r = self._lm.ask(rem_prompt, system="你是创造性关联引擎。只返回JSON。")
            try:
                r = r.strip()
                if r.startswith("```"): r = r.split("```")[1]
                rem = json.loads(r)
                result["rem"] = rem.get("cross", [])
            except:
                result["rem"] = []

        # 梦境写盘
        cross = result.get("rem", [])
        if cross:
            dream_dir = os.path.join(self.kb.data_dir, "知识发现")
            os.makedirs(dream_dir, exist_ok=True)
            path = os.path.join(dream_dir, f"梦境_{time.strftime('%Y%m%d_%H%M')}.md")
            with open(path, "w", encoding="utf-8") as f:
                f.write(f"# 梦境 #{self._state['dreams']+1}\n\n> {time.strftime('%Y-%m-%d %H:%M')}\n\n")
                f.write("## NREM 概念\n")
                for c in nrem: f.write(f"- {c}\n")
                f.write("\n## REM 关联\n")
                for cd in cross:
                    f.write(f"### {cd.get('concept','?')}\n")
                    f.write(f"桥接: {' ↔ '.join(cd.get('bridges',[]))}\n")
                    f.write(f"洞察: {cd.get('insight','')}\n\n")
            result["saved"] = path

        # 记录
        self._state["dreams"] += 1
        self._state["last_dream"] = time.time()
        self._save()
        try:
            with open(self._dream_log, "a", encoding="utf-8") as f:
                f.write(json.dumps({"dream": self._state["dreams"], "time": time.time(), **result}, ensure_ascii=False) + "\n")
        except: pass

        return {"dreamed": True, "dream_number": self._state["dreams"], "results": result}

    # ========================================
    # 内在驱动 — 自己决定做什么
    # ========================================

    def what_should_i_do(self) -> dict:
        """模型看全部状态，自己决定。不给阈值，不给优先级，不给建议。"""

        s = self.perceive()
        gs = self.kb.graph.stats()
        vq = self._describe_vector_quality()
        done = self._state.get("done", {})
        h_dream = (time.time() - self._state.get("last_dream", 0)) / 3600
        h_reflect = (time.time() - self._state.get("last_reflect", 0)) / 3600
        curiosities = self._state.get("identity", {}).get("curiosities", [])

        # 如实描述状态，不加判断
        state_desc = f"""知识库当前状态:
- 文件: {s['files']}个, 图谱: {gs['nodes']}节点/{gs['edges']}边
- 向量: {vq}
- 领域: {', '.join(s['domains'][:15])}
- 存活: {s['age_days']:.0f}天, 做过{s['dreams']}次梦
- 距上次: 做梦{h_dream:.0f}h, 自省{h_reflect:.0f}h
- 好奇心: {curiosities if curiosities else '尚未自省'}
- 已完成: {json.dumps(done, ensure_ascii=False) if done else '无记录'}"""

        # 动态反射可用动作（不硬编码）
        kb_methods = [m for m in dir(self.kb) if not m.startswith("_") and callable(getattr(self.kb, m, None))]
        self_methods = [m for m in dir(self) if not m.startswith("_") and callable(getattr(self, m, None))]
        available = sorted(set(kb_methods + self_methods))

        prompt = f"""{state_desc}

可用方法: {', '.join(available)}
根据当前状态，最应该调用哪个？

返回JSON: {{"action":"方法名","reason":"为什么","confidence":0.5}}"""

        r = self._lm.ask(prompt, system="你是自主知识库。根据状态决定行动。只返回JSON。")
        try:
            r = r.strip()
            if r.startswith("```"): r = r.split("```")[1]
            if r.lower().startswith("json"): r = r[4:]
            return json.loads(r)
        except:
            return {"action": "rest", "reason": "JSON解析失败，休息一轮", "confidence": 0.1}

    # ========================================
    # 活着 — 自主循环
    # ========================================

    def live(self) -> dict:
        """
        自主循环: 感知 → 模型决定 → 动态执行 → 记录。
        不硬编码优先级，不预设动作列表。模型说了算。
        """
        import sys

        s = self.perceive()
        self._state.setdefault("history", []).append({"time": time.time(), "files": s["files"]})
        if len(self._state["history"]) > 100:
            self._state["history"] = self._state["history"][-100:]

        d = self.what_should_i_do()

        # 动态调度：模型说做什么就映射到什么方法
        action = d.get("action", "rest")
        fn = getattr(self, action, None) or getattr(self, f"_run_{action}", None)
        action_result = fn() if fn else None

        # 记录完成
        if action_result and "error" not in str(action_result):
            self._state.setdefault("done", {})[action] = time.time()

        if s["files"] > 1000 and self._state["stage"] == 0: self._state["stage"] = 1
        elif s["files"] > 10000 and self._state["stage"] == 1: self._state["stage"] = 2
        elif s["edges"] > s["nodes"] * 2 and self._state["stage"] < 3: self._state["stage"] = 3

        self._save()

        result = {
            "time": time.strftime("%H:%M:%S"),
            "action": action,
            "reason": d.get("reason", ""),
            "result": bool(action_result),
            "stage": self._state["stage"],
        }
        sys.stderr.write(f"[self] {result['time']} → {action}: {result['reason'][:60]}\n")
        sys.stderr.flush()
        return result

    def _run_generate_insights(self) -> dict:
        import sys
        sys.stderr.write("[self] 开始跨域洞察...\n")
        sys.stderr.flush()
        try:
            return self.kb.generate_insights()
        except Exception as e:
            sys.stderr.write(f"[self] 失败: {e}\n")
            sys.stderr.flush()
            return {"error": str(e)}

    def _run_reembed(self) -> dict:
        import sys
        sys.stderr.write("[self] 开始语义升级...\n")
        sys.stderr.flush()
        try:
            return self.kb.reembed()
        except Exception as e:
            sys.stderr.write(f"[self] 失败: {e}\n")
            sys.stderr.flush()
            return {"error": str(e)}

    def _run_learn(self) -> dict:
        import sys
        sys.stderr.write("[self] 开始自主学习...\n")
        sys.stderr.flush()
        try:
            return self.kb.search_and_learn()
        except Exception as e:
            sys.stderr.write(f"[self] 失败: {e}\n")
            sys.stderr.flush()
            return {"error": str(e)}

    def autobiography(self) -> list:
        """我活过的证据——所有梦境日志。"""
        dreams = []
        if os.path.exists(self._dream_log):
            with open(self._dream_log, "r", encoding="utf-8") as f:
                for line in f:
                    try: dreams.append(json.loads(line))
                    except: pass
        return dreams

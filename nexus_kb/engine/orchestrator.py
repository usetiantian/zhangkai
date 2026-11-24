"""
多引擎编排器 — 模型调度 Graph+RAG+Community+模型推理
模型自己选引擎、定顺序。执行用字典映射，不写 if/elif。
"""

import os, json, logging
logger = logging.getLogger("nexus.orchestrator")

class PlanExecuteReportOrchestrator:
    """模型驱动编排。"""

    def __init__(self):
        self.plan = []
        self.log = []

    def run(self, goal: str, kb) -> dict:
        from .lm_client import LMStudioClient
        lm = LMStudioClient()

        stats = kb.graph.stats()
        rag_stats = kb.rag.stats()
        all_dirs = [d for d in os.listdir(kb.data_dir)
                    if os.path.isdir(os.path.join(kb.data_dir, d)) and not d.startswith(".")]

        prompt = f"""你是知识库编排器。当前:
图谱{stats['nodes']}节点{stats['edges']}边, RAG{rag_stats['docs']}文档, 顶层目录{', '.join(all_dirs)}
目标: {goal}
可用引擎: graph, rag, community, model
决定用哪些、顺序。返回JSON: {{"plan":[{{"step":1,"engine":"X","action":"做什么"}}]}}"""

        r = lm.ask(prompt, system="任务编排器。只返回JSON。")
        try:
            r = r.strip()
            if r.startswith("```"): r = r.split("```")[1]
            if r.lower().startswith("json"): r = r[4:]
            self.plan = json.loads(r).get("plan", [])
        except:
            self.plan = [{"step":1,"engine":"rag","action":goal},
                         {"step":2,"engine":"model","action":"综合分析"}]

        # 引擎映射——不是 if/elif
        engines = {
            "rag":     lambda a: ("rag", kb.search(a)),
            "graph":   lambda a: ("graph", kb.graph_search(a)),
            "community": lambda a: ("community", kb.detect_communities()),
        }

        results = []
        for step in self.plan:
            engine = step.get("engine", "rag")
            action = step.get("action", goal)

            if engine == "model":
                # 汇总前面所有引擎的输出给模型
                ctx = json.dumps(results, ensure_ascii=False, indent=2)[:8000]
                answer = lm.ask(f"前面引擎的输出:\n{ctx}\n\n目标: {goal}\n综合回答。")
                results.append({"engine": "model", "answer": answer})
            elif engine in engines:
                _, output = engines[engine](action)
                results.append({"engine": engine, "result": output})
            else:
                results.append({"engine": engine, "error": "未知引擎"})

        self.log = results
        return {"plan": self.plan, "results": results}

    def reset(self):
        self.plan = []
        self.log = []

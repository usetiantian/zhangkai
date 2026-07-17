"""
自主任务引擎 — Nexus自己决定做什么、怎么做、做完汇报

借鉴CC的行为模式: Plan→Execute→Verify→Report
不是等用户下命令，是自己发现问题自己处理
"""
import time, logging
logger = logging.getLogger("nexus.autonomous")

class AutonomousAgent:
    """自主Agent——Nexus的主动行为引擎。"""

    def __init__(self):
        self.active_tasks = []     # 当前执行中的任务
        self.completed_tasks = []  # 已完成
        self.state = "idle"        # idle | planning | executing | reporting

    def scan_environment(self, nexus) -> list:
        """
        扫描环境——发现该做的事。
        借鉴CC的自主检查: 记忆有没有更新？昨天的问题修了没？
        """
        tasks = []

        # 检查RAG是否有未消化的文档
        rag_stats = nexus.rag.stats()
        if rag_stats.get("chunks", 0) > 50:
            tasks.append({
                "type": "digest",
                "title": f"消化{rag_stats['chunks']}条知识片段",
                "priority": 3,
            })

        # 检查知识图谱是否需要社区检测
        kg_stats = nexus.graph.stats()
        if kg_stats.get("nodes", 0) > 50 and kg_stats.get("communities", 0) == 0:
            tasks.append({
                "type": "community",
                "title": f"对{kg_stats['nodes']}个节点做社区检测",
                "priority": 2,
            })

        # 检查学习队列
        learner_stats = nexus.learner.stats()
        if learner_stats.get("queued", 0) > 0:
            tasks.append({
                "type": "learn",
                "title": f"处理{learner_stats['queued']}个学习任务",
                "priority": 4,
            })

        # 检查是否有用户长时间未活跃
        # (此处需要用户管理数据)

        return sorted(tasks, key=lambda x: x["priority"], reverse=True)

    def execute_task(self, nexus, task: dict) -> dict:
        """执行一个自主任务。"""
        self.state = "executing"
        task["started"] = time.time()

        try:
            if task["type"] == "community":
                from knowledge.community import CommunityDetector
                cd = CommunityDetector()
                comms = cd.detect(nexus.graph.nodes, nexus.graph.edges)
                result = f"检测到{len(comms)}个社区"

            elif task["type"] == "learn":
                results = nexus.learner.process(nexus.rag, nexus.graph)
                result = f"处理了{len(results)}个学习任务"

            elif task["type"] == "digest":
                result = f"RAG中有{nexus.rag.stats()['chunks']}条等待消化"

            else:
                result = f"未知任务类型: {task['type']}"

            task["result"] = result
            task["status"] = "done"
            self.completed_tasks.append(task)
            logger.info(f"Task done: {task['title']} → {result}")

        except Exception as e:
            task["status"] = "failed"
            task["error"] = str(e)
            logger.error(f"Task failed: {task['title']}: {e}")

        self.state = "idle"
        return task

    def tick(self, nexus) -> dict:
        """
        心跳——每隔一段时间自动运行。
        返回: {action, tasks_completed, suggestions}
        """
        tasks = self.scan_environment(nexus)
        completed = []

        for task in tasks[:3]:  # 每次最多3个
            result = self.execute_task(nexus, task)
            completed.append(result)

        return {
            "action": "tick_complete",
            "tasks_found": len(tasks),
            "tasks_completed": len(completed),
            "state": self.state,
        }

    def stats(self) -> dict:
        return {
            "active": len(self.active_tasks),
            "completed": len(self.completed_tasks),
            "state": self.state,
        }

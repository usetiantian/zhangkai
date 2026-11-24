"""Agent — v2.0 最终版: grok-build 完整 Python 实现 + KG + 经验 + 内置模型 + 外部搜索"""

import json
from dataclasses import dataclass, field
from coordinator.engine import think, is_model_ready
from coordinator.context import ContextBuilder
from coordinator.decision import parse as parse_decision
from memory.sessions import Session
from memory.tasks import task_summary_for_context


@dataclass
class Agent:
    """乾坤 Agent — 完整的自主生命体"""
    session: Session = field(default_factory=Session.create)
    persona_name: str = "default"

    _goal_tracker = None
    _subagent_coordinator = None
    _plan_tracker = None
    _curiosity = None
    _workspace = None
    _persona = None
    _doom_loop = None
    _feedback_mgr = None

    def __post_init__(self):
        self._init_persona()
        self._init_doom_loop()
        self._init_tools()
        self._init_workspace()
        self._register_workspace_tools()
        self._init_skills()
        self._init_plugins()
        self._init_curiosity()

    def _init_persona(self):
        from agent.persona import load_persona
        self._persona = load_persona(self.persona_name)

    def _init_doom_loop(self):
        from agent.doom_loop import DoomLoopDetector
        self._doom_loop = DoomLoopDetector()

    def _init_tools(self):
        from tools.search.engines import search_web
        from tools.fetch.router import fetch_url
        from tools.fetch.browser import fetch_with_browser
        from tools.crawl.crawler import crawl_site
        from tools.extract.structured import extract_page
        from tools.diff import check_diff
        from tools.notify import send as feishu_send
        from memory.tasks import create_task, list_tasks, update_task

        self.tools = {
            "search": {"func": search_web, "desc": "search internet"},
            "fetch": {"func": fetch_url, "desc": "fetch webpage"},
            "browser": {"func": fetch_with_browser, "desc": "browser render"},
            "crawl": {"func": crawl_site, "desc": "crawl site"},
            "extract": {"func": extract_page, "desc": "extract data"},
            "diff": {"func": check_diff, "desc": "check changes"},
            "notify": {"func": feishu_send, "desc": "push to feishu"},
            "create_task": {"func": create_task, "desc": "create task"},
            "list_tasks": {"func": lambda **kw: list_tasks(**kw), "desc": "list tasks"},
            "complete_task": {"func": lambda tid, **kw: update_task(tid, status='done'), "desc": "complete task"},
        }

    def _init_skills(self):
        from agent.skills import get_skill_registry
        self._skills = get_skill_registry()

    def _init_plugins(self):
        from agent.plugins.marketplace import get_marketplace
        self._marketplace = get_marketplace()
        plugin_tools = self._marketplace.load_tools()
        self.tools.update(plugin_tools)

    def _init_workspace(self):
        from workspace.workspace import Workspace
        self._workspace = Workspace()

    def _register_workspace_tools(self):
        ws = self._workspace
        if ws:
            self.tools.update({
                "read_file": {"func": ws.read, "desc": "read file"},
                "write_file": {"func": ws.write, "desc": "write file (auto backup)"},
                "list_dir": {"func": ws.list_dir, "desc": "list directory"},
                "undo_file": {"func": ws.undo_last, "desc": "undo last change"},
            })
            from workspace.sandbox import Sandbox, is_safe_code
            sb = Sandbox()
            def safe_run(code):
                check = is_safe_code(code)
                if not check["safe"]:
                    return {"ok": False, "error": "unsafe: " + str(check["warnings"])}
                return sb.run_python(code)
            self.tools["run_code"] = {"func": safe_run, "desc": "run python safely"}
            from workspace.rewind import FileRewind
            rw = FileRewind(ws.root)
            self.tools["rewind_file"] = {"func": rw.rewind_last, "desc": "rewind to previous version"}

    def _init_curiosity(self):
        from agent.curiosity import CuriosityEngine
        self._curiosity = CuriosityEngine(self)

    @property
    def goal_tracker(self):
        if self._goal_tracker is None:
            from agent.goal_tracker import GoalTracker
            self._goal_tracker = GoalTracker(self)
        return self._goal_tracker

    @property
    def subagent_coordinator(self):
        if self._subagent_coordinator is None:
            from agent.subagent import SubagentCoordinator
            self._subagent_coordinator = SubagentCoordinator(self)
        return self._subagent_coordinator

    @property
    def plan_tracker(self):
        if self._plan_tracker is None:
            from agent.plan_mode import PlanTracker
            self._plan_tracker = PlanTracker(self)
        return self._plan_tracker

    @property
    def workspace(self):
        return self._workspace

    @property
    def doom_loop(self):
        return self._doom_loop

    # ── 核心循环 ──

    def handle(self, user_input: str) -> str:
        self.session.add_message("user", user_input)

        inter = self._check_interjection()
        if inter:
            return "received interjection: " + inter

        # 技能匹配
        skill = self._skills.match(user_input)
        if skill:
            self.tools["_skill_prompt"] = {"func": lambda: skill.prompt, "desc": ""}

        # 路由
        if self.goal_tracker.is_active():
            result = self.goal_tracker.continue_goal(user_input)
        elif self._is_goal_request(user_input):
            result = self.goal_tracker.start_goal(user_input)
        elif self._is_complex_task(user_input):
            result = self.plan_tracker.plan_and_execute(user_input)
        else:
            result = self._chat(user_input)

        if self._curiosity:
            self._curiosity.tick()

        return result

    def _chat(self, user_input: str) -> str:
        ctx = self._build_context(user_input)

        for _ in range(5):
            raw = think(ctx)
            decision = parse_decision(raw)

            # 死循环检测
            dl_result = self._doom_loop.feed(raw)
            if dl_result["doom_loop"]:
                return self._doom_loop.recovery_action(dl_result)

            if decision.action == "reply":
                self.session.add_message("assistant", decision.answer)
                self._record_experience(user_input, decision, decision.answer)
                self._learn_to_kg(user_input, decision, decision.answer)
                return decision.answer

            elif decision.action == "tool":
                result = self._execute_tool(decision.tool, decision.params)
                self.session.add_message("tool", result, tool_name=decision.tool)
                self._record_experience(user_input, decision, result)
                self._learn_to_kg(user_input, decision, result)
                ctx = self._build_context("tool " + decision.tool + " result:\n" + result)
                continue

            elif decision.action == "ask":
                self.session.add_message("assistant", "[ask] " + decision.question)
                return decision.question

        return "thinking timeout"

    def _execute_tool(self, name: str, params: dict) -> str:
        if name not in self.tools:
            return json.dumps({"error": "unknown: " + name}, ensure_ascii=False)
        try:
            func = self.tools[name]["func"]
            result = func(**params) if params else func()
            _maybe_cache(result)
            return json.dumps(result, ensure_ascii=False, default=str)
        except Exception as e:
            return json.dumps({"error": str(e)}, ensure_ascii=False)

    def _build_context(self, user_input: str) -> str:
        builder = ContextBuilder()
        builder.task(task_summary_for_context())
        builder.history(self.session.to_context_text())

        # Persona system prompt
        if self._persona and self._persona.system_prompt:
            builder._task_context = self._persona.system_prompt + "\n" + builder._task_context

        # Skill injection
        skill = self._skills.match(user_input)
        if skill:
            builder.knowledge("[技能] " + skill.prompt)

        # KG
        try:
            from knowledge.kg import inject_context
            kg = inject_context(user_input)
            if kg: builder.knowledge(kg)
        except Exception: pass

        # Persona工具限流
        allowlist = self._persona.tools_allowlist if self._persona else None
        lines = []
        for n, i in self.tools.items():
            if allowlist is None or n in allowlist:
                lines.append("  " + n + ": " + i["desc"])
        builder.tools("\n".join(lines))

        return builder.build(user_input)

    def _record_experience(self, user_input, decision, result):
        try:
            from learning.experience_bank import record
            domain = decision.tool if decision.tool else "chat"
            record(user_input, {"action": decision.action, "tool": decision.tool, "params": decision.params}, str(result)[:2000], domain=domain)
        except Exception: pass

    def _learn_to_kg(self, user_input, decision, result):
        try:
            from knowledge.kg import relate
            tool = decision.tool if hasattr(decision, 'tool') and decision.tool else "chat"
            relate("乾坤", tool, "uses")
            result_str = str(result)[:500]
            for keyword in ["Python", "asyncio", "AI", "ML", "data", "api", "search", "fetch"]:
                if keyword.lower() in result_str.lower() or keyword.lower() in user_input.lower():
                    relate(tool, keyword, "related_to")
        except Exception: pass

    def _check_interjection(self):
        try:
            from agent.interjection import check_interjection
            return check_interjection()
        except Exception: return None

    def _is_goal_request(self, text):
        kw = ["help me", "task:", "goal:", "implement", "build", "create project"]
        return any(k in text.lower() for k in kw) and len(text) > 10

    def _is_complex_task(self, text):
        return len(text) > 50

    # ── 公共接口 ──

    def switch_persona(self, name: str) -> dict:
        from agent.persona import load_persona
        self._persona = load_persona(name)
        self.persona_name = name
        return {"ok": True, "persona": name, "description": self._persona.description}

    def switch_model(self, name: str) -> dict:
        from agent.model_switch import get_model_switch
        return get_model_switch().switch(name)

    def list_models(self) -> list:
        from agent.model_switch import get_model_switch
        return get_model_switch().list_models()

    def checkpoint(self, reason="manual"):
        from agent.session_persist import save_checkpoint
        return save_checkpoint(self, reason)

    def resume(self):
        from agent.session_persist import resume_from_checkpoint
        return resume_from_checkpoint(self)

    def record_feedback(self, rating: int, comment: str = ""):
        from agent.feedback import get_feedback_manager
        fm = get_feedback_manager()
        # 获取最后的用户输入和输出
        msgs = self.session.last_n(2)
        user_in = msgs[-2]["content"] if len(msgs) >= 2 else ""
        agent_out = msgs[-1]["content"] if msgs else ""
        fm.record(self.session.id, user_in, agent_out, rating, comment)


def _maybe_cache(result_json: str):
    try:
        data = json.loads(result_json)
        if data.get("ok") and data.get("url") and data.get("content"):
            from memory.cache import save_cached_content
            save_cached_content(data["url"], data.get("title", data["url"]), data["content"])
    except Exception: pass

"""Agent — v2.0"""

import json
from dataclasses import dataclass, field
from coordinator.engine import think, is_model_ready
from coordinator.context import ContextBuilder
from coordinator.decision import parse as parse_decision
from memory.sessions import Session
from memory.tasks import task_summary_for_context


@dataclass
class Agent:
    session: Session = field(default_factory=Session.create)
    _goal_tracker = None
    _subagent_coordinator = None
    _plan_tracker = None
    _curiosity = None
    _workspace = None

    def __post_init__(self):
        self._init_tools()
        self._init_workspace()
        self._init_curiosity()

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
        self._register_workspace_tools()

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

    def handle(self, user_input: str) -> str:
        self.session.add_message("user", user_input)
        inter = self._check_interjection()
        if inter:
            return "received interjection: " + inter
        if self.goal_tracker.is_active():
            return self.goal_tracker.continue_goal(user_input)
        if self._is_goal_request(user_input):
            return self.goal_tracker.start_goal(user_input)
        if self._is_complex_task(user_input):
            return self.plan_tracker.plan_and_execute(user_input)
        result = self._chat(user_input)
        if self._curiosity:
            self._curiosity.tick()
        return result

    def _chat(self, user_input: str) -> str:
        ctx = self._build_context(user_input)
        for _ in range(5):
            raw = think(ctx)
            decision = parse_decision(raw)
            if decision.action == "reply":
                self.session.add_message("assistant", decision.answer)
                self._record_experience(user_input, decision, decision.answer)
                return decision.answer
            elif decision.action == "tool":
                result = self._execute_tool(decision.tool, decision.params)
                self.session.add_message("tool", result, tool_name=decision.tool)
                self._record_experience(user_input, decision, result)
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
        try:
            from knowledge.kg import inject_context
            kg = inject_context(user_input)
            if kg: builder.knowledge(kg)
        except Exception:
            pass
        lines = []
        for n, i in self.tools.items():
            lines.append("  " + n + ": " + i["desc"])
        builder.tools("\n".join(lines))
        return builder.build(user_input)

    def _record_experience(self, user_input, decision, result):
        try:
            from learning.experience_bank import record
            domain = decision.tool if decision.tool else "chat"
            record(user_input, {"action": decision.action, "tool": decision.tool, "params": decision.params}, str(result)[:2000], domain=domain)
        except Exception:
            pass

    def _check_interjection(self):
        try:
            from agent.interjection import check_interjection
            return check_interjection()
        except Exception:
            return None

    def _is_goal_request(self, text):
        kw = ["help me", "task:", "goal:", "implement", "build", "create project"]
        return any(k in text.lower() for k in kw) and len(text) > 10

    def _is_complex_task(self, text):
        return len(text) > 50

    def checkpoint(self, reason="manual"):
        from agent.session_persist import save_checkpoint
        return save_checkpoint(self, reason)

    def resume(self):
        from agent.session_persist import resume_from_checkpoint
        return resume_from_checkpoint(self)


def _maybe_cache(result_json: str):
    try:
        data = json.loads(result_json)
        if data.get("ok") and data.get("url") and data.get("content"):
            from memory.cache import save_cached_content
            save_cached_content(data["url"], data.get("title", data["url"]), data["content"])
    except Exception:
        pass

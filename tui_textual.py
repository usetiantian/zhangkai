"""乾坤 TUI — Textual 全屏终端 (ratatui 级别)"""

import sys, os, json
from pathlib import Path
from datetime import datetime
from textual.app import App, ComposeResult
from textual.widgets import Header, Footer, Input, Static, RichLog, LoadingIndicator
from textual.containers import Container, VerticalScroll
from textual.reactive import reactive
from textual import events

sys.path.insert(0, str(Path(__file__).parent.parent))
from coordinator.engine import is_model_ready
from agent import Agent
from agent.hooks import create_default_registry
from agent.intelligent_router import get_router

agent: Agent | None = None
router = None
scrollback: list[dict] = []


def push_log(etype: str, content: str, **meta):
    scrollback.append({
        "type": etype, "content": str(content),
        "time": datetime.now().strftime("%H:%M"), **meta,
    })
    if len(scrollback) > 500:
        scrollback[:] = scrollback[-500:]


class StatusBar(Static):
    """顶部状态栏"""

    def on_mount(self):
        self.set_interval(1, self.refresh_status)

    def render(self) -> str:
        brain = "Qwen3-VL-2B" if is_model_ready() else "加载中"
        ds = "✓" if os.environ.get("DEEPSEEK_API_KEY") else "✗"
        tools_count = len(agent.tools) if agent else 0
        exp_count = "0"
        try:
            from learning.experience_bank import stats
            s = stats()
            exp_count = f"{s['total']}" + ("+" if s.get('ready_to_train') else "")
        except: pass

        model = router.get_current() if router else None
        route = model.name if model else "local"

        return (f" 大脑: {brain}  |  路由: {route}  |  "
                f"工具: {tools_count}  |  经验: {exp_count}  |  "
                f"DeepSeek: {ds}")

    def refresh_status(self):
        self.refresh()


class ConversationPane(VerticalScroll, can_focus=True):
    """对话面板 — 可滚动"""

    BINDINGS = [
        ("up", "scroll_up", "上滚"),
        ("down", "scroll_down", "下滚"),
        ("pageup", "page_up", "上页"),
        ("pagedown", "page_down", "下页"),
        ("home", "scroll_home", "顶部"),
        ("end", "scroll_end", "底部"),
    ]

    def render_messages(self):
        lines = []
        for entry in scrollback[-100:]:
            etype = entry["type"]
            t = entry["time"]
            content = entry["content"]

            if etype == "user":
                lines.append(f"[bold white]{t} ▸ {content}[/bold white]")
            elif etype == "assistant":
                lines.append(f"[dim]{t}[/dim]")
                lines.append(content[:3000])
            elif etype == "tool":
                tool = entry.get("tool_name", "")
                lines.append(f"[dim]{t}[/dim] [yellow]调用: {tool}[/yellow]")
                lines.append(f"[dim]{content[:500]}[/dim]")
            elif etype == "error":
                lines.append(f"[dim]{t}[/dim] [red]✗ {content[:500]}[/red]")
            elif etype == "system":
                lines.append(f"[dim]{t}[/dim] [dim italic]{content[:400]}[/dim italic]")
            lines.append("")

        if not lines:
            lines = ["", "", "   乾坤 · QianKun v2.0",
                     "   输入消息开始对话", "   /help 查看帮助", ""]

        self.update("\n".join(lines))

    def on_mount(self):
        self.render_messages()
        self.set_interval(2, self.render_messages)

    def action_scroll_up(self):
        self.scroll_up(3)

    def action_scroll_down(self):
        self.scroll_down(3)

    def action_page_up(self):
        self.scroll_page_up()

    def action_page_down(self):
        self.scroll_page_down()

    def action_scroll_home(self):
        self.scroll_home()

    def action_scroll_end(self):
        self.scroll_end()


class QianKunApp(App):
    """乾坤 Textual App"""

    CSS = """
    StatusBar {
        dock: top;
        height: 1;
        background: $panel;
        color: $text-muted;
        padding: 0 1;
    }
    ConversationPane {
        background: $surface;
        padding: 0 1;
    }
    Input {
        dock: bottom;
        margin: 0;
    }
    """

    BINDINGS = [
        ("escape", "quit", "退出"),
        ("ctrl+c", "quit", "退出"),
    ]

    def compose(self) -> ComposeResult:
        yield StatusBar()
        yield ConversationPane()
        yield Input(placeholder="输入消息 (/help 帮助, Esc 退出)")

    def on_mount(self):
        global agent, router
        agent = Agent()
        router = get_router()

        self.title = "乾坤 · QianKun v2.0"
        self.sub_title = "自主 Agent OS"

        # 预加载模型
        import threading
        threading.Thread(target=lambda: is_model_ready(), daemon=True).start()

        push_log("system", "乾坤已就绪。输入消息开始对话。")
        self.query_one(ConversationPane).render_messages()

    def on_input_submitted(self, event: Input.Submitted):
        user_input = event.value.strip()
        event.input.value = ""

        if not user_input:
            return

        # 命令
        if user_input.startswith("/"):
            self._handle_command(user_input)
            self.query_one(ConversationPane).render_messages()
            return

        push_log("user", user_input)

        # 路由
        model = router.select(user_input) if router else None
        if model and model.provider != "local":
            push_log("tool", f"路由: {model.name}", tool_name="router")

        self.query_one(ConversationPane).render_messages()

        # 处理
        try:
            reply = agent.handle(user_input)
        except Exception as e:
            reply = f"错误: {e}"

        if reply:
            push_log("assistant", reply)

        agent.session.commit()
        self.query_one(ConversationPane).render_messages()
        self.query_one(ConversationPane).scroll_end()

    def _handle_command(self, cmd: str):
        parts = cmd.lower().split()
        c = parts[0]

        if c == "/help":
            push_log("system", "命令: /goal /status /calibrate /learn /persona /model /clear /quit")
        elif c == "/status":
            lines = [f"会话: {agent.session.id}  消息: {len(agent.session.messages)}"]
            try:
                from learning.experience_bank import stats
                s = stats()
                lines.append(f"经验: {s['total']}条  可训练: {s.get('ready_to_train',False)}")
            except: pass
            try:
                from knowledge.self_model import weakness_report
                lines.append(weakness_report())
            except: pass
            push_log("system", "\n".join(lines))
        elif c == "/calibrate":
            try:
                from knowledge.self_model import calibrate, weakness_report
                calibrate()
                push_log("system", weakness_report())
            except Exception as e:
                push_log("error", str(e))
        elif c == "/learn":
            try:
                from learning.trainer import fine_tune
                r = fine_tune(sample_limit=20)
                push_log("system", f"训练完成! loss={r['loss']}" if r.get('ok') else f"跳过: {r.get('error')}")
            except Exception as e:
                push_log("error", str(e))
        elif c == "/persona" and len(parts) > 1:
            r = agent.switch_persona(parts[1])
            push_log("system", f"人格切换: {r.get('description', parts[1])}")
        elif c == "/model" and len(parts) > 1:
            r = agent.switch_model(parts[1])
            push_log("system", f"模型切换: {r.get('switched_to','?')}")
        elif c == "/goal" and len(parts) > 1:
            goal = " ".join(parts[1:])
            reply = agent.goal_tracker.start_goal(goal)
            push_log("system", f"Goal: {goal}")
            push_log("assistant", reply)
        elif c == "/clear":
            scrollback.clear()
            push_log("system", "已清屏")
        elif c in ("/q", "/quit"):
            self.exit()


def run():
    app = QianKunApp()
    app.run()

"""Full-Screen TUI v2 — 终端接管 + 滚动缓冲区 + 流式渲染"""

import sys, os, json, threading, time
from datetime import datetime
from rich.console import Console
from rich.live import Live
from rich.layout import Layout
from rich.panel import Panel
from rich.text import Text
from rich.syntax import Syntax
from rich.table import Table
from rich.markdown import Markdown
from rich import box

from coordinator.engine import is_model_ready
from agent import Agent
from agent.hooks import create_default_registry
from agent.intelligent_router import get_router, classify_task

console = Console()


class Scrollback:
    """滚动缓冲区"""

    def __init__(self, max_entries: int = 500):
        self.entries: list[dict] = []
        self.max_entries = max_entries
        self.scroll_offset: int = 0
        self.follow_mode: bool = True

    def push(self, etype: str, content: str, **meta):
        self.entries.append({
            "type": etype, "content": str(content),
            "time": datetime.now().strftime("%H:%M"), **meta,
        })
        if len(self.entries) > self.max_entries:
            self.entries = self.entries[-self.max_entries:]

    def visible_count(self, height: int) -> int:
        return min(height, len(self.entries))

    def scroll_up(self, n: int = 3):
        self.follow_mode = False
        self.scroll_offset = max(0, self.scroll_offset - n)

    def scroll_down(self, n: int = 3):
        self.scroll_offset += n
        if self.scroll_offset >= len(self.entries) - 3:
            self.follow_mode = True

    def scroll_bottom(self):
        self.follow_mode = True

    def view(self, height: int) -> list[dict]:
        total = len(self.entries)
        if total == 0:
            return []
        if self.follow_mode:
            start = max(0, total - height)
        else:
            visible = min(height, total)
            start = max(0, min(self.scroll_offset, total - visible))
        end = min(start + height, total)
        return self.entries[start:end]


def render_entry(entry: dict) -> str:
    """渲染单个条目为 rich markup"""
    etype = entry["type"]
    t = entry["time"]

    if etype == "user":
        return f"[dim]{t}[/dim] [bold white]▸ {entry['content']}[/bold white]"
    elif etype == "assistant":
        return f"[dim]{t}[/dim]\n{entry['content'][:2000]}"
    elif etype == "code":
        return f"[dim]{t}[/dim]\n[dim on #1e1e1e]{entry['content'][:1500]}[/]"
    elif etype == "tool":
        tool = entry.get("tool_name", "")
        return f"[dim]{t}[/dim] [yellow]调用: {tool}[/yellow]\n[dim]{entry['content'][:400]}[/dim]"
    elif etype == "error":
        return f"[dim]{t}[/dim] [red]✗ {entry['content'][:500]}[/red]"
    elif etype == "system":
        return f"[dim]{t}[/dim] [dim italic]{entry['content'][:400]}[/dim italic]"
    return entry["content"]


def run():
    """全屏 TUI"""
    agent = Agent()
    hooks = create_default_registry()
    sb = Scrollback()
    router = get_router()

    threading.Thread(target=lambda: is_model_ready(), daemon=True).start()
    hooks.emit("session_start", session_id=agent.session.id)

    def _make_live_view() -> Layout:
        """构建全屏视图"""
        layout = Layout()
        layout.split(
            Layout(name="header", size=3),
            Layout(name="body"),
            Layout(name="input_bar", size=3),
        )

        # Header
        hdr = Table(box=box.SIMPLE, show_header=False, show_edge=False,
                    padding=(0, 1), expand=True)
        hdr.add_column(style="dim", width=10, justify="right")
        hdr.add_column()
        brain = "Qwen3-VL-2B" if is_model_ready() else "加载中"
        ds = "[green]✓[/green]" if os.environ.get("DEEPSEEK_API_KEY") else "[dim]✗[/dim]"
        model = router.get_current()
        route = f"{model.name}" if model else "local"
        hdr.add_row("大脑", f"[cyan]{brain}[/cyan]  [dim]路由: {route}  DeepSeek:{ds}[/dim]")
        try:
            from learning.experience_bank import stats
            s = stats()
            exp_info = f"经验:{s['total']}条" + (" [green]可训练[/green]" if s.get('ready_to_train') else "")
        except:
            exp_info = "经验:0"
        hdr.add_row("状态", f"工具:{len(agent.tools)} | {exp_info} | 会话:{agent.session.id[:6]}")
        layout["header"].update(Panel(hdr, border_style="blue", padding=(0, 1)))

        # Body
        visible = sb.view(console.height - 8)
        if not visible:
            body_text = ("\n" * 3 +
                        "   [bold cyan]乾坤 · QianKun v2.0[/bold cyan]\n"
                        "   输入消息开始对话\n"
                        "   [dim]/help 查看帮助[/dim]")
        else:
            body_lines = []
            for e in visible:
                body_lines.append(render_entry(e))
            body_text = "\n".join(body_lines)
        layout["body"].update(Panel(body_text, border_style="blue", padding=(0, 1)))

        # Input bar
        goal = "[yellow][Goal][/yellow] " if (hasattr(agent, 'goal_tracker')
                and agent.goal_tracker.is_active()) else ""
        layout["input_bar"].update(Panel(
            f"{goal}[bold green]▸[/bold green] 输入消息 "
            f"[dim](/help /quit ↑↓滚动)[/dim]",
            border_style="green", padding=(1, 1)))

        return layout

    # 主循环
    from rich.prompt import PromptBase
    class TuiPrompt(PromptBase):
        prompt_suffix = ""

    try:
        with Live(_make_live_view(), console=console, screen=True,
                  refresh_per_second=4, transient=False) as live:
            while True:
                live.update(_make_live_view())

                try:
                    user_input = console.input(
                        Text("▸ ", style="bold green")
                    ).strip()
                except (EOFError, KeyboardInterrupt):
                    break

                if not user_input:
                    continue

                if user_input.startswith("/"):
                    r = _cmd(user_input, agent, sb)
                    if r == "quit":
                        break
                    continue

                # User message
                sb.push("user", user_input)
                sb.scroll_bottom()
                live.update(_make_live_view())

                # Route
                model = router.select(user_input)

                try:
                    reply = agent.handle(user_input)
                except Exception as e:
                    reply = f"错误: {e}"

                if reply:
                    sb.push("assistant", reply)
                sb.scroll_bottom()

                agent.session.commit()
                hooks.emit("turn_end", session_id=agent.session.id,
                          output=reply[:200] if reply else "")

    except KeyboardInterrupt:
        pass

    console.print("\n[bold]再见。[/bold]")
    hooks.emit("session_end", session_id=agent.session.id)


def _cmd(cmd: str, agent, sb: Scrollback) -> str | None:
    parts = cmd.lower().split()
    c = parts[0]

    if c in ("/q", "/quit", "/exit"):
        return "quit"
    elif c == "/help":
        sb.push("system", "命令: /goal /status /calibrate /learn /persona /model /clear /quit")
    elif c == "/status":
        lines = [f"会话:{agent.session.id} 消息:{len(agent.session.messages)} 工具:{len(agent.tools)}"]
        try:
            from learning.experience_bank import stats
            s = stats()
            lines.append(f"经验:{s['total']}条 可训练:{s.get('ready_to_train',False)}")
        except: pass
        try:
            from knowledge.self_model import weakness_report
            lines.append(weakness_report())
        except: pass
        sb.push("system", "\n".join(lines))
    elif c == "/calibrate":
        try:
            from knowledge.self_model import calibrate, weakness_report
            calibrate()
            sb.push("system", weakness_report())
        except Exception as e:
            sb.push("error", str(e))
    elif c == "/learn":
        try:
            from learning.trainer import fine_tune
            r = fine_tune(sample_limit=20)
            sb.push("system", f"训练完成! loss={r['loss']}" if r.get('ok') else f"跳过:{r.get('error')}")
        except Exception as e:
            sb.push("error", str(e))
    elif c == "/clear":
        sb.entries.clear()
    elif c == "/persona" and len(parts) > 1:
        r = agent.switch_persona(parts[1])
        sb.push("system", f"人格: {r.get('description', parts[1])}")
    elif c == "/model" and len(parts) > 1:
        r = agent.switch_model(parts[1])
        sb.push("system", f"模型: {r.get('switched_to', parts[1])}")
    elif c == "/goal" and len(parts) > 1:
        goal = " ".join(parts[1:])
        reply = agent.goal_tracker.start_goal(goal)
        sb.push("system", f"Goal: {goal}")
        sb.push("assistant", reply)
    sb.scroll_bottom()
    return None

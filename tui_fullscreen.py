"""Full-Screen TUI — 完整终端接管 (ro-build pager 设计思想)"""

import sys, os, json, threading, time, queue
from datetime import datetime
from pathlib import Path

from rich.console import Console
from rich.live import Live
from rich.layout import Layout
from rich.panel import Panel
from rich.text import Text
from rich.syntax import Syntax
from rich.table import Table
from rich import box
from rich.prompt import Prompt

from coordinator.engine import is_model_ready
from agent import Agent
from agent.hooks import create_default_registry
from agent.intelligent_router import get_router, classify_task

console = Console()

# ── 消息队列 (流式渲染) ──
_event_queue = queue.Queue()


class ScrollbackBuffer:
    """滚动缓冲区 — 管理对话历史和视口"""

    def __init__(self, max_entries: int = 500):
        self.entries: list[dict] = []
        self.max_entries = max_entries
        self.scroll_offset: int = 0
        self.viewport_height: int = 30
        self.follow_mode: bool = True  # 自动跟随最新

    def push(self, entry_type: str, content: str, metadata: dict = None):
        """添加条目"""
        self.entries.append({
            "type": entry_type,
            "content": content,
            "time": datetime.now().strftime("%H:%M:%S"),
            **(metadata or {}),
        })
        if len(self.entries) > self.max_entries:
            self.entries = self.entries[-self.max_entries:]

    def visible_range(self) -> tuple[int, int]:
        """可见范围"""
        total = len(self.entries)
        visible = min(self.viewport_height, total)
        if self.follow_mode:
            start = max(0, total - visible)
        else:
            start = max(0, min(self.scroll_offset, total - visible))
        return (start, start + visible)

    def scroll_up(self, n: int = 5):
        self.follow_mode = False
        self.scroll_offset = max(0, self.scroll_offset - n)

    def scroll_down(self, n: int = 5):
        self.scroll_offset += n
        total = len(self.entries)
        visible = min(self.viewport_height, total)
        if self.scroll_offset >= total - visible:
            self.scroll_offset = max(0, total - visible)
            self.follow_mode = True

    def scroll_to_bottom(self):
        self.follow_mode = True


def _render_entry(entry: dict, width: int) -> Text:
    """渲染单个条目"""
    etype = entry["type"]
    content = entry["content"]
    timestamp = entry.get("time", "")

    if etype == "user":
        return Text(f"  {timestamp} ", style="dim") + Text(
            content, style="bold white")

    elif etype == "assistant":
        # 尝试渲染为 Markdown
        try:
            from rich.markdown import Markdown
            md = Markdown(content[:2000], code_theme="monokai")
            return Text(f"  {timestamp} ", style="dim") + Text(str(md))
        except:
            return Text(content)

    elif etype == "code":
        try:
            lang = entry.get("language", "python")
            syntax = Syntax(content[:2000], lang, theme="monokai",
                           line_numbers=True, word_wrap=True)
            return Text(f"  {timestamp} ", style="dim") + Text("\n" + str(syntax))
        except:
            return Text(content)

    elif etype == "tool_call":
        tool = entry.get("tool_name", "")
        return Text(f"  {timestamp} ", style="dim") + Text(
            f"调用: {tool}", style="bold yellow")

    elif etype == "tool_result":
        return Text(f"  {timestamp} ", style="dim") + Text(
            content[:500], style="dim italic")

    elif etype == "error":
        return Text(f"  {timestamp} ✗ ", style="bold red") + Text(
            content[:500], style="red")

    elif etype == "system":
        return Text(f"  {timestamp} ", style="dim") + Text(
            content[:300], style="dim")

    return Text(content)


def _make_layout() -> Layout:
    """创建全屏布局"""
    layout = Layout()
    layout.split(
        Layout(name="header", size=3),
        Layout(name="body"),
        Layout(name="input_line", size=3),
    )
    return layout


def _render_header(agent: Agent) -> Panel:
    """渲染顶部状态栏"""
    table = Table(box=box.SIMPLE, show_header=False, padding=(0, 1),
                  show_edge=False, expand=True)
    table.add_column(style="dim", width=10, justify="right")
    table.add_column()

    # 大脑 + 外部模型
    brain = "Qwen3-VL-2B" if is_model_ready() else "加载中"
    ds_key = bool(os.environ.get("DEEPSEEK_API_KEY"))
    router = get_router()
    current_model = router.get_current()
    route_info = f"{current_model.name} ({current_model.provider})" if current_model else "local"

    table.add_row("大脑", f"[cyan]{brain}[/cyan]  [dim]| 路由: {route_info}[/dim]")

    # 工具数 + 经验
    exp_str = "0"
    try:
        from learning.experience_bank import stats
        s = stats()
        exp_str = f"{s['total']}条"
        if s.get('ready_to_train'):
            exp_str += " [green]可训练[/green]"
    except:
        pass

    table.add_row("状态",
                  f"工具:{len(agent.tools)} | 经验:{exp_str} | "
                  f"DeepSeek:{'[green]✓[/green]' if ds_key else '[dim]✗[/dim]'} | "
                  f"会话:{agent.session.id[:6]}")

    return Panel(table, border_style="blue", padding=(0, 1))


def _render_body(scrollback: ScrollbackBuffer, width: int) -> str:
    """渲染对话主体"""
    start, end = scrollback.visible_range()
    visible = scrollback.entries[start:end]

    if not visible:
        return ("\n" * 5 +
                "    乾坤 · QianKun v2.0\n"
                "    输入消息开始对话...\n"
                "    /help 查看帮助\n")

    lines = []
    for entry in visible:
        rendered = _render_entry(entry, width)
        lines.append(str(rendered))
        lines.append("")  # 空行分隔

    # 如果上面有未显示的消息
    if start > 0:
        lines.insert(0, f"  [dim]... 上面还有 {start} 条消息 (↑ 滚动查看)[/dim]")

    # 如果下面有未显示的消息
    if end < len(scrollback.entries) and not scrollback.follow_mode:
        lines.append(f"  [dim]... 下面还有 {len(scrollback.entries) - end} 条消息 (↓ 滚动查看)[/dim]")

    return "\n".join(lines)


def run():
    """全屏 TUI 主循环"""
    # 初始化
    agent = Agent()
    hooks = create_default_registry()
    scrollback = ScrollbackBuffer()
    router = get_router()

    # 预加载模型
    def _preload():
        is_model_ready()
    threading.Thread(target=_preload, daemon=True).start()

    hooks.emit("session_start", session_id=agent.session.id)

    input_buffer = ""

    # 全屏渲染循环
    with Live(console=console, screen=True, auto_refresh=False) as live:
        while True:
            # 构建布局
            layout = _make_layout()
            layout["header"].update(_render_header(agent))

            # 主体渲染
            body_text = _render_body(scrollback, console.width)
            layout["body"].update(Panel(
                body_text, border_style="blue", padding=(0, 1)))

            # 输入行
            goal_active = agent.goal_tracker.is_active() if hasattr(agent, 'goal_tracker') else False
            mode_indicator = "[yellow][Goal][/yellow] " if goal_active else ""
            input_display = (f"{mode_indicator}"
                           f"[bold green]你:[/bold green] {input_buffer}"
                           f"[dim]█[/dim]")
            layout["input_line"].update(Panel(
                input_display, border_style="green", padding=(1, 1)))

            live.update(layout)
            live.refresh()

            # 读取输入 (逐字符)
            try:
                from rich import get_console
                c = get_console()
                key = c.input()

                if key == "\n" or key == "\r":  # Enter
                    user_input = input_buffer.strip()
                    input_buffer = ""

                    if not user_input:
                        continue

                    # 命令
                    if user_input.startswith("/"):
                        _handle_command(user_input, agent, scrollback)
                        continue

                    # 添加到 scrollback
                    scrollback.push("user", user_input)
                    scrollback.scroll_to_bottom()

                    # 路由
                    model = router.select(user_input)

                    # 更新布局显示"思考中"
                    layout["body"].update(Panel(
                        _render_body(scrollback, console.width) +
                        "\n  [dim]思考中...[/dim]",
                        border_style="blue", padding=(0, 1)))
                    live.update(layout)
                    live.refresh()

                    # 处理
                    hooks.emit("turn_start", session_id=agent.session.id,
                              input=user_input[:100])

                    scrollback.push("tool_call", f"→ {model.name} ({model.provider})",
                                  {"tool_name": f"route:{model.name}"})

                    reply = agent.handle(user_input)

                    if reply:
                        scrollback.push("assistant", reply)
                    else:
                        scrollback.push("error", "无响应")

                    hooks.emit("turn_end", session_id=agent.session.id,
                              output=reply[:200] if reply else "")

                    scrollback.scroll_to_bottom()
                    agent.session.commit()

                    # 自动 compaction
                    if len(agent.session.messages) > 50:
                        from agent.compaction import compact_session
                        result = compact_session(agent.session.id)
                        if result.get("compacted"):
                            scrollback.push("system",
                                f"上下文已压缩 ({result['total_messages']}→{result['kept']}条)")

                elif key == "\x7f":  # Backspace
                    input_buffer = input_buffer[:-1]
                elif key == "\t":  # Tab
                    input_buffer += "    "
                elif key == "\x1b":  # ESC
                    # 可能是方向键序列
                    pass
                elif len(key) == 1 and ord(key) >= 32:  # 可打印字符
                    input_buffer += key

            except KeyboardInterrupt:
                live.stop()
                console.print("\n[bold]再见。[/bold]")
                hooks.emit("session_end", session_id=agent.session.id)
                break
            except EOFError:
                break


def _handle_command(cmd: str, agent: Agent, scrollback: ScrollbackBuffer):
    """处理命令"""
    parts = cmd.lower().split()
    c = parts[0]

    if c in ("/q", "/quit", "/exit"):
        raise KeyboardInterrupt()

    elif c == "/help":
        scrollback.push("system", "\n".join([
            "命令列表:",
            "  /goal <目标>     设定并执行目标",
            "  /status          系统状态",
            "  /calibrate       重新校准能力",
            "  /learn           触发训练",
            "  /persona <名>    切换人格 (default/stock/coder/researcher)",
            "  /model <名>      切换模型 (qwen3-thinking/qwen2/deepseek-v4)",
            "  /clear           清屏",
            "  /quit            退出",
            "  ↑↓              滚动历史",
        ]))

    elif c == "/status":
        lines = [f"会话: {agent.session.id}", f"消息: {len(agent.session.messages)}",
                 f"工具: {len(agent.tools)}"]
        try:
            from learning.experience_bank import stats
            s = stats()
            lines.append(f"经验: {s['total']}条")
        except: pass
        try:
            from knowledge.self_model import weakness_report
            lines.append(weakness_report())
        except: pass
        scrollback.push("system", "\n".join(lines))

    elif c == "/calibrate":
        scrollback.push("tool_call", "校准中...", {"tool_name": "calibrate"})
        try:
            from knowledge.self_model import calibrate, weakness_report
            calibrate()
            scrollback.push("system", weakness_report())
        except Exception as e:
            scrollback.push("error", f"校准失败: {e}")

    elif c == "/learn":
        scrollback.push("tool_call", "训练中...", {"tool_name": "learn"})
        try:
            from learning.trainer import fine_tune
            r = fine_tune(sample_limit=20)
            if r.get("ok"):
                scrollback.push("system", f"训练完成! loss={r['loss']}")
            else:
                scrollback.push("system", f"跳过: {r.get('error','?')}")
        except Exception as e:
            scrollback.push("error", f"训练失败: {e}")

    elif c == "/persona" and len(parts) > 1:
        r = agent.switch_persona(parts[1])
        scrollback.push("system", f"人格: {r.get('description', parts[1])}")

    elif c == "/model" and len(parts) > 1:
        r = agent.switch_model(parts[1])
        scrollback.push("system", f"模型: {r.get('switched_to', parts[1])}")

    elif c == "/goal" and len(parts) > 1:
        goal = " ".join(parts[1:])
        reply = agent.goal_tracker.start_goal(goal)
        scrollback.push("system", f"Goal: {goal}")
        scrollback.push("assistant", reply)

    elif c == "/clear":
        scrollback.entries.clear()

    scrollback.scroll_to_bottom()

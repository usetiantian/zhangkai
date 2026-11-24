"""乾坤 TUI 主循环 — 完整 rich + pager 引擎"""

import sys, os, json, io
from pathlib import Path

# 确保 stdout UTF-8
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from rich.console import Console
from rich.panel import Panel
from rich.layout import Layout
from rich.live import Live
from rich.text import Text
from rich.markdown import Markdown
from rich.table import Table
from rich import box
from rich.prompt import Prompt

from coordinator.engine import is_model_ready
from agent import Agent
from agent.hooks import create_default_registry
from shell.pager_engine import PagerState
from agent.intelligent_router import get_router, classify_task

console = Console()


def _make_layout() -> Layout:
    """创建 rich 布局"""
    layout = Layout()
    layout.split(
        Layout(name="header", size=3),
        Layout(name="body"),
        Layout(name="input", size=3),
    )
    return layout


def _render_header(agent: Agent) -> Panel:
    """渲染顶部状态栏"""
    table = Table(box=box.SIMPLE, show_header=False, padding=(0, 1))
    table.add_column(style="dim", width=12)
    table.add_column()

    # 大脑状态
    brain = "Qwen3-VL-2B" if is_model_ready() else "未加载"
    table.add_row("大脑", f"[bold cyan]{brain}[/bold cyan]")

    # 外部模型
    ds = "DeepSeek V4" if os.environ.get("DEEPSEEK_API_KEY") else "未配置"
    gpt = "GPT-4o" if os.environ.get("OPENAI_API_KEY") else "未配置"
    ext = []
    if os.environ.get("DEEPSEEK_API_KEY"): ext.append("DeepSeek V4")
    if os.environ.get("OPENAI_API_KEY"): ext.append("GPT-4o")
    table.add_row("外部", f"[dim]{', '.join(ext) if ext else '仅本地'}[/dim]")

    # 工具和经验
    try:
        from learning.experience_bank import stats
        s = stats()
        exp_str = f"{s['total']} 条" + (" [green]可训练[/green]" if s.get('ready_to_train') else "")
    except:
        exp_str = "0"
    table.add_row("工具/经验", f"{len(agent.tools)} 个 / {exp_str}")

    # 当前路由
    if agent.session and agent.session.messages:
        last_msg = agent.session.messages[-1]["content"][:50] if agent.session.messages else ""
        task = classify_task(last_msg)
        router = get_router()
        current = router.get_current()
        model_name = current.name if current else "local"
        table.add_row("路由", f"[dim]{task.value} → {model_name}[/dim]")

    return Panel(table, title="[bold]乾坤 · QianKun v2.0[/bold]",
                 border_style="blue", padding=(0, 1))


def _render_scrollback(pager: PagerState) -> Panel:
    """渲染对话历史 — 使用 pager 引擎"""
    if not pager.entries:
        return Panel("输入消息开始对话...", border_style="dim")

    pager.prepare_layout(console.width - 4, console.height - 10)
    blocks = pager.get_visible_blocks()

    lines = []
    for block in blocks:
        content = block.get("content", "")
        btype = block.get("type", "text")

        if btype == "user_prompt":
            lines.append(Text(f"▸ {content[:200]}", style="bold green"))
        elif btype == "tool_result":
            lines.append(Text(f"  {content[:300]}", style="dim"))
        elif btype == "error":
            lines.append(Text(f"✗ {content[:200]}", style="bold red"))
        elif btype == "goal_progress":
            lines.append(Text(f"◆ {content[:200]}", style="bold yellow"))
        else:
            # assistant text — render as markdown
            lines.append(Markdown(content[:1000]))

    return Panel(
        Text("\n").join(
            [l if isinstance(l, Text) else Text(str(l)) for l in lines]
        ) if lines else Text(""),
        title="对话",
        border_style="blue",
        padding=(0, 1),
    )


def _render_input(agent: Agent) -> Panel:
    """渲染输入提示行"""
    goal_active = agent.goal_tracker.is_active() if hasattr(agent, 'goal_tracker') else False
    status = "[yellow][Goal模式][/yellow] " if goal_active else ""

    return Panel(
        Text(f"{status}输入消息 (/help 帮助, /quit 退出):", style="dim"),
        border_style="green",
        padding=(1, 1),
    )


def run():
    """TUI 主循环 — 完整 rich 渲染"""
    # 初始化
    agent = Agent()
    hooks = create_default_registry()
    pager = PagerState()
    router = get_router()

    # 预加载模型 (后台)
    import threading
    def _preload():
        is_model_ready()
    threading.Thread(target=_preload, daemon=True).start()

    # 启动信息
    console.print(Panel(
        Text("乾坤 · QianKun v2.0\n自主 Agent 工作环境\n"
             f"大脑: Qwen3-VL-2B-Thinking | "
             f"工具: {len(agent.tools)} 个 | "
             f"DeepSeek: {'已配置' if os.environ.get('DEEPSEEK_API_KEY') else '未配置'}",
             style="bold cyan", justify="center"),
        border_style="blue", box=box.DOUBLE, padding=(1, 2),
    ))

    hooks.emit("session_start", session_id=agent.session.id)

    # 主循环
    while True:
        try:
            user_input = Prompt.ask(
                Text("\n你", style="bold green"),
                console=console,
            ).strip()
        except (EOFError, KeyboardInterrupt):
            console.print("\n[bold]再见。[/bold]")
            hooks.emit("session_end", session_id=agent.session.id)
            break

        if not user_input:
            continue

        # 命令处理
        if user_input.startswith("/"):
            result = _handle_command(user_input, agent, pager)
            if result == "quit":
                break
            continue

        # 添加到 pager
        pager.push_block({"type": "user_prompt", "content": user_input, "height": 2})

        # 智能路由: 选择模型
        model = router.select(user_input)
        console.print(f"  [dim]→ {model.name} ({model.provider})[/dim]")

        # 处理
        hooks.emit("turn_start", session_id=agent.session.id, input=user_input[:100])
        reply = agent.handle(user_input)

        if reply:
            pager.push_block({"type": "text", "content": reply,
                             "height": reply.count("\n") + 2})
            console.print(Markdown(reply[:2000]))

        hooks.emit("turn_end", session_id=agent.session.id, output=reply[:200] if reply else "")

        # 自动 compaction
        agent.session.commit()
        if len(agent.session.messages) > 50:
            from agent.compaction import compact_session
            result = compact_session(agent.session.id)
            if result.get("compacted"):
                console.print(f"  [dim]上下文已压缩 ({result['total_messages']}→{result['kept']}条)[/dim]")


def _handle_command(cmd: str, agent: Agent, pager: PagerState) -> str | None:
    """处理命令"""
    parts = cmd.lower().split()
    c = parts[0]

    if c in ("/quit", "/exit", "/q"):
        console.print("[bold]再见。[/bold]")
        return "quit"

    elif c == "/help":
        table = Table(title="命令", box=box.SIMPLE)
        table.add_column("命令", style="cyan")
        table.add_column("说明")
        table.add_row("/goal <目标>", "设定并开始执行目标")
        table.add_row("/status", "查看系统状态")
        table.add_row("/calibrate", "重新校准能力")
        table.add_row("/learn", "触发学习/训练")
        table.add_row("/persona <名>", "切换人格 (default/stock/coder/researcher)")
        table.add_row("/model <名>", "切换模型 (qwen3-thinking/qwen2/deepseek-v4)")
        table.add_row("/new", "新会话")
        table.add_row("/history", "对话历史")
        table.add_row("/quit", "退出")
        console.print(table)

    elif c == "/status":
        table = Table(box=box.SIMPLE, show_header=False)
        table.add_column(style="dim")
        table.add_column()
        table.add_row("会话", agent.session.id[:8])
        table.add_row("消息", str(len(agent.session.messages)))
        table.add_row("工具", str(len(agent.tools)))
        table.add_row("大脑", "就绪" if is_model_ready() else "未加载")
        try:
            from learning.experience_bank import stats
            s = stats()
            table.add_row("经验", f"{s['total']} 条" + (" (可训练)" if s.get('ready_to_train') else ""))
        except: pass
        try:
            from knowledge.self_model import weakness_report
            table.add_row("能力", weakness_report().replace("[当前能力]\n", ""))
        except: pass
        try:
            from agent.external_model_v2 import ExternalModelProviderV2
            ext = ExternalModelProviderV2()
            cs = ext.get_cache_stats()
            table.add_row("DeepSeek缓存", f"命中率 {cs['hit_rate_pct']}% ({cs['hits']}/{cs['total_calls']})")
        except: pass
        console.print(Panel(table, title="系统状态", border_style="blue"))

    elif c == "/calibrate":
        with console.status("[bold cyan]校准中...[/bold cyan]"):
            try:
                from knowledge.self_model import calibrate, weakness_report
                calibrate()
                console.print(weakness_report())
            except Exception as e:
                console.print(f"[red]失败: {e}[/red]")

    elif c == "/learn":
        with console.status("[bold cyan]训练中...[/bold cyan]"):
            try:
                from learning.trainer import fine_tune
                r = fine_tune(sample_limit=20)
                if r.get("ok"):
                    console.print(f"[green]完成! loss={r['loss']}[/green]")
                else:
                    console.print(f"[yellow]跳过: {r.get('error','?')}[/yellow]")
            except Exception as e:
                console.print(f"[red]失败: {e}[/red]")

    elif c == "/persona" and len(parts) > 1:
        name = parts[1]
        r = agent.switch_persona(name)
        console.print(f"[green]人格切换: {r['description']}[/green]"
                      if r.get("ok") else f"[red]失败: {r.get('error','?')}[/red]")

    elif c == "/model" and len(parts) > 1:
        name = parts[1]
        r = agent.switch_model(name)
        console.print(f"[green]模型切换: {r.get('switched_to','?')}[/green]"
                      if r.get("ok") else f"[yellow]{r.get('error','?')}[/yellow]")

    elif c == "/goal" and len(parts) > 1:
        goal_text = " ".join(parts[1:])
        console.print(f"[bold yellow]Goal: {goal_text}[/bold yellow]")
        reply = agent.goal_tracker.start_goal(goal_text)
        console.print(Markdown(reply))
        pager.push_block({"type": "goal_progress", "content": reply, "height": 5})

    elif c == "/new":
        agent.session = type(agent.session).create()
        pager.entries.clear()
        pager.invalidate_layout_cache()
        console.print("[green]新会话[/green]")

    elif c == "/history":
        for m in agent.session.last_n(15):
            role_style = {"user": "green", "assistant": "cyan",
                         "tool": "dim"}.get(m["role"], "")
            console.print(f"  [{role_style}][{m['role']}][/{role_style}] {m['content'][:120]}")

    return None

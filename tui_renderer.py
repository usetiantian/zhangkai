"""TUI — 终端界面增强 (移植自 grok-build pager 的渲染思想)"""

import sys
from datetime import datetime
from coordinator.engine import is_model_ready

try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table
    from rich.layout import Layout
    from rich.live import Live
    from rich.text import Text
    from rich.markdown import Markdown
    from rich import box
    HAS_RICH = True
except ImportError:
    HAS_RICH = False


class QianKunTUI:
    """乾坤终端界面 — rich 增强版"""

    def __init__(self, agent=None):
        self.agent = agent
        self.console = Console() if HAS_RICH else None
        self.theme = "blue"

    def print_banner(self):
        """打印启动横幅"""
        if HAS_RICH and self.console:
            panel = Panel(
                Text("乾坤 · QianKun v2.0\n自主 Agent 工作环境",
                     style=f"bold {self.theme}", justify="center"),
                box=box.DOUBLE,
                border_style=self.theme,
                padding=(1, 2),
            )
            self.console.print(panel)
        else:
            print("=" * 55)
            print("  乾坤 · QianKun v2.0")
            print("=" * 55)

    def print_status(self):
        """打印系统状态"""
        if not HAS_RICH:
            return

        table = Table(box=box.SIMPLE, show_header=False, padding=(0, 2))
        table.add_column(style="dim")
        table.add_column()

        if is_model_ready():
            table.add_row("[大脑]", "Qwen3-VL-2B-Thinking (GPU)")
        else:
            table.add_row("[大脑]", "未加载")

        if self.agent:
            table.add_row("[工具]", f"{len(self.agent.tools)} 个")
            table.add_row("[会话]", self.agent.session.id[:8])

            try:
                from learning.experience_bank import stats
                s = stats()
                table.add_row("[经验]", f"{s['total']} 条" +
                              (" (可训练)" if s.get('ready_to_train') else ""))
            except Exception:
                pass

        self.console.print(table)

    def render_reply(self, text: str, role: str = "assistant"):
        """渲染回复"""
        if HAS_RICH and self.console:
            if role == "assistant":
                self.console.print(
                    Text(text, style=f"bold {self.theme}"),
                    markup=False,
                )
            elif role == "tool":
                self.console.print(
                    Panel(text[:400], title="工具结果",
                          border_style="dim", padding=(0, 1)),
                )
            else:
                self.console.print(text)
        else:
            print(text)

    def render_error(self, text: str):
        """渲染错误"""
        if HAS_RICH and self.console:
            self.console.print(
                Panel(text, title="错误", border_style="red",
                      padding=(0, 1)),
            )
        else:
            print(f"[错误] {text}")

    def render_goal_progress(self, goal_tracker):
        """渲染目标进度"""
        if not goal_tracker or not goal_tracker.orchestration:
            return

        orch = goal_tracker.orchestration
        if not HAS_RICH:
            print(f"[目标] {orch.objective[:50]} " +
                  f"({orch.total_worker_rounds} 轮)")
            return

        table = Table(box=box.SIMPLE, show_header=False, padding=(0, 1))
        table.add_column(style="dim")
        table.add_column()
        table.add_row("目标", orch.objective[:60])
        table.add_row("状态", orch.status.value)
        table.add_row("阶段", orch.phase.value)
        table.add_row("轮次", str(orch.total_worker_rounds))
        table.add_row("验证", str(orch.total_verify_rounds))
        if orch.token_budget:
            remaining = orch.token_budget - orch.parent_tokens_spent
            table.add_row("Token", f"{remaining}/{orch.token_budget}")

        self.console.print(
            Panel(table, title="目标进度", border_style="green",
                  padding=(0, 1)),
        )

    def render_markdown(self, text: str):
        """渲染 Markdown"""
        if HAS_RICH and self.console:
            self.console.print(Markdown(text[:3000]))
        else:
            print(text[:3000])

    def get_input(self, prompt: str = "你: ") -> str:
        """获取用户输入"""
        if HAS_RICH and self.console:
            return self.console.input(
                Text(prompt, style=f"bold {self.theme}")
            ).strip()
        return input(prompt).strip()


# 全局
_tui: QianKunTUI | None = None


def get_tui(agent=None) -> QianKunTUI:
    global _tui
    if _tui is None:
        _tui = QianKunTUI(agent)
    return _tui

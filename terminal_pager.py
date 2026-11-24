"""Terminal Pager — 完整 scrollback 渲染引擎 (移植自 grok-build pager)"""

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path


class BlockType(Enum):
    TEXT = "text"
    CODE = "code"
    TOOL_RESULT = "tool_result"
    SYSTEM = "system"
    USER_PROMPT = "user_prompt"
    GOAL_PROGRESS = "goal_progress"
    ERROR = "error"


@dataclass
class TextBlock:
    """一个文本块"""
    type: BlockType
    content: str
    height: int = 1           # 渲染高度
    collapsed: bool = False
    selection_start: int = 0
    selection_end: int = 0

    def render(self, width: int = 80) -> list[str]:
        """渲染为行列表"""
        lines = []
        for line in self.content.split("\n"):
            while len(line) > width:
                lines.append(line[:width])
                line = line[width:]
            lines.append(line)
        return lines or [""]


@dataclass
class LayoutCache:
    """布局缓存 — 虚拟 Y 坐标映射"""
    virtual_y: dict[int, int] = field(default_factory=dict)  # entry_index → y
    entry_heights: dict[int, int] = field(default_factory=dict)
    total_height: int = 0
    gaps_may_be_dirty: bool = True


@dataclass
class ScrollbackState:
    """
    Scrollback 状态 — 移植自 grok-build ScrollbackState.
    
    管理:
    - 虚拟 Y 坐标映射
    - 可见区域计算
    - 滚动偏移
    - 布局缓存
    """
    entries: list[TextBlock] = field(default_factory=list)
    viewport_height: int = 24
    scroll_offset: int = 0       # 从顶部偏移
    layout_cache: LayoutCache | None = None

    def push_entry(self, block: TextBlock):
        """添加一个条目"""
        self.entries.append(block)
        if self.layout_cache:
            self.layout_cache.gaps_may_be_dirty = True

    def visible_entry_range(self) -> range:
        """可见条目范围"""
        if not self.entries:
            return range(0)
        self._ensure_layout()
        return range(len(self.entries))

    def viewport_virtual_bounds(self) -> tuple[int, int] | None:
        """
        计算视口虚拟边界 (移植自 grok-build viewport_virtual_bounds).
        """
        cache = self.layout_cache
        if not cache or not self.entries:
            return None

        visible = self.visible_entry_range()
        if not visible:
            return None

        base_y = cache.virtual_y.get(visible.start, 0)
        top = base_y + self.scroll_offset
        bottom = top + self.viewport_height
        
        return (top, bottom)

    def entry_at_content_y(self, y: int) -> int | None:
        """根据 Y 坐标找到对应条目"""
        if not self.layout_cache:
            return None
        for idx, vy in self.layout_cache.virtual_y.items():
            height = self.layout_cache.entry_heights.get(idx, 1)
            if vy <= y < vy + height:
                return idx
        return None

    def compute_paint_window(self) -> tuple[int, int]:
        """
        计算绘制窗口 (移植自 grok-build compute_paint_window).
        返回 (start_entry, end_entry).
        """
        bounds = self.viewport_virtual_bounds()
        if not bounds:
            return (0, 0)

        top, bottom = bounds
        start = self.entry_at_content_y(top)
        end = self.entry_at_content_y(bottom)

        if start is None:
            start = 0
        if end is None:
            end = len(self.entries) - 1 if self.entries else 0

        return (start, end + 1)

    def scroll_to(self, entry_index: int):
        """滚动到指定条目"""
        if not self.layout_cache or entry_index not in self.layout_cache.virtual_y:
            return
        target_y = self.layout_cache.virtual_y[entry_index]
        max_offset = max(0, self.layout_cache.total_height - self.viewport_height)
        self.scroll_offset = min(target_y, max_offset)

    def scroll_down(self, lines: int = 1):
        """向下滚动"""
        max_offset = max(0, (self.layout_cache.total_height - self.viewport_height) if self.layout_cache else 0)
        self.scroll_offset = min(self.scroll_offset + lines, max_offset)

    def scroll_up(self, lines: int = 1):
        """向上滚动"""
        self.scroll_offset = max(0, self.scroll_offset - lines)

    def _ensure_layout(self):
        """确保布局缓存最新"""
        if self.layout_cache is None:
            self.layout_cache = LayoutCache()
            self.layout_cache.gaps_may_be_dirty = True

        if self.layout_cache.gaps_may_be_dirty:
            self._compute_layout()

    def _compute_layout(self):
        """计算布局 — 虚拟 Y 坐标"""
        cache = self.layout_cache
        if not cache:
            return

        y = 0
        for i, entry in enumerate(self.entries):
            height = len(entry.render()) if not entry.collapsed else 1
            cache.virtual_y[i] = y
            cache.entry_heights[i] = height
            y += height

        cache.total_height = y
        cache.gaps_may_be_dirty = False


class TerminalPager:
    """
    终端 Pager — 完整渲染引擎.
    
    移植自 grok-build pager:
    - ScrollbackState 管理
    - Viewport 映射
    - Block 渲染
    - 键盘/鼠标输入
    """
    def __init__(self, viewport_height: int = 24):
        self.state = ScrollbackState(viewport_height=viewport_height)
        self._history: list[str] = []

    def push_text(self, text: str, role: str = "assistant"):
        """添加文本块"""
        block_type = {
            "user": BlockType.USER_PROMPT,
            "assistant": BlockType.TEXT,
            "tool": BlockType.TOOL_RESULT,
            "system": BlockType.SYSTEM,
            "error": BlockType.ERROR,
        }.get(role, BlockType.TEXT)
        
        self.state.push_entry(TextBlock(type=block_type, content=text))
        self.state.scroll_to(len(self.state.entries) - 1)  # 自动滚到最新

    def push_code(self, code: str, language: str = ""):
        """添加代码块"""
        prefix = f"```{language}\n" if language else "```\n"
        self.state.push_entry(TextBlock(
            type=BlockType.CODE,
            content=prefix + code + "\n```"
        ))

    def render_viewport(self) -> str:
        """渲染当前视口"""
        start, end = self.state.compute_paint_window()
        start = max(0, start)
        end = min(len(self.state.entries), end)

        lines = []
        for i in range(start, end):
            if i >= len(self.state.entries):
                break
            entry = self.state.entries[i]
            
            prefix = {
                BlockType.USER_PROMPT: "> ",
                BlockType.SYSTEM: "─ ",
                BlockType.ERROR: "✗ ",
                BlockType.TOOL_RESULT: "  ",
                BlockType.GOAL_PROGRESS: "◆ ",
            }.get(entry.type, "")
            
            for line in entry.render():
                lines.append(prefix + line)

        return "\n".join(lines)

    def handle_key(self, key: str):
        """处理按键"""
        if key in ("j", "down"):
            self.state.scroll_down()
        elif key in ("k", "up"):
            self.state.scroll_up()
        elif key in ("g", "home"):
            self.state.scroll_offset = 0
        elif key in ("G", "end"):
            self.state.scroll_offset = max(0, 
                (self.state.layout_cache.total_height - self.state.viewport_height) 
                if self.state.layout_cache else 0)
        elif key in ("/",):
            pass  # 搜索模式 (TODO)

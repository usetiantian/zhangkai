"""Full Pager Engine v2 — compute_paint_window + prepare_layout (移植自 grok-build scrollback)"""

from dataclasses import dataclass, field
from typing import Callable


@dataclass
class EntryLayoutInfo:
    """条目布局信息"""
    height: int = 0       # 渲染高度 (0=stub, 待测量)
    is_header: bool = False  # 组头
    collapsed: bool = False

    def is_group_header(self) -> bool:
        return self.is_header and not self.collapsed


@dataclass
class LayoutCacheData:
    """布局缓存"""
    virtual_y: list[int] = field(default_factory=list)
    layouts: list[EntryLayoutInfo] = field(default_factory=list)
    total_height: int = 0
    dirty_heights: set = field(default_factory=set)
    gaps_may_be_dirty: bool = True
    generation: int = 0


@dataclass
class PagerState:
    """完整 Pager 状态"""
    entries: list[dict] = field(default_factory=list)  # {type, content, height}
    cache: LayoutCacheData = field(default_factory=LayoutCacheData)
    viewport_height: int = 24
    viewport_width: int = 80
    scroll_offset: int = 0
    follow_mode: bool = True
    scroll_anchor: int | None = None
    selection: tuple[int, int] | None = None  # (start, end) entry indices
    last_width: int = 0
    generation: int = 0

    def invalidate_layout_cache(self):
        self.cache.gaps_may_be_dirty = True
        self.generation += 1
        self.cache.generation = self.generation

    def capture_scroll_anchor(self):
        """捕获滚动锚点 — 用于在重布局后恢复位置"""
        if not self.cache.layouts or not self.cache.virtual_y:
            self.scroll_anchor = None
            return
        vp_bounds = self.viewport_virtual_bounds()
        if vp_bounds:
            self.scroll_anchor = vp_bounds[0]  # 视口顶部虚拟Y

    def restore_scroll_anchor(self):
        """恢复滚动位置"""
        if self.scroll_anchor is None or not self.cache.virtual_y:
            return
        target = min(self.scroll_anchor,
                     max(0, self.cache.total_height - self.viewport_height))
        self.scroll_offset = target

    def viewport_virtual_bounds(self) -> tuple[int, int] | None:
        cache = self.cache
        if not cache.virtual_y or not cache.layouts:
            return None
        if not self.entries:
            return None
        base_y = cache.virtual_y[0] if cache.virtual_y else 0
        top = base_y + self.scroll_offset
        bottom = top + self.viewport_height
        return (top, bottom)

    def compute_paint_window(self) -> tuple[range, int]:
        """
        计算绘制窗口 (移植自 grok-build compute_paint_window).
        
        返回: (paint_start..paint_end, content_y0)
        """
        vy = self.cache.virtual_y
        layouts = self.cache.layouts
        if not vy or not layouts or not self.entries:
            return (range(0), 0)

        visible = range(len(self.entries))
        base_y = vy[visible.start]
        vp_start = base_y + self.scroll_offset
        vp_end = vp_start + self.viewport_height

        # binary search for first visible entry
        first_rel = 0
        for i, y in enumerate(vy[visible.start:visible.stop]):
            if y >= vp_start:
                first_rel = i
                break
            first_rel = i + 1

        if first_rel > 0:
            prev = visible.start + first_rel - 1
            if (prev < len(vy) and prev < len(layouts)
                    and vy[prev] + layouts[prev].height > vp_start):
                first_rel -= 1

        paint_start = visible.start + first_rel

        # find end
        paint_end_rel = 0
        for i, y in enumerate(vy[visible.start:visible.stop]):
            if y >= vp_end:
                paint_end_rel = i
                break
            paint_end_rel = i + 1

        paint_end = visible.start + paint_end_rel

        # Extend for group headers
        i = paint_start
        while i < paint_end and i < len(layouts):
            if (layouts[i].height > 0
                    and layouts[i].is_group_header()):
                run_end = paint_end
                for j in range(i, len(layouts)):
                    if layouts[j].is_group_header() and j > i:
                        break
                    run_end = j + 1
                paint_end = max(paint_end,
                                min(run_end, visible.stop))
            i += 1

        content_y0 = (vy[paint_start] - base_y
                      if paint_start < paint_end and paint_start < len(vy)
                      else 0)

        return (range(paint_start, paint_end), content_y0)

    def prepare_layout(self, width: int, height: int):
        """
        准备布局 (移植自 grok-build prepare_layout).
        
        核心逻辑:
        - 捕获滚动锚点
        - 检查宽度变化 → 失效缓存
        - 更新视口尺寸
        - 测量脏条目
        - 恢复滚动锚点
        """
        # 宽度变化检测
        if width != self.last_width and self.last_width > 0:
            self.invalidate_layout_cache()
        self.last_width = width
        self.viewport_width = width

        # 视口高度变化
        if height != self.viewport_height:
            self.invalidate_layout_cache()
        self.viewport_height = max(1, height)

        # 捕获锚点
        self.capture_scroll_anchor()

        # 确保布局缓存
        if self.cache.gaps_may_be_dirty or len(self.cache.layouts) != len(self.entries):
            self._compute_full_layout(width)

        # 测量脏条目
        if self.cache.dirty_heights:
            self._measure_dirty(width)
            self.cache.dirty_heights.clear()

        # 恢复锚点
        self.restore_scroll_anchor()

        # Follow mode: 自动滚到底部
        if self.follow_mode:
            max_offset = max(0, self.cache.total_height - self.viewport_height)
            self.scroll_offset = max_offset

    def _compute_full_layout(self, width: int):
        """计算完整布局"""
        cache = self.cache
        cache.virtual_y = []
        cache.layouts = []
        y = 0

        for entry in self.entries:
            height = entry.get("height", 1)
            if height <= 0:
                height = 1  # stub

            cache.virtual_y.append(y)
            cache.layouts.append(EntryLayoutInfo(
                height=height,
                is_header=entry.get("type") == "header",
            ))
            y += height

        cache.total_height = y
        cache.gaps_may_be_dirty = False
        self.cache.generation += 1

    def _measure_dirty(self, width: int):
        """测量脏条目的真实高度"""
        # 简化: 根据内容估算高度
        for idx in self.cache.dirty_heights:
            if idx < len(self.entries):
                content = self.entries[idx].get("content", "")
                lines = content.count("\n") + 1
                wrapped = (len(content) // max(1, width)) + lines
                self.entries[idx]["height"] = max(1, wrapped)

    def push_block(self, block: dict):
        """添加一个块 (移植自 grok-build push_block)"""
        self.entries.append(block)
        self.invalidate_layout_cache()

    def get_visible_blocks(self) -> list[dict]:
        """获取当前视口内的块"""
        window, _ = self.compute_paint_window()
        if not self.entries:
            return []
        start = max(0, window.start)
        end = min(len(self.entries), window.stop)
        return self.entries[start:end]

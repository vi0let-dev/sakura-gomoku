"""界面布局：按内容顺序自上而下排布，天然保证「文字与元素不重叠」。

核心是 Builder —— 用游标依次放置元素并保留最小间距。
如果内容放不下，finish() 会等比例压缩间距（但不低于各自的最小值），
仍然放不下就直接报错，方便在自检里发现（而不是让元素悄悄叠在一起）。
"""

from __future__ import annotations

import pygame

from .ui import SYM_ARROW, SYM_DOT, SYM_FLOWER, SYM_HEART, SYM_STAR, UiKit

# --------------------------------------------------------------------- 文案
TEXTS = {
    "title": "五子棋",
    "subtitle": "GOMOKU  ·  SAKURA",
    "jp_left": "ゴモク",
    "jp_right": "サクラ",
    "status_label": "战况 / STATUS",
    "move": "手数",
    "thinking": "思考中",
    "mode_section": "对局模式 / MODE",
    "level_section": "AI 难度 / LEVEL",
    "action_section": "操作 / COMMAND",
    "help_section": "快捷键 / SHORTCUT",
    "result_win": "获胜",
    "result_draw": "平局",
    "restart_hint": "R 再来一局   ·   U 悔棋",
    "black": "黑棋",
    "white": "白棋",
    "help": (
        "鼠标左键落子（可拖动微调）\n"
        "U 悔棋    R 重新开始    S 音效\n"
        "1 / 2 / 3 切换模式\n"
        "F1 / F2 / F3 切换难度    Esc 退出"
    ),
}

MODES = (
    ("pve", "人机对战", "YOU VS AI"),
    ("pvp", "双人对战", "PVP"),
    ("ai", "AI 对 AI", "AUTO"),
)
LEVELS = (("简单", "EASY"), ("普通", "NORMAL"), ("困难", "HARD"))
ACTIONS = (("undo", "悔棋", "UNDO"), ("restart", "重新开始", "RESET"))
TOGGLES = (("sound", "音效:开", "SFX"), ("quit", "退出", "EXIT"))

# 面板内容的最小可用区（保证按钮和文字仍然可读）
MIN_INNER_W = 214
MIN_INNER_H = 372
MARGIN = 22
BAND = 148          # 顶部标题区高度
GAP_H = 16          # 棋盘与面板的横向间距
SECTION_LABEL_GAP = 4   # 小节标题与其下按钮之间的固定空隙


class Button:
    """一个可点击区域。rect 由布局决定，渲染与命中检测只读它。"""

    __slots__ = ("bid", "label", "hint", "rect", "accent", "filled", "disabled", "tooltip")

    def __init__(self, bid: str, label: str, rect, *, hint: str = "", accent=None,
                 filled: bool = True, disabled: bool = False, tooltip: str = "") -> None:
        self.bid = bid
        self.label = label
        self.hint = hint
        self.rect = rect
        self.accent = accent
        self.filled = filled
        self.disabled = disabled
        self.tooltip = tooltip


class Builder:
    """竖向布局游标。

    元素分两类：
        * 流的元素（block）—— 依次向下排布，间距可被压缩；
        * 贴底元素（anchor）—— 固定在容器底部，不参与流式计算。
    finish() 会把两类都算进高度校验，因此不会出现「贴底元素压住上方内容」。
    """

    def __init__(self, kit: UiKit, rect, describe: str) -> None:
        self.kit = kit
        self.rect = rect
        self.describe = describe
        self.cursor = rect.y
        self.blocks: list[list] = []        # [名称, 顶部, 高度]
        self.gaps: list[list] = []          # [插入位置, 实际间距, 最小间距]
        self.anchored: list[list] = []      # 贴底元素（不参与流式排布）

    def _add(self, name: str, height: int, gap_min: int) -> int:
        if self.blocks:
            self.cursor += gap_min
        top = self.cursor
        self.gaps.append([len(self.blocks), gap_min, gap_min])
        self.blocks.append([name, top, height])
        self.cursor += height
        return top

    def label(self, text: str, *, size: int = 14, gap: int = 6) -> int:
        """放置一个小节标题，返回它占用的高度。"""
        height = self.kit.size_of(text, size)[1]
        self._add(f"label:{text}", height, gap)
        return height

    def box(self, name: str, height: int, gap: int = 8) -> pygame.Rect:
        top = self._add(name, height, gap)
        return pygame.Rect(self.rect.x, top, self.rect.w, height)

    def row(self, name: str, height: int, gap_before: int = 8, gap_after: int = 6) -> int:
        top = self._add(name, height, gap_before)
        self.gaps.append([len(self.blocks), gap_after, gap_after])
        self.cursor += gap_after
        return top

    def anchor(self, name: str, height: int, bottom: int) -> int:
        """把元素贴在容器底部（不参与流式排布，但计入高度校验）。"""
        top = bottom - height
        self.anchored.append([name, top, height])
        return top

    def finish(self) -> int:
        """压缩间距以适配容器；仍放不下则抛错。返回内容使用的高度。"""
        flow_h = sum(item[2] for item in self.blocks)
        fixed_h = sum(item[2] for item in self.anchored)
        min_sum = sum(g[2] for g in self.gaps)
        avail = self.rect.h

        if flow_h + min_sum > avail:
            raise AssertionError(
                f"面板内容放不下：{self.describe} 至少需要 {flow_h + min_sum}px，可用 {avail}px"
            )
        if flow_h + fixed_h + min_sum > avail:
            raise AssertionError(
                f"面板内容与底部元素冲突：{self.describe} 至少需要 "
                f"{flow_h + fixed_h + min_sum}px，可用 {avail}px"
            )

        # 压缩间距时，必须为上方的流内容与底部元素都留出位置
        limit = self.rect.bottom - fixed_h
        if flow_h >= limit - self.rect.y:
            for gap in self.gaps:       # 空间极紧：间距一律取最小值
                gap[1] = gap[2]
        elif self.cursor > limit:
            extra = sum(g[1] - g[2] for g in self.gaps)
            if extra > 0:
                keep = max(0.0, 1.0 - (self.cursor - limit) / extra)
                for gap in self.gaps:
                    gap[1] = gap[2] + int((gap[1] - gap[2]) * keep)
        cursor = self.rect.y
        for index, block in enumerate(self.blocks):
            if index > 0:
                cursor += self.gaps[index][1]
            block[1] = cursor
            cursor += block[2]
        self.cursor = cursor

        assert self.cursor <= self.rect.bottom - fixed_h + 1, (
            f"面板内容与底部元素重叠：{self.describe} 流内容占到 {self.cursor - self.rect.y}px，"
            f"底部元素还要 {fixed_h}px，总高只有 {avail}px"
        )
        # 返回「自然高度」（含最小间距），与是否压缩无关。
        # 这个值用来反推面板应该多高，所以必须是未压缩的。
        return flow_h + fixed_h + min_sum


def _min_panel_width(kit: UiKit, base: int) -> int:
    """三列按钮 + 文字留白所需的最小面板内容宽度。"""
    labels = [label for _, label, _ in MODES + ACTIONS + TOGGLES]
    widest = max(kit.size_of(label, max(11, base - 1))[0] for label in labels) + 18
    col_gap = max(8, int(base * 0.65))
    return max(MIN_INNER_W, widest, int(base * 4.4) * 3 + col_gap * 2)


def _base_for(kit: UiKit, inner_w: int) -> int:
    """在这个内容宽度下，找一个既能让文字放得下、又不至于过大的基准字号。"""
    for base in range(17, 12, -1):
        if _min_panel_width(kit, base) <= inner_w:
            return base
    return 13


def _choose_panel_w(win_w: int) -> int:
    """面板宽度随窗口变宽（内容随之变大），同时不超过窗口的 30%。"""
    wanted = int(win_w * 0.30)
    return max(MIN_INNER_W + 36, min(400, wanted))


def required_panel_size(kit: UiKit, panel_w: int, base: int) -> tuple[int, int]:
    """给定面板宽度与基准字号，返回内容所需的 (面板高, 内容高)。"""
    inner_w = panel_w - 36
    probe = pygame.Rect(0, 0, inner_w, 4000)
    used = _layout_panel(probe, kit, base=base)["used"]
    inner_h = max(MIN_INNER_H, used)
    return inner_h + 32, inner_h


def required_panel_height(kit: UiKit, panel_w: int) -> int:
    """面板高度由内容单独决定（与窗口高度无关）：宽度越小 → 字号越小 → 内容越矮。"""
    inner_w = panel_w - 36
    base = _base_for(kit, inner_w)
    return required_panel_size(kit, panel_w, base)[0]


def require(kit: UiKit, win_w: int, win_h: int) -> tuple[int, int]:
    """这个窗口尺寸下，布局真正需要的 (最小宽, 最小高)。"""
    panel_w = _choose_panel_w(win_w)
    panel_h = required_panel_height(kit, panel_w)
    board = max(360, min(win_h - BAND - MARGIN, win_w - panel_w - GAP_H - MARGIN * 2))
    min_w = MARGIN + board + GAP_H + panel_w + MARGIN
    min_h = max(panel_h + MARGIN * 2, BAND + board + MARGIN)
    return min_w, min_h


def page_size(kit: UiKit) -> tuple[int, int]:
    """能容纳全部内容的最小窗口尺寸，用于设定 MIN_WINDOW 与自检。"""
    width = 640
    height = 0
    while width < 3000:
        need_w, need_h = require(kit, width, 1 << 20)
        height = max(height, need_h)
        if need_w <= width:
            break
        width += 8
    return width, height


def compute_layout(win_w: int, win_h: int, kit: UiKit) -> dict:
    """计算整窗布局。窗口小于最小可用尺寸时会抛 AssertionError。"""
    panel_w = _choose_panel_w(win_w)
    board_size = min(win_h - BAND - MARGIN, win_w - panel_w - GAP_H - MARGIN * 2)
    board_size = max(360, board_size)

    board = pygame.Rect(MARGIN, BAND, board_size, board_size)
    scale = max(0.9, min(1.16, board_size / 664.0))
    inner_w = panel_w - 36
    base = _base_for(kit, inner_w)

    # 面板高度只看内容；画布高了就居中（留白），不把按钮拉散
    panel_h = required_panel_height(kit, panel_w)
    panel_y = max(MARGIN, (win_h - panel_h) // 2)
    panel = pygame.Rect(board.right + GAP_H, panel_y, panel_w, panel_h)

    inner = pygame.Rect(panel.x + 18, panel.y + 16, panel.w - 36, panel.h - 32)
    layout = _layout_panel(inner, kit, base=base)
    layout.update({
        "window": (win_w, win_h),
        "board": board,
        "panel": panel,
        "inner": inner,
        "header": pygame.Rect(board.x, MARGIN, board.w, BAND - MARGIN - 12),
        "base": base,
        "scale": scale,
        "needed_panel_h": panel_h,
    })
    return layout


def _layout_panel(inner: pygame.Rect, kit: UiKit, base: int) -> dict:
    """在给定内容区里排布面板内容，返回各元素矩形与按钮。"""
    b = Builder(kit, inner, "面板")
    label_size = max(11, base - 4)
    gap_row = max(9, int(base * 0.72))

    # 标题 + 副标题 + 霓虹条
    title_h = b._add("title", int(base * 2.6), 0)
    sub_h = b._add("subtitle", int(base * 1.15), 2)
    bar_h = b._add("titlebar", 3, 6)
    bar_rect = pygame.Rect(0, 0, min(inner.w, 92), 3)

    status_h = int(base * 4.9)
    status = b.box("status", status_h, int(base * 0.95))

    label_h = b.label(TEXTS["mode_section"], size=label_size, gap=gap_row)
    mode_top = b.row("modes", int(base * 2.6), gap_before=0, gap_after=gap_row)
    section_mode_top = mode_top - SECTION_LABEL_GAP - label_h

    label_h = b.label(TEXTS["level_section"], size=label_size, gap=gap_row)
    level_top = b.row("levels", int(base * 2.1), gap_before=0, gap_after=gap_row)
    section_level_top = level_top - SECTION_LABEL_GAP - label_h

    label_h = b.label(TEXTS["action_section"], size=label_size, gap=gap_row)
    action_top = b.row("actions", int(base * 2.5), gap_before=0, gap_after=gap_row)
    section_action_top = action_top - SECTION_LABEL_GAP - label_h

    toggle_top = b.row("toggles", int(base * 2.5), gap_before=0, gap_after=0)

    help_size = max(10, base - 4)
    help_lines = TEXTS["help"].split("\n")
    line_h = kit.size_of("汉", help_size)[1]
    help_h = line_h * len(help_lines) + 4 * (len(help_lines) - 1)
    help_label_h = kit.size_of(TEXTS["help_section"], label_size)[1]
    help_top = b.anchor("help", help_label_h + 6 + help_h, inner.bottom)
    used = b.finish()

    mode_h = int(base * 2.6)
    level_h = int(base * 2.1)
    action_h = toggle_h = int(base * 2.5)

    col_gap = max(8, int(base * 0.65))
    third = (inner.w - col_gap * 2) // 3
    half = (inner.w - col_gap) // 2

    buttons: dict[str, Button] = {}
    for i, (bid, label, hint) in enumerate(MODES):
        rect = pygame.Rect(inner.x + i * (third + col_gap), mode_top, third, mode_h)
        buttons[f"mode_{bid}"] = Button(f"mode_{bid}", label, rect, hint=hint)
    for i, (label, hint) in enumerate(LEVELS):
        rect = pygame.Rect(inner.x + i * (third + col_gap), level_top, third, level_h)
        buttons[f"level_{label}"] = Button(f"level_{label}", label, rect, hint=hint,
                                           filled=False, tooltip=hint)
    for i, (bid, label, hint) in enumerate(ACTIONS):
        rect = pygame.Rect(inner.x + i * (half + col_gap), action_top, half, action_h)
        buttons[bid] = Button(bid, label, rect, hint=hint)
    for i, (bid, label, hint) in enumerate(TOGGLES):
        rect = pygame.Rect(inner.x + i * (half + col_gap), toggle_top, half, toggle_h)
        buttons[bid] = Button(bid, label, rect, hint=hint)

    return {
        "buttons": buttons,
        "status_rect": status,
        "title_rect": pygame.Rect(inner.x, title_h, inner.w, int(base * 2.6)),
        "subtitle_rect": pygame.Rect(inner.x, sub_h, inner.w, int(base * 1.15)),
        "bar_rect": pygame.Rect(inner.centerx - 46, bar_h, 92, 3),
        "help_rect": pygame.Rect(inner.x, help_top + help_label_h + 6, inner.w, help_h),
        "help_label_rect": pygame.Rect(inner.x, help_top, inner.w, help_label_h),
        "sections": {
            "mode": (inner.x, section_mode_top),
            "level": (inner.x, section_level_top),
            "action": (inner.x, section_action_top),
            "help": (inner.x, help_top),
        },
        "used": used,
    }

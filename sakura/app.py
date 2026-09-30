"""app.py —— 樱花五子棋主程序（二次元风格 GUI）。

运行：
    python app.py            # 用默认的 conda 环境
    python -m sakura.app
"""

from __future__ import annotations

import math
import os
import random
import sys
import time

if __package__ in (None, ""):
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    __package__ = "sakura"

import pygame

from .ai import DEFAULT_LEVEL, LEVELS, GomokuAI
from .effects import Effects
from .game import BLACK, WHITE, Board
from .layout import (ACTIONS, LEVELS as LEVEL_ITEMS, MODES, TEXTS, Button,  # noqa: F401
                     compute_layout, page_size)
from .theme import (C, blit_glow, blit_round, font_info, load_font, radial_stone,
                    star_field, twinkle, vertical_gradient)
from .ui import SYM_ARROW, SYM_DOT, SYM_FLOWER, SYM_HEART, SYM_STAR, UiKit

os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

WINDOW_TITLE = "樱花五子棋 Sakura Gomoku"
DEFAULT_WINDOW = (1010, 840)
FALLBACK_MIN = (860, 700)
FPS = 60
AI_MIN_DELAY = 0.22            # “思考中”至少显示这么久


def build_sounds() -> dict:
    """正弦波合成音效（落子 / 胜利 / 点击），不依赖外部音频文件。"""
    if not pygame.mixer.get_init():
        return {}
    try:
        rate = pygame.mixer.get_init()[0]
        out = {}
        specs = (
            ("place", 880.0, 0.075, 0.30, 0.0),
            ("win", 1180.0, 0.55, 0.34, 3.0),
            ("click", 620.0, 0.045, 0.22, 0.0),
        )
        for name, freq, dur, amp, glide in specs:
            frames = int(rate * dur)
            data = bytearray()
            for i in range(frames):
                t = i / rate
                f = freq * (1.0 + glide * t / max(dur, 1e-6))
                fade = math.exp(-5.5 * t / dur)
                value = int(32767 * amp * fade * math.sin(2 * math.pi * f * t))
                data += max(-32767, min(32767, value)).to_bytes(2, "little", signed=True) * 2
            out[name] = pygame.mixer.Sound(buffer=bytes(data))
        return out
    except Exception:
        return {}


class App:
    def __init__(self, size: tuple[int, int] = DEFAULT_WINDOW) -> None:
        pygame.mixer.pre_init(44100, -16, 2, 512)
        pygame.init()
        pygame.display.set_caption(WINDOW_TITLE)

        self.window = pygame.display.set_mode(size, pygame.RESIZABLE)
        self.kit = UiKit()
        self.min_size = self._probe_min_size()

        try:
            pygame.display.set_icon(self._make_icon())
        except pygame.error:
            pass

        self.board = Board()
        self.ai = GomokuAI(DEFAULT_LEVEL)
        self.effects = Effects(size)
        self.sounds = build_sounds()

        self.mode = "pve"
        self.human_player = BLACK
        self.level = DEFAULT_LEVEL
        self.sound_on = True

        self.hover = None
        self.press_origin = None
        self.thinking = False
        self.think_since = 0.0
        self.notice = ""
        self.notice_until = 0.0
        self.glow_stones: dict[tuple[int, int], float] = {}
        self.running = True
        self._bg: pygame.Surface | None = None
        self._bg_key = None
        self._board_bg: pygame.Surface | None = None
        self._board_key = None

        self.rebuild_layout()

    # ================================================================ 初始化
    def _probe_min_size(self) -> tuple[int, int]:
        try:
            width, height = page_size(self.kit)
        except Exception:
            return FALLBACK_MIN
        return max(FALLBACK_MIN[0], width), max(FALLBACK_MIN[1], height)

    @staticmethod
    def _make_icon() -> pygame.Surface:
        icon = pygame.Surface((64, 64), pygame.SRCALPHA)
        pygame.draw.rect(icon, (46, 30, 68), icon.get_rect(), border_radius=14)
        pygame.draw.rect(icon, C["sakura"], icon.get_rect(), width=2, border_radius=14)
        for i in range(4):
            pygame.draw.line(icon, (150, 130, 210), (14 + i * 12, 12), (14 + i * 12, 52), 1)
            pygame.draw.line(icon, (150, 130, 210), (12, 14 + i * 12), (52, 14 + i * 12), 1)
        icon.blit(radial_stone(30, C["black_stone_hi"], C["black_stone_lo"], light=(-5, -6)), (8, 8))
        icon.blit(radial_stone(26, C["white_stone_hi"], C["white_stone_lo"], light=(-4, -5)), (30, 30))
        return icon

    def rebuild_layout(self) -> None:
        win_w, win_h = self.window.get_size()
        self.layout = compute_layout(win_w, win_h, self.kit)
        self.buttons = self.layout["buttons"]
        self.scale = self.layout["scale"]

    def _background(self) -> pygame.Surface:
        key = self.window.get_size()
        if self._bg is not None and self._bg_key == key:
            return self._bg
        bg = vertical_gradient(key, C["bg_top"], C["bg_bottom"]).copy()
        # 柔和的极光斑块
        aurora = pygame.Surface(key, pygame.SRCALPHA)
        width, height = key
        for cx, cy, radius, color, alpha in (
            (width * 0.18, height * 0.22, int(height * 0.42), C["violet_deep"], 46),
            (width * 0.86, height * 0.16, int(height * 0.36), C["sakura_deep"], 38),
            (width * 0.62, height * 0.92, int(height * 0.40), C["cyan_deep"], 26),
        ):
            blit_glow(aurora, (cx, cy), radius, color, alpha)
        bg.blit(aurora, (0, 0))
        bg.blit(star_field(key), (0, 0))
        self._bg, self._bg_key = bg, key
        return bg

    # ================================================================ 音效 / 提示
    def play(self, name: str) -> None:
        if not self.sound_on:
            return
        sound = self.sounds.get(name)
        if sound is not None:
            try:
                sound.play()
            except Exception:
                pass

    def set_notice(self, text: str, seconds: float = 2.4) -> None:
        self.notice = text
        self.notice_until = time.monotonic() + seconds

    # ================================================================ 对局操作
    def reset_game(self) -> None:
        self.board.reset()
        self.thinking = False
        self.notice = ""
        self.glow_stones.clear()
        self.ai.rng.seed(random.randrange(1 << 30))

    def commit_move(self, row: int, col: int, player: int) -> bool:
        if not self.board.place(row, col, player):
            return False
        self.play("place")
        self.glow_stones[(row, col)] = 0.0
        pos = self.cell_to_px(row, col)
        self.effects.burst(pos, 12, spread=110,
                           color=C["cyan"] if player == BLACK else C["sakura_soft"])
        if self.board.winner:
            self.play("win")
            name = TEXTS["black"] if player == BLACK else TEXTS["white"]
            self.set_notice(f"{name}{TEXTS['result_win']}", 4.0)
            for r, c in self.board.winning_line:
                self.effects.burst(self.cell_to_px(r, c), 10, spread=170, big=True)
        elif self.board.game_over:
            self.set_notice(TEXTS["result_draw"], 4.0)
        return True

    def human_can_move(self) -> bool:
        if self.board.game_over or self.thinking:
            return False
        if self.mode == "ai":
            return False
        if self.mode == "pve" and self.board.current != self.human_player:
            return False
        return True

    def ai_turn(self) -> None:
        if self.board.game_over:
            self.thinking = False
            return
        if not self.thinking:
            self.thinking = True
            self.think_since = time.monotonic()
            return
        if time.monotonic() - self.think_since < AI_MIN_DELAY:
            return
        move = self.ai.choose_move(self.board, self.board.current)
        self.thinking = False
        if move is not None:
            self.commit_move(move[0], move[1], self.board.current)

    def maybe_ai(self) -> None:
        if self.board.game_over:
            return
        if self.mode == "ai" or (self.mode == "pve" and self.board.current != self.human_player):
            self.ai_turn()

    def undo(self) -> None:
        if self.thinking:
            self.set_notice("电脑思考中，稍等一下")
            return
        if not self.board.history:
            self.set_notice("还没有落子")
            return
        steps = 1 if self.mode in ("pvp", "ai") else 2
        undone = self.board.undo(min(steps, len(self.board.history)))
        if self.mode == "pve" and self.board.current != self.human_player and self.board.history:
            undone += self.board.undo(1)
        self.glow_stones.clear()
        self.set_notice(f"已悔棋 {undone} 步")

    def set_mode(self, mode: str) -> None:
        self.mode = mode
        self.reset_game()

    def set_level(self, level: str) -> None:
        self.level = level
        self.ai.set_level(level)
        self.set_notice(f"AI 难度：{level}")

    def dispatch(self, bid: str) -> None:
        self.play("click")
        if bid.startswith("mode_"):
            self.set_mode(bid.split("_", 1)[1])
        elif bid.startswith("level_"):
            self.set_level(bid.split("_", 1)[1])
        elif bid == "undo":
            self.undo()
        elif bid == "restart":
            self.reset_game()
            self.set_notice("新的对局开始")
        elif bid == "sound":
            self.sound_on = not self.sound_on
            self.set_notice("音效已" + ("开启" if self.sound_on else "关闭"))
        elif bid == "quit":
            self.running = False

    # ================================================================ 坐标换算
    def cell_to_px(self, row: int, col: int):
        board = self.layout["board"]
        cell, origin = self._grid()
        return int(round(origin[0] + col * cell)), int(round(origin[1] + row * cell))

    def _grid(self) -> tuple[float, tuple[float, float]]:
        """返回 (格子边长, 左上角第一个交叉点的坐标)。"""
        board = self.layout["board"]
        pad = board.w * 0.092
        cell = (board.w - pad * 2) / (15 - 1)
        return cell, (board.x + pad, board.y + pad)

    def px_to_cell(self, pos):
        cell, origin = self._grid()
        col = round((pos[0] - origin[0]) / cell)
        row = round((pos[1] - origin[1]) / cell)
        if not (0 <= row < 15 and 0 <= col < 15):
            return None
        px, py = self.cell_to_px(row, col)
        if math.hypot(pos[0] - px, pos[1] - py) > cell * 0.62:
            return None
        return row, col

    # ================================================================ 事件
    def handle_event(self, event) -> None:
        if event.type == pygame.QUIT:
            self.running = False

        elif event.type == pygame.VIDEORESIZE:
            w = max(self.min_size[0], event.w)
            h = max(self.min_size[1], event.h)
            self.window = pygame.display.set_mode((w, h), pygame.RESIZABLE)
            self.rebuild_layout()
            self.effects.resize((w, h))

        elif event.type == pygame.KEYDOWN:
            self._on_key(event.key)

        elif event.type == pygame.MOUSEMOTION:
            self.hover = self.px_to_cell(event.pos)

        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            hit = self._hit(event.pos)
            if hit is not None:
                self.dispatch(hit)
                return
            if self.layout["board"].collidepoint(event.pos):
                cell = self.px_to_cell(event.pos)
                if cell and self.board.is_empty(*cell):
                    self.press_origin = event.pos

        elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            if self.press_origin is not None:
                self.press_origin = None
                if not self.human_can_move():
                    if self.mode == "ai":
                        self.set_notice("AI 对局进行中")
                    return
                cell = self.px_to_cell(event.pos)
                if cell is None:
                    return
                row, col = cell
                if not self.board.is_empty(row, col):
                    self.set_notice("这里已经有棋子了")
                    return
                self.commit_move(row, col, self.board.current)

    def _on_key(self, key: int) -> None:
        if key in (pygame.K_ESCAPE, pygame.K_q):
            self.running = False
        elif key == pygame.K_r:
            self.reset_game()
            self.set_notice("新的对局开始")
        elif key == pygame.K_u:
            self.undo()
        elif key == pygame.K_s:
            self.sound_on = not self.sound_on
            self.set_notice("音效已" + ("开启" if self.sound_on else "关闭"))
        elif key in (pygame.K_1, pygame.K_2, pygame.K_3):
            self.set_mode(MODES[key - pygame.K_1][0])
        elif key in (pygame.K_F1, pygame.K_F2, pygame.K_F3):
            self.set_level(LEVEL_ITEMS[key - pygame.K_F1][0])

    def _hit(self, pos) -> str | None:
        for bid, button in self.buttons.items():
            if button.rect.collidepoint(pos) and not button.disabled:
                return bid
        return None

    # ================================================================ 渲染
    def draw(self, dt: float) -> None:
        t = self.effects.elapsed + dt
        mouse = pygame.mouse.get_pos()
        self.window.blit(self._background(), (0, 0))
        self.effects.draw_petals(self.window)
        self._draw_header(t)
        self._draw_board(t, dt)
        self._draw_panel(t, mouse)
        self.effects.draw_sparks(self.window)
        self._draw_notice(t)
        self._draw_banner(t)
        self._draw_tooltip(mouse)
        pygame.display.flip()

    # ---------------------------------------------------------------- 顶部标题
    def _draw_header(self, t: float) -> None:
        rect = self.layout["header"]
        pulse = twinkle(t, 2.0)
        # 三个互不重叠的槽位：左（日文）· 中（中文标题 + 副标题）· 右（日文）
        left_w = int(rect.w * 0.13)
        right_w = int(rect.w * 0.13)
        mid = pygame.Rect(rect.x + left_w, rect.y, rect.w - left_w - right_w, rect.h)

        self.kit.slot(self.window, TEXTS["jp_left"], pygame.Rect(rect.x, rect.y, left_w, int(rect.h * 0.5)),
                      size=int(17 * self.scale), color=C["sakura"], glow=7, align="left")
        self.kit.slot(self.window, TEXTS["jp_right"], pygame.Rect(rect.right - right_w, rect.y, right_w, int(rect.h * 0.5)),
                      size=int(17 * self.scale), color=C["cyan"], glow=7, align="right")

        title_slot = pygame.Rect(mid.x, mid.y + 2, mid.w, int(mid.h * 0.62))
        self.kit.slot(self.window, TEXTS["title"], title_slot, size=int(40 * self.scale),
                      color=C["ink"], glow=10, glow_color=C["sakura"], min_size=22)
        sub_slot = pygame.Rect(mid.x, title_slot.bottom + 2, mid.w, int(mid.h * 0.24))
        self.kit.slot(self.window, TEXTS["subtitle"], sub_slot, size=int(13 * self.scale),
                      color=C["ink_faint"], latin=True, min_size=10)

        # 霓虹装饰条（在副标题下方，位于标题块内部）
        bar_y = sub_slot.bottom + 4
        bar_w = int(mid.w * 0.5)
        bar = pygame.Rect(mid.centerx - bar_w // 2, bar_y, bar_w, 3)
        blit_round(self.window, bar, 2, (*C["sakura"][:3], int(150 + 90 * pulse)))
        blit_round(self.window, bar.inflate(0, 1), 2, (*C["sakura"][:3], 200))
        # 两侧小菱形
        for sign in (-1, 1):
            cx = bar.centerx + sign * (bar_w // 2 + 12)
            diamond = self.kit.render(SYM_STAR, int(13 * self.scale), C["gold"], glow=int(4 + 5 * pulse))
            self.window.blit(diamond, (cx - diamond.get_width() // 2, bar.centery - diamond.get_height() // 2))

    # ---------------------------------------------------------------- 棋盘
    def _board_surface(self) -> pygame.Surface:
        board = self.layout["board"]
        key = board.size
        if self._board_bg is not None and self._board_key == key:
            return self._board_bg

        size = board.w
        surf = pygame.Surface((size, size), pygame.SRCALPHA)
        radius = int(size * 0.045)
        # 盘面：暮紫玻璃 + 描边
        fill = pygame.Surface((size, size), pygame.SRCALPHA)
        for y in range(size):
            k = y / max(1, size - 1)
            color = (
                int(78 + 26 * (1 - k)),
                int(58 + 20 * (1 - k)),
                int(112 + 30 * (1 - k)),
                214,
            )
            pygame.draw.line(fill, color, (0, y), (size, y))
        mask = pygame.Surface((size, size), pygame.SRCALPHA)
        pygame.draw.rect(mask, (255, 255, 255, 255), mask.get_rect(), border_radius=radius)
        fill.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MIN)
        surf.blit(fill, (0, 0))

        cell, origin = self._grid()
        ox, oy = origin[0] - board.x, origin[1] - board.y
        last = cell * 14
        # 网格
        for i in range(15):
            edges = i in (0, 14)
            color = (*C["grid"][:3], 190 if edges else 92)
            width = 2 if edges else 1
            pygame.draw.line(surf, color, (ox, oy + i * cell), (ox + last, oy + i * cell), width)
            pygame.draw.line(surf, color, (ox + i * cell, oy), (ox + i * cell, oy + last), width)
        # 星位
        for r, c in ((3, 3), (3, 11), (11, 3), (11, 11), (7, 7)):
            pos = (int(ox + c * cell), int(oy + r * cell))
            pygame.draw.circle(surf, (*C["cyan"][:3], 210), pos, max(3, int(cell * 0.10)))

        # 四角装饰
        corner = max(10, int(size * 0.05))
        for cx, cy, dx, dy in ((6, 6, 1, 1), (size - 7, 6, -1, 1),
                               (6, size - 7, 1, -1), (size - 7, size - 7, -1, -1)):
            pygame.draw.line(surf, (*C["sakura"][:3], 220), (cx, cy), (cx + dx * corner, cy), 2)
            pygame.draw.line(surf, (*C["sakura"][:3], 220), (cx, cy), (cx, cy + dy * corner), 2)

        pygame.draw.rect(surf, (*C["violet"][:3], 120), surf.get_rect(), width=2, border_radius=radius)
        self._board_bg, self._board_key = surf, key
        return surf

    def _draw_board(self, t: float, dt: float) -> None:
        board = self.layout["board"]
        cell, _ = self._grid()
        radius = int(cell * 0.44)
        stone_size = radius * 2

        blit_glow(self.window, board.center, board.w // 2 + 20, C["violet_deep"], int(26 + 18 * twinkle(t, 1.4)))
        self.window.blit(self._board_surface(), board.topleft)

        winning = set(self.board.winning_line)
        for row, col, player in self.board.history:
            pos = self.cell_to_px(row, col)
            age = self.glow_stones.get((row, col))
            pop = min(1.0, (age if age is not None else 1.0) / 0.16)
            scale = 0.55 + 0.45 * pop

            if (row, col) in winning:
                pulse = twinkle(t, 4.0)
                blit_glow(self.window, pos, int(radius * 2.2), C["gold"], int(70 + 70 * pulse))

            blit_glow(self.window, pos + (2, 3), int(radius * 1.3), (8, 6, 18), 120)
            if player == BLACK:
                base = radial_stone(stone_size, C["black_stone_hi"], C["black_stone_lo"], light=(-4, -5))
                rim = C["cyan"]
                rim_alpha = int(120 + 70 * twinkle(t, 2.2, row * 0.7 + col))
            else:
                base = radial_stone(stone_size, C["white_stone_hi"], C["white_stone_lo"], light=(-4, -5))
                rim = C["sakura_soft"]
                rim_alpha = int(120 + 70 * twinkle(t, 2.2, row * 1.3 + col * 0.5))
            if scale < 1.0:
                base = pygame.transform.smoothscale(base, (max(2, int(stone_size * scale)),) * 2)
            self.window.blit(base, (pos[0] - base.get_width() // 2, pos[1] - base.get_height() // 2))

            ring = pygame.Surface((stone_size + 6, stone_size + 6), pygame.SRCALPHA)
            pygame.draw.circle(ring, (*rim[:3], rim_alpha), (ring.get_width() // 2, ring.get_height() // 2),
                               radius, 2)
            self.window.blit(ring, (pos[0] - ring.get_width() // 2, pos[1] - ring.get_height() // 2))

            if age is not None:
                self.glow_stones[(row, col)] = age + dt

        # 最后一手标记
        last = self.board.last_move
        if last and not self.board.winning_line:
            pos = self.cell_to_px(last[0], last[1])
            dot = max(3, int(cell * 0.11))
            pygame.draw.circle(self.window, C["sakura"], pos, dot)
            pygame.draw.circle(self.window, (255, 255, 255, 200), pos, dot, 1)

        # 悬停预览
        if (self.hover and not self.board.game_over and self.human_can_move()
                and self.board.is_empty(*self.hover)):
            row, col = self.hover
            pos = self.cell_to_px(row, col)
            size = int(cell * 1.5)
            guide = pygame.Surface((size, size), pygame.SRCALPHA)
            mid = size // 2
            pygame.draw.line(guide, (*C["cyan"][:3], 110), (mid, 0), (mid, size), 2)
            pygame.draw.line(guide, (*C["cyan"][:3], 110), (0, mid), (size, mid), 2)
            self.window.blit(guide, (pos[0] - mid, pos[1] - mid))
            player = self.board.current
            ghost = (radial_stone(stone_size, C["black_stone_hi"], C["black_stone_lo"], light=(-4, -5))
                     if player == BLACK else
                     radial_stone(stone_size, C["white_stone_hi"], C["white_stone_lo"], light=(-4, -5)))
            ghost = ghost.copy()
            ghost.set_alpha(120)
            self.window.blit(ghost, (pos[0] - stone_size // 2, pos[1] - stone_size // 2))

        # 胜利连线
        if len(self.board.winning_line) >= 2:
            pts = [self.cell_to_px(r, c) for r, c in self.board.winning_line]
            pulse = twinkle(t, 3.2)
            layer = pygame.Surface(self.window.get_size(), pygame.SRCALPHA)
            pygame.draw.line(layer, (*C["gold"][:3], int(120 + 110 * pulse)), pts[0], pts[-1],
                             max(3, int(cell * 0.16)))
            self.window.blit(layer, (0, 0))

    # ---------------------------------------------------------------- 右侧面板
    def _draw_panel(self, t: float, mouse) -> None:
        panel = self.layout["panel"]
        inner = self.layout["inner"]
        self.kit.glass(self.window, panel, radius=24, glow=64, glow_color=C["violet_deep"])
        self.kit.neon_bar(self.window, self.layout["bar_rect"], C["sakura"], radius=2, glow=70)

        # 标题
        self.kit.slot(self.window, TEXTS["title"], self.layout["title_rect"],
                      size=int(34 * self.scale), color=C["ink"], glow=12, glow_color=C["sakura"],
                      min_size=22)
        self.kit.slot(self.window, TEXTS["subtitle"], self.layout["subtitle_rect"],
                      size=max(10, int(12 * self.scale)), color=C["ink_faint"], latin=True, min_size=9)

        self._draw_status(t)
        self._draw_sections()
        self._draw_buttons(t, mouse)
        self._draw_help()

    def _draw_status(self, t: float) -> None:
        rect = self.layout["status_rect"]
        board = self.board
        if board.game_over:
            if board.winner:
                label = f"{TEXTS['black'] if board.winner == BLACK else TEXTS['white']}{TEXTS['result_win']}"
                color = C["gold"]
            else:
                label, color = TEXTS["result_draw"], C["ink"]
        else:
            label = f"{TEXTS['black'] if board.current == BLACK else TEXTS['white']}回合"
            color = C["sakura"] if board.current == BLACK else C["cyan"]

        blit_round(self.window, rect, 16, (26, 20, 46, 170))
        pygame.draw.rect(self.window, (*C["glass_line"][:3], 110), rect, width=1, border_radius=16)
        blit_round(self.window, pygame.Rect(rect.x, rect.y + 10, 3, rect.h - 20), 2, color)

        # 严格三行槽位：标签 / 大字 / 底部信息行（各自独占一条带，绝不相压）
        pad = 14
        stone_room = 54
        row_h = rect.h // 3
        label_slot = pygame.Rect(rect.x + pad, rect.y + 4, rect.w - pad * 2 - stone_room, row_h - 4)
        main_slot = pygame.Rect(rect.x + pad, rect.y + row_h, rect.w - pad * 2 - stone_room, row_h)
        info_slot = pygame.Rect(rect.x + pad, rect.y + row_h * 2, rect.w - pad * 2, row_h - 2)

        self.kit.slot(self.window, TEXTS["status_label"], label_slot,
                      size=max(9, int(11 * self.scale)), color=C["ink_faint"], align="left",
                      axis="bottom", min_size=9)
        self.kit.slot(self.window, label, main_slot, size=int(20 * self.scale), color=color,
                      glow=4, glow_color=color, align="left", min_size=13)

        # 右侧回合指示球
        cx, cy = rect.right - 30, rect.y + row_h + row_h // 2
        radius = max(9, int(13 * self.scale))
        if not board.game_over:
            stone_size = radius * 2
            stone = (radial_stone(stone_size, C["black_stone_hi"], C["black_stone_lo"], light=(-3, -4))
                     if board.current == BLACK else
                     radial_stone(stone_size, C["white_stone_hi"], C["white_stone_lo"], light=(-3, -4)))
            blit_glow(self.window, (cx, cy), radius * 2, color, int(50 + 40 * twinkle(t, 2.4)))
            self.window.blit(stone, (cx - radius, cy - radius))

        # 底部信息行：手数 + 思考状态，顺序排布，超出就不画
        size = max(10, int(12 * self.scale))
        move = f"{TEXTS['move']} {board.move_count}"
        move_rect = self.kit.slot(self.window, move, info_slot, size=size, color=C["ink_dim"],
                                  align="left", min_size=10)
        if self.thinking:
            dots = SYM_DOT * (1 + int(twinkle(t, 3.0) * 3))
            rest = pygame.Rect(move_rect.right + 12, info_slot.y, info_slot.right - move_rect.right - 12, info_slot.h)
            if rest.w > 40:
                self.kit.slot(self.window, f"{TEXTS['thinking']}{dots}", rest, size=size,
                              color=C["mint"], align="left", min_size=9)

    def _draw_sections(self) -> None:
        sections = self.layout["sections"]
        for key, text in (("mode", TEXTS["mode_section"]), ("level", TEXTS["level_section"]),
                          ("action", TEXTS["action_section"])):
            x, y = sections[key]
            self.kit.section(self.window, text, x, y, self.layout["inner"].w,
                             color=C["violet"] if key != "action" else C["cyan"])

    def _draw_buttons(self, t: float, mouse) -> None:
        accent_map = {
            "mode_pve": C["sakura"], "mode_pvp": C["cyan"], "mode_ai": C["violet"],
            "undo": C["violet"], "restart": C["sakura"],
            "sound": C["mint"], "quit": C["danger"],
        }
        for bid, button in self.buttons.items():
            hover = button.rect.collidepoint(mouse) and not button.disabled
            accent = button.accent or accent_map.get(bid, C["sakura"])
            active = False
            if bid.startswith("mode_"):
                active = self.mode == bid.split("_", 1)[1]
            elif bid.startswith("level_"):
                active = self.level == bid.split("_", 1)[1]
            elif bid == "sound":
                button.label = "音效:开" if self.sound_on else "音效:关"
            elif bid == "undo":
                button.disabled = not self.board.history or self.thinking

            if button.filled:
                self.kit.button(self.window, button.rect, button.label, active=active, hover=hover,
                                disabled=button.disabled, t=t, accent=accent, sub=button.hint)
            else:
                self.kit.pill(self.window, button.rect, text=button.label,
                              size=self.kit.fit_size(button.label, button.rect.w - 16, 15, 10),
                              color=C["ink"] if active else C["ink_dim"],
                              fill=(accent[0] // 3 + 34, accent[1] // 4 + 26, accent[2] // 3 + 56, 225) if active
                              else C["glass_soft"],
                              edge=accent if active else C["glass_line"],
                              glow=int(30 + 30 * twinkle(t, 2.6)) if active else 0)

    def _draw_help(self) -> None:
        x, y = self.layout["sections"]["help"]
        self.kit.section(self.window, TEXTS["help_section"], x, y, self.layout["inner"].w, color=C["gold"])
        rect = self.layout["help_rect"]
        self.kit.draw_paragraph(self.window, TEXTS["help"], rect,
                                size=max(10, int(12 * self.scale)), color=C["ink_faint"])

    # ---------------------------------------------------------------- 浮层
    def _draw_notice(self, t: float) -> None:
        if not self.notice or time.monotonic() > self.notice_until:
            return
        board = self.layout["board"]
        size = max(11, int(13 * self.scale))
        text_w, text_h = self.kit.size_of(self.notice, size)
        pad_x, pad_y = 20, 10
        rect = pygame.Rect(0, 0, text_w + pad_x * 2, text_h + pad_y * 2)
        rect.midbottom = (board.centerx, board.bottom - 10)
        rect.clamp_ip(pygame.Rect(0, 0, *self.window.get_size()))
        blit_round(self.window, rect, rect.h // 2, (24, 18, 44, 228))
        pygame.draw.rect(self.window, (*C["sakura"][:3], 170), rect, width=1, border_radius=rect.h // 2)
        self.kit.slot(self.window, self.notice, rect, size=size, color=C["ink"], glow=4,
                      glow_color=C["sakura"], min_size=11)

    def _draw_banner(self, t: float) -> None:
        board = self.board
        if not board.game_over:
            return
        board_rect = self.layout["board"]
        size = max(16, int(24 * self.scale))
        if board.winner:
            name = TEXTS["black"] if board.winner == BLACK else TEXTS["white"]
            text = f"{name} {TEXTS['result_win']}"
            color = C["gold"]
        else:
            text, color = TEXTS["result_draw"], C["ink"]

        sub_size = max(10, int(12 * self.scale))
        text_w, text_h = self.kit.size_of(text, size)
        sub_w, sub_h = self.kit.size_of(TEXTS["restart_hint"], sub_size)
        w = max(text_w, sub_w) + 64
        h = text_h + sub_h + 42
        rect = pygame.Rect(0, 0, min(w, board_rect.w - 24), h)
        rect.center = (board_rect.centerx, board_rect.y + int(board_rect.h * 0.3))
        self.kit.glass(self.window, rect, radius=20, glow=80, glow_color=color)
        pulse = twinkle(t, 3.0)
        pygame.draw.rect(self.window, (*color[:3], int(150 + 90 * pulse)), rect, width=2, border_radius=20)
        self.kit.slot(self.window, text, pygame.Rect(rect.x, rect.y + 12, rect.w, text_h + 4),
                      size=size, color=color, glow=14, glow_color=color, min_size=15)
        self.kit.slot(self.window, TEXTS["restart_hint"],
                      pygame.Rect(rect.x, rect.bottom - sub_h - 14, rect.w, sub_h + 4),
                      size=sub_size, color=C["ink_dim"], min_size=9)

    def _draw_tooltip(self, mouse) -> None:
        for button in self.buttons.values():
            if button.tooltip and button.rect.collidepoint(mouse):
                size = max(10, int(11 * self.scale))
                text_w, text_h = self.kit.size_of(button.tooltip, size, latin=True)
                pad = 10
                rect = pygame.Rect(0, 0, text_w + pad * 2, text_h + pad)
                rect.midtop = (button.rect.centerx, button.rect.top - rect.h - 6)
                if rect.left < 4:
                    rect.left = 4
                if rect.right > self.window.get_width() - 4:
                    rect.right = self.window.get_width() - 4
                if rect.top < 4:
                    rect.top = button.rect.bottom + 6
                blit_round(self.window, rect, 8, (22, 16, 40, 234))
                pygame.draw.rect(self.window, (*C["cyan"][:3], 140), rect, width=1, border_radius=8)
                self.kit.slot(self.window, button.tooltip, rect, size=size, color=C["ink_dim"],
                              latin=True, min_size=9)
                return

    # ================================================================ 主循环
    def run(self) -> None:
        clock = pygame.time.Clock()
        while self.running:
            dt = min(0.05, clock.tick(FPS) / 1000.0)
            for event in pygame.event.get():
                self.handle_event(event)
            self.maybe_ai()
            self.effects.update(dt)
            self.draw(dt)
        pygame.quit()


def main() -> int:
    info = font_info()
    if os.environ.get("SAKURA_DEBUG"):
        print("fonts:", {k: (os.path.basename(v) if v else None) for k, v in info.items()})
    app = App()
    if os.environ.get("SAKURA_DEBUG"):
        print("window:", app.window.get_size(), "min:", app.min_size)
    app.run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

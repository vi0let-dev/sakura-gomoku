"""二次元风格配色、字体与绘制工具。

设计要点：
    * 字体分两套 —— 中日文（含假名）用 Noto Sans SC，
      拉丁字母/数字/符号用 Segoe UI，避免出现豆腐块。
    * 所有字号都支持“按可用宽度自动缩小”，从字体层面杜绝文字溢出。
    * 发光、柔光面板、渐变棋子都做了缓存，保证 60 FPS。
"""

from __future__ import annotations

import math
import os
import random

import pygame

# --------------------------------------------------------------------- 配色
# 暮色紫罗兰 + 樱花粉 + 磷光青，典型的视觉小说 / 二次元 UI 取色
C = {
    "bg_top": (24, 20, 42),
    "bg_bottom": (58, 34, 74),
    "bg_deep": (15, 12, 28),

    "glass": (46, 38, 74, 168),
    "glass_soft": (255, 255, 255, 14),
    "glass_line": (176, 158, 230, 90),
    "glass_hi": (255, 255, 255, 46),
    "shadow": (10, 8, 20, 160),

    "ink": (245, 240, 255),
    "ink_dim": (196, 186, 224),
    "ink_faint": (142, 133, 176),

    "sakura": (255, 150, 196),
    "sakura_soft": (255, 196, 220),
    "sakura_deep": (222, 92, 148),
    "cyan": (126, 232, 255),
    "cyan_deep": (64, 176, 232),
    "violet": (180, 148, 255),
    "violet_deep": (122, 92, 216),
    "gold": (255, 214, 128),
    "mint": (150, 244, 202),
    "danger": (255, 132, 158),

    "black_stone_hi": (118, 108, 178),
    "black_stone_lo": (26, 20, 48),
    "white_stone_hi": (255, 253, 255),
    "white_stone_lo": (206, 198, 232),
    "grid": (178, 160, 232),
}

# --------------------------------------------------------------------- 字体
FONT_DIR = os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts")

# 中日文字体：Noto Sans SC 覆盖全部简繁与假名；其余按顺序回退
CJK_FONTS = (
    "NotoSansSC-VF.ttf",
    "msyhbd.ttc",
    "simhei.ttf",
    "Dengb.ttf",
    "YuGothB.ttc",
)
CJK_REGULAR_FONTS = (
    "NotoSansSC-VF.ttf",
    "msyh.ttc",
    "simhei.ttf",
    "Deng.ttf",
    "YuGothM.ttc",
)
# 拉丁/数字/符号
LATIN_FONTS = ("seguisb.ttf", "segoeui.ttf", "arialbd.ttf")

_font_cache: dict[tuple[str, int], pygame.font.Font] = {}


def _first_existing(names) -> str | None:
    for name in names:
        path = os.path.join(FONT_DIR, name)
        if os.path.exists(path):
            return path
    return None


_CJK_BOLD = _first_existing(CJK_FONTS)
_CJK_REGULAR = _first_existing(CJK_REGULAR_FONTS) or _CJK_BOLD
_LATIN_BOLD = _first_existing(LATIN_FONTS)


def load_font(kind: str, size: int) -> pygame.font.Font:
    """按用途与字号取字体（带缓存）。kind: cjk_bold / cjk / latin。"""
    size = max(9, int(size))
    key = (kind, size)
    cached = _font_cache.get(key)
    if cached is not None:
        return cached

    path = {"cjk_bold": _CJK_BOLD, "cjk": _CJK_REGULAR, "latin": _LATIN_BOLD}.get(kind, _CJK_BOLD)
    font = None
    if path:
        try:
            font = pygame.font.Font(path, size)
        except (OSError, pygame.error):
            font = None
    if font is None:  # 极端回退：系统字体名
        font = pygame.font.SysFont("microsoftyaheiui,notosanssc,arial", size, bold=(kind != "cjk"))
    _font_cache[key] = font
    return font


def font_info() -> dict:
    """返回实际选中的字体文件，便于自检时打印。"""
    return {
        "cjk_bold": _CJK_BOLD,
        "cjk_regular": _CJK_REGULAR,
        "latin_bold": _LATIN_BOLD,
    }


# --------------------------------------------------------------------- 绘制
_surface_cache: dict = {}


def vertical_gradient(size, top, bottom) -> pygame.Surface:
    """垂直渐变（逐行插值）。"""
    key = ("vgrad", size, top, bottom)
    cached = _surface_cache.get(key)
    if cached is not None:
        return cached
    width, height = size
    surface = pygame.Surface(size).convert()
    for y in range(height):
        t = y / max(1, height - 1)
        color = (
            int(top[0] + (bottom[0] - top[0]) * t),
            int(top[1] + (bottom[1] - top[1]) * t),
            int(top[2] + (bottom[2] - top[2]) * t),
        )
        pygame.draw.line(surface, color, (0, y), (width, y))
    _surface_cache[key] = surface
    return surface


def glow_surface(radius: int, color, strength: int = 120, rings: int = 7) -> pygame.Surface:
    """柔光光晕（用于按钮/棋子的外发光），带缓存。"""
    key = ("glow", radius, tuple(color), strength, rings)
    cached = _surface_cache.get(key)
    if cached is not None:
        return cached
    size = radius * 2
    surface = pygame.Surface((size, size), pygame.SRCALPHA)
    rgb = color[:3]
    for i in range(rings, 0, -1):
        alpha = int(strength * (1 - i / (rings + 1)) ** 2)
        pygame.draw.circle(surface, (*rgb, alpha), (radius, radius), int(radius * i / rings))
    _surface_cache[key] = surface
    return surface


def round_rect_surface(size, radius: int, color) -> pygame.Surface:
    """带 alpha 的圆角矩形，带缓存（用于玻璃面板）。"""
    key = ("rrect", size, radius, tuple(color))
    cached = _surface_cache.get(key)
    if cached is not None:
        return cached
    surface = pygame.Surface(size, pygame.SRCALPHA)
    pygame.draw.rect(surface, color, surface.get_rect(), border_radius=radius)
    _surface_cache[key] = surface
    return surface


def blit_round(surface: pygame.Surface, rect, radius: int, color, width: int = 0) -> None:
    """在 surface 上画圆角矩形（填充或描边）。"""
    if width <= 0:
        surface.blit(round_rect_surface(rect.size, radius, color), rect.topleft)
    else:
        pygame.draw.rect(surface, color, rect, width=width, border_radius=radius)


def blit_glow(surface: pygame.Surface, center, radius: int, color, strength: int = 110) -> None:
    image = glow_surface(radius, color, strength)
    surface.blit(image, (int(center[0] - radius), int(center[1] - radius)))


def radial_stone(size: int, inner, outer, light=(0, 0)) -> pygame.Surface:
    """径向渐变圆（棋子本体），带缓存。"""
    key = ("stone", size, tuple(inner), tuple(outer), tuple(light))
    cached = _surface_cache.get(key)
    if cached is not None:
        return cached

    ss = 3  # 超采样后缩小，边缘更细腻
    d = size * ss
    surface = pygame.Surface((d, d), pygame.SRCALPHA)
    center = d / 2
    radius = d / 2
    cx = center + light[0] * ss * 0.4
    cy = center + light[1] * ss * 0.4
    steps = max(16, int(radius))
    for i in range(steps, 0, -1):
        t = i / steps
        color = (
            int(inner[0] + (outer[0] - inner[0]) * t),
            int(inner[1] + (outer[1] - inner[1]) * t),
            int(inner[2] + (outer[2] - inner[2]) * t),
            255,
        )
        pygame.draw.circle(surface, color, (int(cx), int(cy)), i)
    result = pygame.transform.smoothscale(surface, (size, size))
    _surface_cache[key] = result
    return result


def twinkle(t: float, speed: float = 3.0, phase: float = 0.0) -> float:
    """0~1 的周期闪烁，用于呼吸光效。"""
    return 0.5 + 0.5 * math.sin(t * speed + phase)


def star_field(size, count: int = 90, seed: int = 20240921) -> pygame.Surface:
    """背景星点层（只在尺寸变化时重建）。"""
    key = ("stars", size, count, seed)
    cached = _surface_cache.get(key)
    if cached is not None:
        return cached
    width, height = size
    surface = pygame.Surface(size, pygame.SRCALPHA)
    rng = random.Random(seed)
    for _ in range(count):
        x, y = rng.randrange(width), rng.randrange(height)
        radius = rng.choice((1, 1, 1, 2))
        alpha = rng.randint(30, 120)
        color = rng.choice((C["ink"], C["sakura_soft"], C["cyan"], C["violet"]))
        pygame.draw.circle(surface, (*color[:3], alpha), (x, y), radius)
    _surface_cache[key] = surface
    return surface

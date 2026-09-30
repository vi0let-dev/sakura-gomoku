"""二次元 UI 组件：自适应文字、玻璃面板、发光按钮、徽章。"""

from __future__ import annotations

import pygame

from .theme import C, blit_glow, blit_round, load_font, round_rect_surface, twinkle

# 装饰符号一律用这些（已确认 Noto Sans SC / Segoe UI 都有字形，不会出现豆腐块）
SYM_HEART = "\u2661"      # ♡
SYM_STAR = "\u2606"       # ☆
SYM_STAR_FILL = "\u2605"  # ★
SYM_FLOWER = "\u2740"     # ❀
SYM_DIAMOND = "\u25c7"    # ◇
SYM_DOT = "\u00b7"        # ·
SYM_ARROW = "\u2192"      # →
SYM_CROSS = "\u00d7"      # ×


class UiKit:
    """统一的字体获取、文字测量与装饰绘制入口。"""

    def __init__(self) -> None:
        self._fit_cache: dict[tuple, tuple[int, int, int]] = {}
        self._render_cache: dict[tuple, pygame.Surface] = {}

    # ------------------------------------------------------------ 字体 / 文本
    def font(self, size: int, *, latin: bool = False, light: bool = False) -> pygame.font.Font:
        if latin:
            kind = "latin"
        elif light:
            kind = "cjk"
        else:
            kind = "cjk_bold"
        return load_font(kind, size)

    def render(self, text: str, size: int, color, *, latin: bool = False, light: bool = False,
               glow: int = 0, glow_color=None) -> pygame.Surface:
        """渲染一行文字；glow>0 时带外发光（结果缓存）。"""
        if not text:
            text = " "
        key = (text, size, tuple(color), latin, light, glow, tuple(glow_color) if glow_color else None)
        cached = self._render_cache.get(key)
        if cached is not None:
            return cached

        font = self.font(size, latin=latin, light=light)
        base = font.render(text, True, color)
        if glow > 0:
            # 发光半径不能太大：中文笔画细，糊一圈就认不出来了。
            # 半径与字号挂钩，且透明度用陡峭的衰减，保证「文字最亮、光晕只是衬底」。
            radius_max = max(2, min(glow, max(2, size // 6)))
            pad = radius_max + 2
            surface = pygame.Surface((base.get_width() + pad * 2, base.get_height() + pad * 2), pygame.SRCALPHA)
            tint = glow_color or color
            # 先把字形压成纯色剪影（RGB 全亮 + 原始 alpha 轮廓）：
            # 直接对彩色字形 set_alpha 是无效的，叠出来就是一团糊。
            silhouette = font.render(text, True, (255, 255, 255))
            layer = pygame.Surface(silhouette.get_size(), pygame.SRCALPHA)
            layer.fill((*tint[:3], 255))
            layer.blit(silhouette, (0, 0), special_flags=pygame.BLEND_RGBA_MIN)

            for radius in range(radius_max, 0, -1):
                t = 1.0 - radius / (radius_max + 1)
                alpha = 2 + int(46 * t ** 2)          # 衰减陡峭，远离字形处几乎不可见
                layer.set_alpha(alpha)
                if radius * 2 <= radius_max:
                    offsets = ((radius, 0), (-radius, 0), (0, radius), (0, -radius))
                else:
                    offsets = ((radius, 0), (-radius, 0), (0, radius), (0, -radius),
                               (radius, radius), (-radius, -radius), (radius, -radius), (-radius, radius))
                for dx, dy in offsets:
                    surface.blit(layer, (pad + dx, pad + dy))
            layer.set_alpha(255)
            surface.blit(base, (pad, pad))
            result = surface
        else:
            result = base

        if len(self._render_cache) > 4000:
            self._render_cache.clear()
        self._render_cache[key] = result
        return result

    def size_of(self, text: str, size: int, *, latin: bool = False, light: bool = False) -> tuple[int, int]:
        return self.font(size, latin=latin, light=light).size(text)

    def fit_size(self, text: str, max_w: int, start: int, minimum: int = 11, **kw) -> int:
        """返回不超过 max_w 的最大字号（不会小于 minimum）。"""
        key = (text, int(max_w), int(start), int(minimum), kw.get("latin", False), kw.get("light", False))
        cached = self._fit_cache.get(key)
        if cached is not None:
            return cached
        size = int(start)
        while size > minimum and self.size_of(text, size, **kw)[0] > max_w:
            size -= 1
        self._fit_cache[key] = size
        return size

    def draw_text(self, surface, text: str, center=None, topleft=None, midleft=None, midright=None,
                  *, size: int = 18, color=None, latin: bool = False, light: bool = False,
                  glow: int = 0, glow_color=None, max_w: int | None = None,
                  align: str = "left", min_size: int = 11) -> pygame.Rect:
        """绘制一行文字；给 max_w 时自动缩小字号以避免溢出。"""
        color = color or C["ink"]
        if max_w is not None:
            size = self.fit_size(text, max_w, size, min_size, latin=latin, light=light)
        image = self.render(text, size, color, latin=latin, light=light, glow=glow, glow_color=glow_color)
        rect = image.get_rect()
        if center is not None:
            rect.center = center
        elif topleft is not None:
            rect.topleft = topleft
        elif midleft is not None:
            rect.midleft = midleft
        elif midright is not None:
            rect.midright = midright
        surface.blit(image, rect.topleft)
        return rect

    def slot(self, surface, text: str, rect, *, size: int = 18, color=None, latin: bool = False,
             light: bool = False, glow: int = 0, glow_color=None, align: str = "center",
             pad_x: int = 0, min_size: int = 11, axis: str = "both") -> pygame.Rect:
        """把文字放进 rect 里（自动缩小字号到位），并在指定轴上居中。

        与 draw_text 的关键区别：文字带发光时，渲染结果的 surface 会比文字本身大一圈，
        所以这里用 kit.size_of 量出的「真实文字高度」来定位，保证视觉中心落在槽位中心。
        这是避免文字互相压住的关键。
        """
        color = color or C["ink"]
        box = rect.inflate(-pad_x * 2, 0) if pad_x else rect
        size = self.fit_size(text, box.w, size, min_size, latin=latin, light=light)
        image = self.render(text, size, color, latin=latin, light=light, glow=glow, glow_color=glow_color)
        text_w, text_h = self.size_of(text, size, latin=latin, light=light)

        if align == "left":
            cx = box.x + text_w // 2
        elif align == "right":
            cx = box.right - text_w // 2
        else:
            cx = box.centerx
        cy = box.centery if axis == "both" else (box.y + text_h // 2 if axis == "top" else box.bottom - text_h // 2)

        rect_out = image.get_rect(center=(cx, cy))
        surface.blit(image, rect_out.topleft)
        return pygame.Rect(cx - text_w // 2, cy - text_h // 2, text_w, text_h)

    def wrap(self, text: str, size: int, max_w: int, *, latin: bool = False, light: bool = False) -> list[str]:
        """按宽度折行（中文逐字断行，英文按空格断行）。"""
        font = self.font(size, latin=latin, light=light)
        lines: list[str] = []
        current = ""
        for ch in text:
            if ch == "\n":
                lines.append(current)
                current = ""
                continue
            if font.size(current + ch)[0] <= max_w:
                current += ch
            else:
                if current:
                    lines.append(current)
                current = ch
        if current:
            lines.append(current)
        return lines or [""]

    def draw_paragraph(self, surface, text: str, rect, *, size: int = 15, color=None,
                       line_gap: int = 6, latin: bool = False) -> int:
        """在 rect 内绘制多行文字，返回占用高度；超出 rect 高度时自动减小字号。"""
        color = color or C["ink_faint"]
        while size > 11:
            lines = self.wrap(text, size, rect.w, latin=latin)
            line_h = self.size_of("汉", size)[1]
            if len(lines) * (line_h + line_gap) - line_gap <= rect.h:
                break
            size -= 1
        lines = self.wrap(text, size, rect.w, latin=latin)
        line_h = self.size_of("汉", size)[1]
        y = rect.y
        for line in lines:
            self.draw_text(surface, line, topleft=(rect.x, y), size=size, color=color, latin=latin)
            y += line_h + line_gap
        return y - rect.y - line_gap

    # ------------------------------------------------------------ 装饰
    def glass(self, surface, rect, radius: int = 18, *, tint=None, edge=True,
              glow: int = 0, glow_color=None, highlight=True) -> None:
        """玻璃面板：柔和阴影 + 半透明填充 + 高光描边。"""
        shadow = pygame.Surface((rect.w + 24, rect.h + 24), pygame.SRCALPHA)
        big = pygame.Rect(12, 12, rect.w, rect.h)
        pygame.draw.rect(shadow, (0, 0, 0, 70), big.move(0, 6), border_radius=radius + 4)
        pygame.draw.rect(shadow, (0, 0, 0, 45), big.move(0, 3).inflate(6, 6), border_radius=radius + 6)
        surface.blit(shadow, (rect.x - 12, rect.y - 12))

        if glow > 0:
            blit_glow(surface, rect.center, max(rect.w, rect.h) // 2 + 18,
                      glow_color or C["violet"], glow)

        fill = tint or C["glass"]
        surface.blit(round_rect_surface(rect.size, radius, fill), rect.topleft)
        # 顶部高光渐变，营造玻璃质感
        if highlight:
            hi = pygame.Surface((rect.w, max(2, rect.h // 3)), pygame.SRCALPHA)
            for y in range(hi.get_height()):
                alpha = int(26 * (1 - y / max(1, hi.get_height() - 1)))
                pygame.draw.line(hi, (255, 255, 255, alpha), (0, y), (rect.w, y))
            surface.blit(hi, (rect.x, rect.y + 2))
        if edge:
            pygame.draw.rect(surface, C["glass_line"], rect, width=1, border_radius=radius)

    def neon_bar(self, surface, rect, color, *, radius: int = 3, glow: int = 90) -> None:
        """细长的霓虹装饰条。"""
        blit_glow(surface, rect.center, max(rect.w, rect.h), color, glow)
        blit_round(surface, rect, radius, color)

    def pill(self, surface, rect, *, fill=None, edge=None, text: str = "", size: int = 15,
             color=None, glow: int = 0) -> None:
        """胶囊徽章（难度、状态等）。"""
        radius = rect.h // 2
        if glow > 0:
            blit_glow(surface, rect.center, rect.w // 2 + 14, edge or C["violet"], glow)
        surface.blit(round_rect_surface(rect.size, radius, fill or C["glass_soft"]), rect.topleft)
        pygame.draw.rect(surface, edge or C["glass_line"], rect, width=1, border_radius=radius)
        if text:
            self.draw_text(surface, text, center=rect.center, size=size, color=color or C["ink"],
                           max_w=rect.w - 18, min_size=11)

    # ------------------------------------------------------------ 按钮
    def button(self, surface, rect, label: str, *, active: bool = False, hover: bool = False,
               disabled: bool = False, t: float = 0.0, accent=None, sub: str = "",
               icon: str = "") -> None:
        """绘制按钮；active 时用强调色 + 呼吸光，hover 时提亮。"""
        accent = accent or C["sakura"]
        radius = min(16, rect.h // 2)

        if disabled:
            fill, edge, ink = (46, 42, 66, 150), (96, 90, 122, 130), C["ink_faint"]
        elif active:
            fill = (accent[0] // 3 + 30, accent[1] // 4 + 22, accent[2] // 3 + 52, 220)
            edge, ink = accent, (255, 255, 255)
        elif hover:
            fill, edge, ink = (96, 82, 140, 220), C["cyan"], (255, 255, 255)
        else:
            fill, edge, ink = C["glass"], C["glass_line"], C["ink_dim"]

        if active and not disabled:
            blit_glow(surface, rect.center, rect.w // 2 + 10, accent, int(46 + 44 * twinkle(t, 2.6)))
        surface.blit(round_rect_surface(rect.size, radius, fill), rect.topleft)
        pygame.draw.rect(surface, edge, rect, width=2 if active else 1, border_radius=radius)

        text = f"{icon} {label}" if icon else label
        if sub:
            # 上：主标签；下：拉丁副标题。两个槽位各自独立，避免发光外扩互相压住
            top = pygame.Rect(rect.x + 8, rect.y + 4, rect.w - 16, rect.h // 2 - 3)
            bottom = pygame.Rect(rect.x + 8, top.bottom + 1, rect.w - 16, rect.bottom - top.bottom - 5)
            self.slot(surface, text, top, size=16, color=ink, glow=6 if active else 0,
                      glow_color=accent, min_size=10)
            self.slot(surface, sub, bottom, size=11, color=C["ink_faint"], latin=True, min_size=8)
        else:
            self.slot(surface, text, rect.inflate(-16, -8), size=17, color=ink,
                      glow=6 if active else 0, glow_color=accent, min_size=10)

    # ------------------------------------------------------------ 章节标题
    def section(self, surface, text: str, x: int, y: int, width: int, *, color=None) -> int:
        """在 (x, y) 画一个小节标题（左侧竖条 + 文字 + 右侧细线），返回占用高度。"""
        color = color or C["violet"]
        size = self.fit_size(text, width - 40, 14, 11)
        text_h = self.size_of(text, size)[1]
        h = max(text_h + 4, 16)          # 槽位要比文字高一点，横向参考线才不会压住下一节标题
        pygame.draw.rect(surface, color, pygame.Rect(x, y + 2, 3, h - 4), border_radius=2)
        slot = pygame.Rect(x + 10, y, width - 10, h)
        used = self.slot(surface, text, slot, size=size, color=C["ink_faint"], align="left", min_size=11)
        if used.right + 6 < x + width:
            pygame.draw.line(surface, (*C["glass_line"][:3], 70),
                             (used.right + 6, y + h // 2), (x + width, y + h // 2), 1)
        return h

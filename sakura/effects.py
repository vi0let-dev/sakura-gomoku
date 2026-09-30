"""樱花飘落、星屑爆闪等二次元粒子特效。"""

from __future__ import annotations

import math
import random

import pygame

from .theme import C, blit_glow

_petal_cache: dict[tuple[int, int], list[pygame.Surface]] = {}


def _petal_frames(size: int, seed: int = 7, count: int = 4) -> list[pygame.Surface]:
    """预渲染几种朝向的花瓣。"""
    key = (size, seed)
    cached = _petal_cache.get(key)
    if cached is not None:
        return cached

    frames: list[pygame.Surface] = []
    # 花瓣形状：半个椭圆 + 尖角，用多边形近似
    base = pygame.Surface((size, size), pygame.SRCALPHA)
    s = size
    points = []
    steps = 18
    for i in range(steps + 1):
        a = math.pi * i / steps
        points.append((s * 0.5 + s * 0.46 * math.sin(a) ** 0.85, s * 0.5 - s * 0.46 * math.cos(a)))
    for i in range(steps + 1):
        a = math.pi * i / steps
        points.append((s * 0.5 - s * 0.46 * math.sin(a) ** 0.85, s * 0.5 + s * 0.46 * math.cos(a)))
    pygame.draw.polygon(base, (*C["sakura_soft"], 210), points)
    pygame.draw.polygon(base, (*C["sakura"], 120), points, max(1, s // 14))
    # 中脉
    pygame.draw.line(base, (*C["sakura_deep"], 90), (s * 0.5, s * 0.12), (s * 0.5, s * 0.9), 1)

    for i in range(count):
        frames.append(pygame.transform.rotozoom(base, -40 + i * 28, 1.0))
    _petal_cache[key] = frames
    return frames


class Petal:
    __slots__ = ("x", "y", "vy", "sway", "phase", "angle", "spin", "size", "alpha")

    def __init__(self, width: int, height: int, rng: random.Random, spawn_anywhere: bool = True) -> None:
        self.reset(width, height, rng, spawn_anywhere)

    def reset(self, width: int, height: int, rng: random.Random, spawn_anywhere: bool = True) -> None:
        self.size = rng.choice((8, 10, 12, 14, 16))
        self.x = rng.uniform(-40, width + 40)
        self.y = rng.uniform(0, height) if spawn_anywhere else rng.uniform(-80, -10)
        self.vy = rng.uniform(16, 42)
        self.sway = rng.uniform(12, 34)
        self.phase = rng.uniform(0, math.tau)
        self.angle = rng.uniform(0, 360)
        self.spin = rng.uniform(-42, 42)
        self.alpha = rng.randint(120, 215)

    def update(self, dt: float, width: int, height: int, rng: random.Random) -> None:
        self.phase += dt * 1.1
        self.y += self.vy * dt
        self.x += math.sin(self.phase) * self.sway * dt
        self.angle += self.spin * dt
        if self.y > height + 30 or self.x < -70 or self.x > width + 70:
            self.reset(width, height, rng, spawn_anywhere=False)


class Spark:
    """星屑粒子（落子迸发 / 胜利礼花）。"""

    __slots__ = ("x", "y", "vx", "vy", "life", "max_life", "size", "color", "shape")

    def __init__(self, x: float, y: float, vx: float, vy: float, life: float, size: float, color, shape: str) -> None:
        self.x, self.y = x, y
        self.vx, self.vy = vx, vy
        self.life = self.max_life = life
        self.size = size
        self.color = color
        self.shape = shape

    def update(self, dt: float, gravity: float = 60.0) -> bool:
        self.life -= dt
        self.x += self.vx * dt
        self.y += self.vy * dt
        self.vy += gravity * dt
        self.vx *= 1 - 1.6 * dt
        return self.life > 0


class Effects:
    """统一管理花瓣与星屑。"""

    def __init__(self, size, petal_count: int = 26, seed: int = 20240921) -> None:
        self.rng = random.Random(seed)
        self.width, self.height = size
        self.petals = [Petal(self.width, self.height, self.rng) for _ in range(petal_count)]
        self.sparks: list[Spark] = []
        self._elapsed = 0.0

    def resize(self, size) -> None:
        self.width, self.height = size
        for petal in self.petals:
            petal.reset(self.width, self.height, self.rng, spawn_anywhere=True)

    def set_petal_count(self, count: int) -> None:
        while len(self.petals) < count:
            self.petals.append(Petal(self.width, self.height, self.rng))
        while len(self.petals) > count:
            self.petals.pop()

    def burst(self, pos, count: int = 18, *, spread: float = 150.0, color=None, big: bool = False) -> None:
        """在 pos 处迸发星屑。"""
        palette = [color] if color else [C["cyan"], C["sakura"], C["gold"], C["violet"], C["ink"]]
        for _ in range(count):
            angle = self.rng.uniform(0, math.tau)
            speed = self.rng.uniform(spread * 0.25, spread)
            spark = Spark(
                pos[0], pos[1],
                math.cos(angle) * speed, math.sin(angle) * speed - (40 if big else 0),
                self.rng.uniform(0.45, 1.0 if not big else 1.5),
                self.rng.uniform(2.0, 4.6 if big else 3.2),
                self.rng.choice(palette),
                self.rng.choice(("star", "circle")) if big else "circle",
            )
            self.sparks.append(spark)

    def update(self, dt: float) -> None:
        self._elapsed += dt
        for petal in self.petals:
            petal.update(dt, self.width, self.height, self.rng)
        self.sparks = [s for s in self.sparks if s.update(dt)]
        if len(self.sparks) > 600:
            del self.sparks[: len(self.sparks) - 600]

    @property
    def elapsed(self) -> float:
        return self._elapsed

    def draw_petals(self, surface: pygame.Surface) -> None:
        for petal in self.petals:
            frames = _petal_frames(petal.size)
            image = frames[int(petal.angle / 90) % len(frames)]
            image.set_alpha(petal.alpha)
            surface.blit(image, (int(petal.x), int(petal.y)))

    def draw_sparks(self, surface: pygame.Surface) -> None:
        for spark in self.sparks:
            t = max(0.0, min(1.0, spark.life / spark.max_life))
            alpha = int(255 * t)
            size = max(1, int(spark.size * (0.4 + 0.6 * t)))
            if spark.shape == "star":
                blit_glow(surface, (spark.x, spark.y), size * 3, spark.color, int(70 * t))
                pygame.draw.circle(surface, (*spark.color[:3], alpha), (int(spark.x), int(spark.y)), size)
                for k in range(4):
                    angle = math.pi / 2 * k + self._elapsed * 1.5
                    dx, dy = math.cos(angle) * size * 2.6, math.sin(angle) * size * 2.6
                    pygame.draw.line(surface, (*spark.color[:3], alpha),
                                     (spark.x, spark.y), (spark.x + dx, spark.y + dy), 1)
            else:
                layer = pygame.Surface((size * 2 + 2, size * 2 + 2), pygame.SRCALPHA)
                pygame.draw.circle(layer, (*spark.color[:3], alpha), (size + 1, size + 1), size)
                surface.blit(layer, (int(spark.x - size - 1), int(spark.y - size - 1)))

"""把各个界面渲染成 PNG，便于人工检查视觉效果（不需要真实窗口）。"""

import os
import sys

os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"
os.environ["PYGAME_HIDE_SUPPORT_PROMPT"] = "1"

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

import pygame  # noqa: E402

from sakura.app import App  # noqa: E402
from sakura.game import BLACK, WHITE  # noqa: E402

OUT = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "screenshots")

MID = [(7, 7, BLACK), (7, 8, WHITE), (8, 8, BLACK), (6, 6, WHITE),
       (8, 6, BLACK), (8, 7, WHITE), (9, 7, BLACK)]
WIN = [(7, 7, BLACK), (6, 6, WHITE), (7, 8, BLACK), (6, 7, WHITE), (7, 9, BLACK),
       (6, 8, WHITE), (7, 10, BLACK), (6, 9, WHITE), (7, 11, BLACK)]


def shot(app, name, moves=(), *, mode="pve", level="普通", hover=None, notice="", frames=40):
    app.mode = mode
    app.set_level(level)
    app.board.reset()
    app.glow_stones.clear()
    app.thinking = False
    app.notice = notice
    app.notice_until = 10 ** 9 if notice else 0
    for r, c, p in moves:
        app.board.place(r, c, p)
        app.effects.burst(app.cell_to_px(r, c), 8)
    app.hover = hover
    for i in range(frames):
        app.effects.update(1 / 60)
        app.draw(1 / 60)
    path = os.path.join(OUT, name)
    pygame.image.save(app.window, path)
    print("saved", os.path.basename(path), "|", app.board.status_text())


def main():
    os.makedirs(OUT, exist_ok=True)
    app = App()
    shot(app, "01_start.png", notice="点击交叉点落子，你执黑先行")
    shot(app, "02_playing.png", MID, hover=(6, 7), notice="轮到你落子")
    shot(app, "03_win.png", WIN)
    shot(app, "04_pvp.png", MID, mode="pvp", notice="双人对战中")
    shot(app, "05_ai_vs_ai.png", WIN, mode="ai", level="困难", notice="AI 对 AI 自动对局")
    shot(app, "06_hard_thinking.png", MID, level="困难")

    # 缩放：最小窗口 / 大窗口
    for size, name in ((( 860, 700), "07_min_window.png"), ((1440, 960), "08_large_window.png")):
        pygame.event.post(pygame.event.Event(pygame.VIDEORESIZE, w=size[0], h=size[1], size=size))
        for event in pygame.event.get():
            app.handle_event(event)
        shot(app, name, MID, hover=(6, 7))
    pygame.quit()


if __name__ == "__main__":
    main()

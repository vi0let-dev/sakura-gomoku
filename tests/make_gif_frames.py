"""生成动图用的原始帧（无压缩 RGB），供 gif_assemble.py 合成 GIF。

为什么要分两步：游戏环境只装了 pygame，而写 GIF 需要 Pillow。
把「渲染」和「编码」拆开，就不用为了做个动图给运行环境塞额外依赖。

用法（在项目根目录）：
    <env>\\python.exe tests\\make_gif_frames.py frames.bin [宽] [高] [fps] [脚本步数]

输出：
    frames.bin   每帧 width*height*3 字节的原始 RGB
    frames.json  帧尺寸与每帧时长（毫秒）
    screenshots/gif_preview.png  最后一帧（原尺寸）预览
"""

import json
import os
import sys
import time

os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"
os.environ["PYGAME_HIDE_SUPPORT_PROMPT"] = "1"

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

import pygame  # noqa: E402

from sakura.ai import GomokuAI  # noqa: E402
from sakura.app import App  # noqa: E402
from sakura.game import BLACK, WHITE, Board  # noqa: E402

# 演示对局：双方都用电脑棋手，黑方（普通难度、先手）对白方（简单难度），
# 黑方会正常防守并靠棋力取胜，比写死脚本更自然，也不会出现“漏防送胜”的怪局。
BLACK_LEVEL = "普通"
WHITE_LEVEL = "简单"
BLACK_SEED = 42
WHITE_SEED = 77
# 这组参数下是一盘 21 手、黑方取胜的对局：全程有攻防，长度也适合做成动图
T_OPEN = 1.8      # 开场停留
T_THINK = 0.18    # 「思考中」停留
T_MOVE = 0.36     # 每手落子后的停留
T_END = 1.8       # 终局礼花停留

# 为了控制 GIF 体积：只把「开局的几手」和「最后几手」逐手演示，
# 中间的对局直接快进（棋盘状态会更新，但不额外产生帧）。
SHOW_HEAD = 6     # 开局演示手数
SHOW_TAIL = 7     # 结尾演示手数
SKIP_FRAMES = 3   # 中间对局每手压缩成的帧数（让棋盘看起来在推进）


def surface_bytes(surface: pygame.Surface) -> bytes:
    return pygame.image.tobytes(surface, "RGB")


def main():
    out_bin = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "frames.bin")
    win_w = int(sys.argv[2]) if len(sys.argv) > 2 else 800
    win_h = int(sys.argv[3]) if len(sys.argv) > 3 else 640
    fps = int(sys.argv[4]) if len(sys.argv) > 4 else 12
    max_moves = int(sys.argv[5]) if len(sys.argv) > 5 else 40
    frame_ms = int(round(1000 / fps))

    app = App(size=(win_w, win_h))
    app.rebuild_layout()
    app.effects.resize((win_w, win_h))
    app.effects.set_petal_count(30)
    app.mode = "pve"
    app.set_level("普通")
    app.sound_on = False

    fh = open(out_bin, "wb")
    durations = []
    t = 0.0
    shot = 0

    def frame(dt: float) -> None:
        """按时间推进一帧并写入。"""
        nonlocal t, shot
        t += dt
        app.effects.update(dt)
        app.draw(dt)
        fh.write(surface_bytes(app.window))
        durations.append(frame_ms)
        shot += 1

    def hold(seconds: float, dt: float = 1 / 24) -> None:
        steps = max(1, int(round(seconds / dt)))
        for _ in range(steps):
            frame(dt)

    print(f"窗口 {win_w}x{win_h}，{fps}fps，预计帧数不定，开始渲染…")
    t0 = time.time()

    # 1) 开场：空棋盘，樱花飘落
    hold(T_OPEN)

    # 2) 先把整局棋算完，记下每一步，再决定哪些步骤逐帧渲染
    black_ai = GomokuAI(BLACK_LEVEL, seed=BLACK_SEED)
    white_ai = GomokuAI(WHITE_LEVEL, seed=WHITE_SEED)
    probe = Board()
    plan = []                                # [(player, (row, col)), ...]
    while not probe.game_over and len(plan) < max_moves:
        player = probe.current
        cell = (black_ai if player == BLACK else white_ai).choose_move(probe, player)
        if cell is None or not probe.place(cell[0], cell[1], player):
            break
        plan.append((player, cell))
    total = len(plan)
    skip_from = SHOW_HEAD
    skip_to = max(SHOW_HEAD, total - SHOW_TAIL)

    # 3) 逐手回放
    for index, (player, cell) in enumerate(plan):
        if skip_from <= index < skip_to:
            # 快进段：只在棋盘上落子并少量出帧
            app.commit_move(cell[0], cell[1], player)
            for _ in range(SKIP_FRAMES):
                frame(1 / fps)
            continue
        app.thinking = True
        hold(T_THINK)                        # 「思考中」提示
        app.thinking = False
        app.commit_move(cell[0], cell[1], player)
        hold(T_MOVE)                         # 落子 + 星屑

    # 4) 终局：留够时间看礼花
    if app.board.game_over:
        hold(T_END)
    fh.close()

    meta = {"width": win_w, "height": win_h, "frames": shot,
            "durations": durations, "fps": fps, "moves": app.board.move_count,
            "winner": app.board.winner}
    with open(os.path.splitext(out_bin)[0] + ".json", "w", encoding="utf-8") as jf:
        json.dump(meta, jf)

    os.makedirs(os.path.join(ROOT, "screenshots"), exist_ok=True)
    pygame.image.save(app.window, os.path.join(ROOT, "screenshots", "gif_preview.png"))
    pygame.quit()

    size_mb = os.path.getsize(out_bin) / 1024 / 1024
    print(f"完成：{shot} 帧，用时 {time.time()-t0:.1f}s，{out_bin} {size_mb:.1f} MB")
    print(f"棋局：{app.board.move_count} 手，{'黑胜' if app.board.winner==BLACK else ('白胜' if app.board.winner==WHITE else '未结束')}")


if __name__ == "__main__":
    main()

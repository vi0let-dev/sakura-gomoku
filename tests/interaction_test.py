"""交互流程测试：用合成事件驱动真实主循环（落子 / 按钮 / AI 应手 / 缩放 / 退出）。"""

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

from sakura.app import App  # noqa: E402
from sakura.game import BLACK, WHITE  # noqa: E402

FAILS = []


def check(cond, msg):
    print(f"[{'PASS' if cond else 'FAIL'}] {msg}")
    if not cond:
        FAILS.append(msg)


def pump(app, predicate=lambda: False, timeout=3.0, dt=1 / 120):
    """跑真实主循环直到条件成立或超时。"""
    deadline = time.time() + timeout
    frames = 0
    while time.time() < deadline:
        for event in pygame.event.get():
            app.handle_event(event)
        app.maybe_ai()
        app.effects.update(dt)
        app.draw(dt)
        frames += 1
        if predicate():
            return True, frames
        time.sleep(dt)
    return False, frames


def click(app, pos, timeout=0.3):
    pygame.event.post(pygame.event.Event(pygame.MOUSEMOTION, pos=pos, rel=(0, 0), buttons=(0, 0, 0)))
    pygame.event.post(pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=pos, button=1))
    pygame.event.post(pygame.event.Event(pygame.MOUSEBUTTONUP, pos=pos, button=1))
    pump(app, timeout=timeout)


def press(app, key, timeout=0.25):
    pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=key, mod=0, unicode="", scancode=0))
    pygame.event.post(pygame.event.Event(pygame.KEYUP, key=key, mod=0, unicode="", scancode=0))
    pump(app, timeout=timeout)


def main():
    app = App()
    print("\n== 人机对战 ==")
    app.set_mode("pve")
    check(app.board.move_count == 0, "开局棋盘为空")

    click(app, app.cell_to_px(7, 7))
    ok, _ = pump(app, lambda: app.board.move_count >= 2, timeout=8)
    check(ok and app.board.get(7, 7) == BLACK, "点击后黑棋落在天元")
    check(app.board.move_count == 2 and app.board.last_move[2] == WHITE, "AI 随后执白应手")

    for cell in ((6, 8), (8, 8), (5, 9), (9, 9)):
        before = app.board.move_count
        click(app, app.cell_to_px(*cell), timeout=0.05)
        pump(app, lambda: app.board.move_count >= before + 2 or app.board.game_over, timeout=8)
    check(app.board.move_count >= 8 or app.board.game_over, f"连续对局推进到 {app.board.move_count} 手")

    print("\n== 按钮与快捷键 ==")
    before = app.board.move_count
    app.dispatch("undo")
    check(app.board.move_count < before, f"悔棋生效（{before} → {app.board.move_count}）")

    press(app, pygame.K_r)
    check(app.board.move_count == 0 and not app.board.game_over, "快捷键 R 重新开始")

    press(app, pygame.K_s)
    check(app.sound_on is False, "快捷键 S 关闭音效")
    press(app, pygame.K_s)
    check(app.sound_on is True, "快捷键 S 再次开启")

    press(app, pygame.K_2)
    check(app.mode == "pvp", "快捷键 2 切到双人对战")
    click(app, app.cell_to_px(7, 7))
    check(app.board.get(7, 7) == BLACK and app.board.move_count == 1, "双人模式黑棋落子，AI 未介入")
    click(app, app.cell_to_px(7, 8))
    check(app.board.get(7, 8) == WHITE and app.board.move_count == 2, "双人模式白棋继续落子")

    press(app, pygame.K_3)
    check(app.mode == "ai", "快捷键 3 切到 AI 对 AI")
    ok, _ = pump(app, lambda: app.board.move_count >= 6, timeout=10)
    check(ok, f"AI 对 AI 自动推进到 {app.board.move_count} 手")

    press(app, pygame.K_1)
    check(app.mode == "pve", "快捷键 1 回到人机对战")

    for key, level in ((pygame.K_F1, "简单"), (pygame.K_F2, "普通"), (pygame.K_F3, "困难")):
        press(app, key)
        check(app.ai.level == level, f"F 键切到 {level} 难度")

    print("\n== 非法操作 ==")
    app.set_mode("pvp")
    before = app.board.move_count
    click(app, (5, 5))
    check(app.board.move_count == before, "点到棋盘外不落子")
    app.board.place(7, 7, BLACK)
    click(app, app.cell_to_px(7, 7))
    check(app.board.move_count == 1, "点到已有棋子不重复落子")

    # AI 对局中点击无效：连点 8 次，棋盘只应由电脑在两个固定点交替落子
    app.set_mode("ai")
    app.ai.set_level("简单")
    for _ in range(8):
        click(app, app.cell_to_px(3, 3), timeout=0.02)
    click(app, app.cell_to_px(3, 3), timeout=0.01)   # 立即检查，排除刚落的子被悔掉
    check(app.board.is_empty(3, 3), "AI 对局中点击 (3,3) 无效，棋盘上没有玩家落子")
    check(app.board.move_count >= 1, f"AI 对局仍在自动推进（{app.board.move_count} 手）")

    # 轮到电脑时玩家点击也应无效（此时电脑正在思考）
    app.set_mode("pve")
    click(app, app.cell_to_px(7, 7), timeout=0.01)      # 玩家先落一子，随后轮到电脑
    if app.board.current != WHITE:
        pump(app, lambda: app.board.current == WHITE, timeout=2)
    check(app.board.current == WHITE, "玩家落子后轮到电脑")
    before = app.board.move_count
    click(app, app.cell_to_px(3, 3), timeout=0.01)
    check(app.board.move_count == before and app.board.is_empty(3, 3), "轮到电脑时玩家点击无效")
    app.set_mode("pvp")

    print("\n== 终局流程 ==")
    app.set_mode("pvp")
    for c in range(4):
        app.board.place(7, c, BLACK)
        app.board.place(8, c, WHITE)
    click(app, app.cell_to_px(7, 4))
    check(app.board.winner == BLACK and app.board.game_over, "第五子落下判定黑棋获胜")
    before = app.board.move_count
    click(app, app.cell_to_px(10, 10))
    check(app.board.move_count == before, "终局后不再接受落子")
    pump(app, timeout=0.3)
    check(True, "终局画面绘制无异常")

    print("\n== 窗口与退出 ==")
    pygame.event.post(pygame.event.Event(pygame.VIDEORESIZE, w=1280, h=900, size=(1280, 900)))
    pump(app, timeout=0.3)
    check(app.window.get_size() == (1280, 900), f"缩放后画布 {app.window.get_size()}")
    check(app.layout["board"].right < app.layout["panel"].x, "缩放后棋盘与面板仍不重叠")

    pygame.event.post(pygame.event.Event(pygame.VIDEORESIZE, w=300, h=200, size=(300, 200)))
    pump(app, timeout=0.3)
    check(app.window.get_size()[0] >= app.min_size[0] and app.window.get_size()[1] >= app.min_size[1],
          f"过小的尺寸被夹到最小值 {app.window.get_size()}")

    pygame.event.post(pygame.event.Event(pygame.QUIT))
    pump(app, timeout=0.3)
    check(not app.running, "QUIT 事件结束主循环")

    pygame.quit()
    print("\n" + "=" * 54)
    if FAILS:
        print(f"失败 {len(FAILS)} 项：")
        for f in FAILS:
            print("  -", f)
        return 1
    print("交互测试全部通过")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

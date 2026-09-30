"""棋盘规则、AI 决策、布局与渲染的冒烟测试（无窗口运行）。"""

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

from sakura.ai import GomokuAI, evaluate_board, point_score  # noqa: E402
from sakura.game import BLACK, EMPTY, SIZE, WHITE, Board  # noqa: E402
from sakura.layout import TEXTS, compute_layout, page_size  # noqa: E402
from sakura.theme import font_info  # noqa: E402
from sakura.ui import UiKit  # noqa: E402

FAILS = []


def check(cond, msg):
    print(f"[{'PASS' if cond else 'FAIL'}] {msg}")
    if not cond:
        FAILS.append(msg)


def row_pattern(pattern, start=0):
    text = "." * start + pattern
    assert len(text) <= SIZE, f"图案超过 {SIZE} 列：{text}"
    return text.ljust(SIZE, ".")


def make_board(rows, turn=BLACK):
    b = Board()
    items = rows if rows and isinstance(rows[0], tuple) else list(enumerate(rows))
    for r, line in items:
        assert 0 <= r < SIZE, f"行号越界：{r}"
        for c, ch in enumerate(line):
            assert c < SIZE, f"第 {r} 行图案超过 {SIZE} 列"
            if ch == ".":
                continue
            player = BLACK if ch == "X" else WHITE
            b.grid[r][c] = player
            b.history.append((r, c, player))
    b.current = turn
    b.winner = EMPTY
    b.winning_line = []
    b.game_over = False
    return b


def assert_no_win(b, note=""):
    for r, c, player in b.history:
        assert not b.winning_line_through(r, c, player), f"测试图案已经五连：{note}"
    return b


def test_board():
    print("\n== 棋盘规则 ==")
    b = Board()
    check(not b.game_over and b.current == BLACK, "初始：黑先、未结束")
    check(b.place(7, 7, BLACK), "黑棋可以落子")
    check(not b.place(7, 7, WHITE), "同一位置不能重复落子")
    check(b.current == WHITE, "落子后自动换手")

    b = Board()
    for c in range(4):
        b.place(7, c, BLACK)
        b.place(8, c, WHITE)
    b.place(7, 4, BLACK)
    check(b.winner == BLACK and b.game_over and len(b.winning_line) == 5, "水平五连判胜")

    b = Board()
    for r in range(4):
        b.place(r, 3, WHITE)
        b.place(r, 9, BLACK)
    b.place(4, 3, WHITE)
    check(b.winner == WHITE, "垂直五连判胜")

    b = Board()
    for i in range(4):
        b.place(i, i, BLACK)
        b.place(i, i + 1, WHITE)
    b.place(4, 4, BLACK)
    check(b.winner == BLACK, "主对角五连判胜")

    b = Board()
    for i in range(4):
        b.place(i, 8 - i, WHITE)
        b.place(i, i, BLACK)
    b.place(4, 4, WHITE)
    check(b.winner == WHITE, "副对角五连判胜")

    b = Board()
    for c in range(4):
        b.place(0, c, BLACK)
    check(b.winner == EMPTY and not b.game_over, "四连不算赢")
    check(b.would_win(0, 4, BLACK), "would_win 能识别成五点")
    check(not b.would_win(1, 1, BLACK), "would_win 对普通点返回 False")

    b = Board()
    for cell in ((5, 1), (5, 2), (5, 3), (5, 6)):
        b.place(cell[0], cell[1], BLACK)
    b.place(6, 0, WHITE)
    b.place(5, 5, BLACK)
    b.place(6, 1, WHITE)
    b.place(5, 4, BLACK)
    check(b.winner == BLACK and len(b.winning_line) == 6, f"六子长连判胜（连线 {len(b.winning_line)} 子）")

    b = Board()
    b.place(7, 7, BLACK)
    b.place(7, 8, WHITE)
    b.undo(1)
    check(b.is_empty(7, 8) and b.current == WHITE, "悔棋恢复棋盘与手番")
    b.undo(1)
    check(b.move_count == 0 and b.current == BLACK, "连续悔棋回到开局")

    b = Board()
    pattern = [[(r + 2 * c) % 4 for c in range(SIZE)] for r in range(SIZE)]
    for r in range(SIZE):
        for c in range(SIZE):
            b.place(r, c, BLACK if pattern[r][c] in (0, 1) else WHITE)
            if b.winner:
                break
        if b.winner:
            break
    check(b.game_over and b.winner == EMPTY, "填满且无五连时判平局")


def test_ai():
    print("\n== 电脑棋手 ==")
    ai = GomokuAI("普通")

    b = assert_no_win(make_board([(4, row_pattern("XXXX", 1))]), "case1")
    check(b.would_win(4, 0, BLACK) and b.would_win(4, 5, BLACK), "(4,0)/(4,5) 都是制胜点")
    move = ai.choose_move(b, BLACK)
    check(move is not None and b.would_win(move[0], move[1], BLACK), f"AI 选择自己的制胜点（{move}）")

    b = assert_no_win(make_board([(7, row_pattern("OOOO", 3)), (7, row_pattern("X", 7))]), "case2")
    move = ai.choose_move(b, BLACK)
    check(move == (7, 2), f"AI 堵住唯一的成五点（{move}）")

    b = assert_no_win(make_board([(7, row_pattern("OOOO", 1)), (8, row_pattern("XXX", 1))]), "case3")
    move = ai.choose_move(b, BLACK)
    check(move in ((7, 0), (7, 5)), f"对手活四时去堵一端（{move}）")

    b = assert_no_win(make_board([(7, row_pattern("OOO", 2)), (8, row_pattern("XX", 3))]), "case4")
    move = ai.choose_move(b, BLACK)
    check(move in ((7, 1), (7, 5)), f"对手活三时予以限制（{move}）")

    b = assert_no_win(make_board([(7, row_pattern("OOOO", 2)), (9, row_pattern("XXX", 2))]), "case5")
    b.grid[7][6] = BLACK
    b.history.append((7, 6, BLACK))
    check(b.would_win(7, 1, WHITE) and not b.would_win(7, 6, WHITE), "白棋是冲四，只有 (7,1) 成五")
    move = ai.choose_move(b, BLACK)
    check(move == (7, 1), f"AI 优先堵冲四（{move}）")

    b = assert_no_win(make_board([(2, row_pattern("XXXX", 2)), (7, row_pattern("OOOO", 3))]), "case6")
    move = ai.choose_move(b, BLACK)
    check(move is not None and b.would_win(move[0], move[1], BLACK), f"双方都有机会时先自己获胜（{move}）")

    check(GomokuAI("普通").choose_move(Board(), BLACK) == (7, 7), "空盘开局落在天元")

    for level in ("简单", "普通", "困难"):
        ai.set_level(level)
        b = Board()
        b.place(7, 7, BLACK)
        b.place(7, 8, WHITE)
        b.place(6, 6, BLACK)
        t0 = time.perf_counter()
        move = ai.choose_move(b, WHITE)
        cost = time.perf_counter() - t0
        check(move is not None and b.is_empty(move[0], move[1]),
              f"{level}：返回合法着法 {move}（{cost*1000:.0f} ms）")
        check(cost < 3.0, f"{level}：耗时 {cost:.2f}s 在预算内")

    b = make_board([(0, row_pattern("XXXX", 1))])
    b.grid[0][0] = EMPTY
    b.history = [(0, c, BLACK) for c in (1, 2, 3, 4)]
    move = GomokuAI("普通").choose_move(b, BLACK)
    check(move == (0, 0), f"制胜点是 (0,0) 时也能正确返回（{move}）")

    b = Board()
    b.place(7, 7, BLACK)
    b.place(7, 8, BLACK)
    b.place(7, 9, BLACK)
    check(evaluate_board(b, BLACK) > evaluate_board(b, WHITE), "评估函数偏向棋型更好的一方")
    check(point_score(b.grid, 7, 10, BLACK) > point_score(b.grid, 5, 5, BLACK), "成四点分数远高于普通点")


def test_ai_vs_ai():
    print("\n== AI 自我对局（10 局） ==")
    black_ai, white_ai = GomokuAI("简单", seed=7), GomokuAI("简单", seed=11)
    results = {"black": 0, "white": 0, "draw": 0}
    t0 = time.perf_counter()
    for _ in range(10):
        b = Board()
        for _ in range(SIZE * SIZE):
            ai = black_ai if b.current == BLACK else white_ai
            move = ai.choose_move(b, b.current)
            if move is None:
                break
            b.place(move[0], move[1], b.current)
            if b.game_over:
                break
        if b.winner == BLACK:
            results["black"] += 1
        elif b.winner == WHITE:
            results["white"] += 1
        else:
            results["draw"] += 1
        if b.winner:
            check(len(b.winning_line) >= 5, f"终局连线 {len(b.winning_line)} 子")
    cost = time.perf_counter() - t0
    print(f"    结果 {results}，总耗时 {cost:.2f}s")
    check(sum(results.values()) == 10, "10 局全部正常结束")
    check(cost < 30, "自我对局速度正常")


def test_layout():
    print("\n== 布局自检（元素不重叠 / 文字不溢出） ==")
    pygame.init()
    pygame.display.set_mode((320, 240))
    kit = UiKit()
    print("    字体:", {k: (os.path.basename(v) if v else None) for k, v in font_info().items()})

    min_size = page_size(kit)
    print(f"    内容所需最小窗口: {min_size}")
    check(min_size is not None, "能算出容纳全部内容的最小窗口")
    check(min_size[0] <= 1000 and min_size[1] <= 920, f"最小窗口 {min_size} 在合理范围内")

    sizes = [(860, 700), (1010, 840), (1100, 860), (1280, 900), (1440, 960), (1920, 1080), (2560, 1440)]
    minimum = page_size(kit)
    sizes.insert(0, minimum)
    check(compute_layout(minimum[0], minimum[1], kit) is not None,
          f"最小窗口 {minimum} 可以正常布局")
    problems = 0
    for size in sizes:
        try:
            L = compute_layout(size[0], size[1], kit)
        except AssertionError as exc:
            problems += 1
            print(f"    [FAIL] {size}: {exc}")
            continue

        buttons = L["buttons"]
        rects = list(buttons.values())
        for bid, btn in buttons.items():
            if not L["inner"].contains(btn.rect):
                problems += 1
                print(f"    [FAIL] {size} {bid} 超出面板 {btn.rect} vs {L['inner']}")
        for i in range(len(rects)):
            for j in range(i + 1, len(rects)):
                a, b = rects[i].rect, rects[j].rect
                if a.colliderect(b):
                    problems += 1
                    print(f"    [FAIL] {size} 按钮重叠 {a} / {b}")
        for bid, btn in buttons.items():
            room = btn.rect.w - 16
            text = btn.label
            fit = kit.fit_size(text, room, 17, 9)
            if kit.size_of(text, fit)[0] > room:
                problems += 1
                print(f"    [FAIL] {size} {bid} 文字 {text!r} 溢出")
            if btn.filled and btn.hint:
                hs = kit.fit_size(btn.hint, room, 11, 8, latin=True)
                if kit.size_of(btn.hint, hs, latin=True)[0] > room:
                    problems += 1
                    print(f"    [FAIL] {size} {bid} 副标题 {btn.hint!r} 溢出")
        status, board, header, inner = L["status_rect"], L["board"], L["header"], L["inner"]
        ordered = [("status", status), ("modes", buttons["mode_pve"].rect),
                   ("levels", buttons["level_简单"].rect), ("actions", buttons["undo"].rect),
                   ("toggles", buttons["sound"].rect), ("help", L["help_rect"])]
        for k in range(len(ordered) - 1):
            a, b = ordered[k][1], ordered[k + 1][1]
            if a.bottom > b.top:
                problems += 1
                print(f"    [FAIL] {size} {ordered[k][0]} 与 {ordered[k+1][0]} 纵向重叠")
        if board.right + 8 > L["panel"].x:
            problems += 1
            print(f"    [FAIL] {size} 棋盘与面板重叠")
        if board.bottom > size[1] or board.right > size[0]:
            problems += 1
            print(f"    [FAIL] {size} 棋盘超出窗口 {board}")
        if header.bottom > board.top:
            problems += 1
            print(f"    [FAIL] {size} 顶部标题与棋盘重叠")
        if header.right > L["panel"].x:
            problems += 1
            print(f"    [FAIL] {size} 顶部标题与面板重叠")
        move_w = kit.size_of(f"{TEXTS['move']} 99", 12)[0]
        think_w = kit.size_of(f"{TEXTS['thinking']}...", 12)[0]
        if move_w + 12 + think_w > status.w - 28 - 40:
            problems += 1
            print(f"    [FAIL] {size} 状态行文字可能重叠（{move_w}+{think_w}）")
        if L["used"] > inner.h + 1:
            problems += 1
            print(f"    [FAIL] {size} 面板内容超出 {L['used']} > {inner.h}")

    check(problems == 0, f"7 种窗口尺寸下布局全部合格（问题 {problems} 处）")

    # 反向验证：内容确实放不下时必须报错，而不是悄悄重叠
    from sakura.layout import _layout_panel
    too_small = pygame.Rect(40, 40, 236, 200)
    raised = False
    try:
        _layout_panel(too_small, kit, base=16)
    except AssertionError:
        raised = True
    check(raised, "面板空间不足时会抛出断言（不会静默重叠）")
    pygame.display.quit()


def test_render():
    print("\n== 渲染 ==")
    from sakura.app import App
    from sakura.ui import UiKit
    from sakura.game import BLACK as B, WHITE as W

    app = App()
    check(app.window.get_size() == (1010, 840), f"初始窗口 {app.window.get_size()}")
    check(app.min_size[0] <= 1000 and app.min_size[1] <= 920, f"最小窗口限制 {app.min_size}")

    for row, col in ((0, 0), (7, 7), (14, 14), (3, 11)):
        px = app.cell_to_px(row, col)
        check(app.px_to_cell(px) == (row, col), f"坐标换算往返一致 {row},{col}")

    app.draw(1 / 60)
    check(True, "空棋盘绘制无异常")

    # 实测：记录一帧内所有文字的落位框，检查有没有互相压住
    records: list = []
    original_slot = UiKit.slot

    def spy(self, surface, text, rect, **kw):
        out = original_slot(self, surface, text, rect, **kw)
        records.append((text, pygame.Rect(out)))
        return out

    UiKit.slot = spy
    try:
        app.mode = "pvp"
        app.board.reset()
        for c in range(4):
            app.board.place(7, c, B)
            app.board.place(8, c, W)
        app.hover = (6, 7)
        app.thinking = True
        records.clear()
        app.draw(1 / 60)
        texts = [t for t, _ in records]
        overlaps = []
        for i in range(len(records)):
            for j in range(i + 1, len(records)):
                a, b = records[i][1], records[j][1]
                if a.colliderect(b):
                    overlaps.append((records[i][0], records[j][0]))
        check(not overlaps, f"一帧内文字互不重叠（{len(records)} 条文本，冲突 {len(overlaps)} 处）")
        if overlaps:
            for pair in overlaps[:6]:
                print("    [FAIL] 文字重叠:", pair)
        check(any("五子棋" == t for t in texts), "标题已绘制")
        check(any("回合" in t for t in texts), "状态文字已绘制")
        check(any("思考中" in t for t in texts), "思考中提示已绘制")

        # 终局：横幅文字也不能压住状态区
        app.board.reset()
        for c in range(4):
            app.board.place(7, c, B)
            app.board.place(8, c, W)
        app.board.place(7, 4, B)
        records.clear()
        app.draw(1 / 60)
        banner_overlaps = []
        for i in range(len(records)):
            for j in range(i + 1, len(records)):
                a, b = records[i][1], records[j][1]
                if a.colliderect(b) and a.centerx < app.layout["board"].right \
                        and b.centerx < app.layout["board"].right:
                    banner_overlaps.append((records[i][0], records[j][0]))
        check(not banner_overlaps, f"终局横幅文字互不重叠（冲突 {len(banner_overlaps)} 处）")
    finally:
        UiKit.slot = original_slot

    app.thinking = False
    app.mode = "pvp"
    app.board.reset()
    for c in range(4):
        app.commit_move(7, c, B)
        app.commit_move(8, c, W)
    app.commit_move(7, 4, B)
    app.draw(1 / 60)
    check(app.board.winner == B, "终局横幅绘制无异常")

    for bid in list(app.buttons):
        app.dispatch(bid)
        app.mode = "pvp"
        app.draw(1 / 60)
    check(True, "所有按钮均可点击并绘制")

    app.effects.burst((400, 400), 30, big=True)
    for _ in range(20):
        app.effects.update(1 / 60)
    app.draw(1 / 60)
    check(len(app.effects.petals) > 0, "樱花花瓣在场")

    for size in ((860, 700), (1440, 960), (1000, 780)):
        pygame.event.post(pygame.event.Event(pygame.VIDEORESIZE, w=size[0], h=size[1], size=size))
        for event in pygame.event.get():
            app.handle_event(event)
        app.draw(1 / 60)
    check(app.window.get_size()[0] >= app.min_size[0], f"缩放后窗口 {app.window.get_size()} 不小于限制")

    check("place" in app.sounds and "win" in app.sounds, "合成音效已生成")
    app.play("place")
    pygame.quit()


def main():
    test_board()
    test_ai()
    test_ai_vs_ai()
    test_layout()
    test_render()
    print("\n" + "=" * 54)
    if FAILS:
        print(f"失败 {len(FAILS)} 项：")
        for f in FAILS:
            print("  -", f)
        return 1
    print("全部通过")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""五子棋棋盘核心逻辑（纯逻辑，不依赖 pygame，可单独测试）。

棋盘 15x15，格子值：0 = 空，1 = 黑棋，2 = 白棋
坐标统一使用 (row, col)，row 向下增大，col 向右增大。
"""

from __future__ import annotations

SIZE = 15
EMPTY, BLACK, WHITE = 0, 1, 2

# 四个扫描方向：横、竖、主对角、副对角
DIRECTIONS = ((0, 1), (1, 0), (1, 1), (1, -1))

PLAYER_NAMES = {BLACK: "黑棋", WHITE: "白棋"}


def opponent(player: int) -> int:
    return WHITE if player == BLACK else BLACK


def in_bounds(row: int, col: int) -> bool:
    return 0 <= row < SIZE and 0 <= col < SIZE


class Board:
    """棋盘状态与胜负判定。"""

    def __init__(self, size: int = SIZE) -> None:
        self.size = size
        self.reset()

    # ------------------------------------------------------------------ 基础
    def reset(self) -> None:
        self.grid = [[EMPTY] * self.size for _ in range(self.size)]
        self.history: list[tuple[int, int, int]] = []      # (row, col, player)
        self.current = BLACK
        self.winner = EMPTY
        self.winning_line: list[tuple[int, int]] = []
        self.game_over = False

    def get(self, row: int, col: int) -> int:
        return self.grid[row][col]

    def is_empty(self, row: int, col: int) -> bool:
        return self.grid[row][col] == EMPTY

    @property
    def move_count(self) -> int:
        return len(self.history)

    @property
    def last_move(self):
        return self.history[-1] if self.history else None

    @property
    def is_full(self) -> bool:
        return len(self.history) >= self.size * self.size

    def empties(self):
        for r in range(self.size):
            row = self.grid[r]
            for c in range(self.size):
                if row[c] == EMPTY:
                    yield r, c

    def neighbors_of_stones(self, radius: int = 2) -> set[tuple[int, int]]:
        """已有棋子附近（切比雪夫半径 radius 内）的空点集合，用于缩小搜索范围。"""
        cells: set[tuple[int, int]] = set()
        for r, c, _ in self.history:
            for dr in range(-radius, radius + 1):
                for dc in range(-radius, radius + 1):
                    if not (dr or dc):
                        continue
                    rr, cc = r + dr, c + dc
                    if in_bounds(rr, cc) and self.grid[rr][cc] == EMPTY:
                        cells.add((rr, cc))
        return cells

    # ------------------------------------------------------------------ 落子
    def place(self, row: int, col: int, player: int) -> bool:
        """在空点落子；成功后切换手番并判定胜负。"""
        if self.game_over or not in_bounds(row, col) or self.grid[row][col] != EMPTY:
            return False

        self.grid[row][col] = player
        self.history.append((row, col, player))

        line = self.winning_line_through(row, col, player)
        if line:
            self.winner = player
            self.winning_line = line
            self.game_over = True
        elif self.is_full:
            self.game_over = True          # 平局
        else:
            self.current = opponent(player)
        return True

    def undo(self, steps: int = 1) -> int:
        """撤销最近 steps 步，返回实际撤销的步数。"""
        undone = 0
        for _ in range(steps):
            if not self.history:
                break
            row, col, player = self.history.pop()
            self.grid[row][col] = EMPTY
            self.current = player
            undone += 1
        self.winner = EMPTY
        self.winning_line = []
        self.game_over = False
        return undone

    # ------------------------------------------------------------------ 判定
    def winning_line_through(self, row: int, col: int, player: int):
        """若该点构成五连（或更长）则返回连线上所有坐标，否则 None。"""
        for dr, dc in DIRECTIONS:
            line = [(row, col)]
            for sign in (1, -1):
                step = 1
                while True:
                    rr, cc = row + dr * step * sign, col + dc * step * sign
                    if not in_bounds(rr, cc) or self.grid[rr][cc] != player:
                        break
                    line.append((rr, cc))
                    step += 1
            if len(line) >= 5:
                line.sort()
                return line
        return None

    def would_win(self, row: int, col: int, player: int) -> bool:
        """在空点试落一子判断是否成五（不改变棋盘状态）。"""
        if self.grid[row][col] != EMPTY:
            return False
        self.grid[row][col] = player
        try:
            return bool(self.winning_line_through(row, col, player))
        finally:
            self.grid[row][col] = EMPTY

    def status_text(self) -> str:
        if self.winner:
            return f"{PLAYER_NAMES[self.winner]}获胜"
        if self.game_over:
            return "平局"
        return f"{PLAYER_NAMES[self.current]}落子"

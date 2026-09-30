"""电脑棋手：棋型评分 + 迭代加深 α-β 搜索。

分工（很重要）：
    * 静态评估只衡量「威胁」，单方向上限是 THREAT_CAP；
    * 真正的连五由搜索返回 SCORE_MATE。
否则静态评估会被「双方都有一堆成五点」淹没，出现为了自己做四而漏掉对手成五的蠢棋。
"""

from __future__ import annotations

import random
import time

from .game import BLACK, DIRECTIONS, EMPTY, SIZE, WHITE, opponent

# --------------------------------------------------------------------- 分数
SCORE_MATE = 1_000_000        # 搜索中真正连五（终局）
THREAT_CAP = 500_000          # 静态评估里的单方向上限
SCORE_OPEN_FOUR = 120_000
SCORE_FOUR = 30_000           # 冲四 / 被堵一端的四
SCORE_OPEN_THREE = 12_000
SCORE_THREE = 1_500           # 眠三
SCORE_OPEN_TWO = 600
SCORE_TWO = 120
SCORE_ONE = 20

# 难度：搜索深度 / 每层候选数 / 节点上限 / 时间预算（秒）
LEVELS = {
    "简单": dict(depth=1, width=10, nodes=2_000, budget=0.35),
    "普通": dict(depth=2, width=8, nodes=12_000, budget=1.0),
    "困难": dict(depth=4, width=6, nodes=45_000, budget=2.0),
}
DEFAULT_LEVEL = "普通"


class SearchTimeout(Exception):
    """搜索超出时间/节点预算。"""


# --------------------------------------------------------------------- 棋型
def _run(grid, row, col, dr, dc, player, size) -> int:
    """沿 (dr, dc) 统计从 (row, col) 出发的连续同色子数量。"""
    n = 0
    r, c = row + dr, col + dc
    while 0 <= r < size and 0 <= c < size and grid[r][c] == player:
        n += 1
        r += dr
        c += dc
    return n


def line_score(length: int, open_ends: int) -> int:
    """「连子长度 + 开放端数」→ 分数（成五按威胁上限计）。"""
    if length >= 5:
        return THREAT_CAP
    if length == 4:
        return SCORE_OPEN_FOUR if open_ends >= 2 else (SCORE_FOUR if open_ends == 1 else 0)
    if length == 3:
        return SCORE_OPEN_THREE if open_ends >= 2 else (SCORE_THREE if open_ends == 1 else 0)
    if length == 2:
        return SCORE_OPEN_TWO if open_ends >= 2 else (SCORE_TWO if open_ends == 1 else 0)
    if length == 1:
        return SCORE_ONE + open_ends * 10
    return 0


def point_score(grid, row: int, col: int, player: int, size: int = SIZE) -> int:
    """假设 player 落在空点 (row, col)，四个方向累计的棋型分。"""
    total = 0
    for dr, dc in DIRECTIONS:
        before = _run(grid, row, col, -dr, -dc, player, size)
        after = _run(grid, row, col, dr, dc, player, size)
        length = before + after + 1

        head_r, head_c = row - dr * before, col - dc * before
        ends = 0
        for er, ec in ((head_r + dr * length, head_c + dc * length), (head_r - dr, head_c - dc)):
            if 0 <= er < size and 0 <= ec < size and grid[er][ec] == EMPTY:
                ends += 1
        total += line_score(length, ends)
    return total


# --------------------------------------------------------------------- 着法
def candidates(board, player: int, width: int) -> list[tuple[int, int, float]]:
    """候选着法 [(row, col, 排序分)]，按威胁程度降序。"""
    if not board.history:
        mid = board.size // 2
        return [(mid, mid, 0.0)]

    grid = board.grid
    size = board.size
    foe = opponent(player)
    cells = board.neighbors_of_stones(2)
    if not cells:
        return []

    scored = []
    for row, col in cells:
        attack = point_score(grid, row, col, player, size)
        defend = point_score(grid, row, col, foe, size)
        # 进攻略优先于防守；双威胁点（攻守兼备）额外加分
        scored.append((row, col, max(attack, defend * 0.9) + attack * 0.6 + defend * 0.4))
    scored.sort(key=lambda item: -item[2])
    return scored[:width]


def find_win(board, player: int):
    """棋子附近能立刻连五的点（不限制候选数，避免漏掉关键点）。"""
    for row, col in board.neighbors_of_stones(2):
        if board.would_win(row, col, player):
            return row, col
    return None


def evaluate_board(board, player: int, size: int = SIZE) -> int:
    """从 player 视角静态评估（只看棋子附近的空点，兼顾效率）。"""
    grid = board.grid
    foe = opponent(player)
    mine = theirs = 0
    for row, col in board.neighbors_of_stones(1):
        mine += point_score(grid, row, col, player, size)
        theirs += point_score(grid, row, col, foe, size)
    return mine - int(theirs * 1.15)


# --------------------------------------------------------------------- 搜索
class GomokuAI:
    """五子棋电脑棋手。level 取 LEVELS 的键。"""

    def __init__(self, level: str = DEFAULT_LEVEL, seed: int | None = None) -> None:
        self.rng = random.Random(seed)
        self.nodes = 0
        self._deadline = 0.0
        self.set_level(level)

    def set_level(self, level: str) -> None:
        self.level = level if level in LEVELS else DEFAULT_LEVEL
        cfg = LEVELS[self.level]
        self.depth = cfg["depth"]
        self.width = cfg["width"]
        self.node_cap = cfg["nodes"]
        self.budget = cfg["budget"]

    # -------------------------------------------------------------- 对外接口
    def choose_move(self, board, player: int):
        """返回 (row, col) 或 None。"""
        if board.game_over:
            return None
        if not candidates(board, player, 1):
            return None

        # 1) 自己能连五 → 直接赢（(0,0) 也是合法着法，必须显式判断 None）
        win = find_win(board, player)
        if win is not None:
            return win

        # 2) 对手能连五 → 必须堵
        block = find_win(board, opponent(player))
        if block is not None:
            return block

        if self.level == "简单":
            return self._easy_move(board, player)

        self.nodes = 0
        self._deadline = time.monotonic() + self.budget
        best = None
        try:
            for depth in range(2, self.depth + 1, 2):
                move = self._search_root(board, player, depth)
                if move is not None:
                    best = move
        except SearchTimeout:
            pass
        return best if best is not None else self._fallback(board, player)

    # -------------------------------------------------------------- 简单难度
    def _easy_move(self, board, player: int):
        """只看一层棋型，并带一点随机性。"""
        if self.rng.random() < 0.25:
            cells = list(board.neighbors_of_stones(1)) or list(board.empties())
            return self.rng.choice(cells) if cells else None

        grid = board.grid
        foe = opponent(player)
        best, best_score = None, -1.0
        for row, col, _ in candidates(board, player, 14):
            score = point_score(grid, row, col, player)
            score += point_score(grid, row, col, foe) * 0.85
            score *= 1.0 + self.rng.random() * 0.25
            if score > best_score:
                best, best_score = (row, col), score
        return best

    def _fallback(self, board, player: int):
        moves = candidates(board, player, 1)
        if moves:
            return moves[0][0], moves[0][1]
        empties = list(board.empties())
        return self.rng.choice(empties) if empties else None

    # -------------------------------------------------------------- 搜索主体
    def _search_root(self, board, player: int, depth: int):
        alpha, beta = -10 ** 12, 10 ** 12
        best_move, best_score = None, -10 ** 12
        for row, col, _ in candidates(board, player, self.width):
            self._tick()
            board.grid[row][col] = player
            board.history.append((row, col, player))
            try:
                if board.winning_line_through(row, col, player):
                    score = SCORE_MATE + depth * 1000
                else:
                    score = -self._negamax(board, opponent(player), depth - 1, -beta, -alpha, depth)
            finally:
                board.history.pop()
                board.grid[row][col] = EMPTY
            if score > best_score:
                best_move, best_score = (row, col), score
            if score > alpha:
                alpha = score
        return best_move

    def _negamax(self, board, player: int, depth: int, alpha: int, beta: int,
                 root_depth: int | None = None) -> int:
        self._tick()
        win_value = SCORE_MATE + (root_depth if root_depth is not None else depth) * 1000
        if depth <= 0:
            return evaluate_board(board, player, board.size)

        moves = candidates(board, player, self.width)
        if not moves:
            return evaluate_board(board, player, board.size)

        # 当前方有必胜点 → 直接返回（必胜点必定是最优）
        for row, col, _ in moves:
            board.grid[row][col] = player
            board.history.append((row, col, player))
            try:
                won = bool(board.winning_line_through(row, col, player))
            finally:
                board.history.pop()
                board.grid[row][col] = EMPTY
            if won:
                return win_value

        best = -10 ** 12
        for row, col, _ in moves:
            self._tick()
            board.grid[row][col] = player
            board.history.append((row, col, player))
            try:
                score = -self._negamax(board, opponent(player), depth - 1, -beta, -alpha, root_depth)
            finally:
                board.history.pop()
                board.grid[row][col] = EMPTY
            if score > best:
                best = score
            if best > alpha:
                alpha = best
            if alpha >= beta:
                break
        return best if best > -10 ** 12 else evaluate_board(board, player, board.size)

    def _tick(self) -> None:
        self.nodes += 1
        if self.nodes % 256 == 0:
            if time.monotonic() > self._deadline or self.nodes > self.node_cap:
                raise SearchTimeout

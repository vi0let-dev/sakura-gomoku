"""樱花五子棋（二次元风格 pygame 实现）。

模块划分：
    game.py     棋盘与胜负判定（纯逻辑，不依赖 pygame）
    ai.py       棋型评分 + α-β 搜索的电脑棋手
    theme.py    配色、字体、渐变/发光等绘制原语
    ui.py       自适应文字、玻璃面板、发光按钮
    layout.py   按内容顺序排布的面板布局（保证元素不重叠）
    effects.py  樱花飘落与星屑粒子
    app.py      事件循环与主程序入口
"""

__all__ = ["ai", "app", "effects", "game", "layout", "theme", "ui"]
__version__ = "1.0.0"

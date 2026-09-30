#!/usr/bin/env python
"""樱花五子棋启动脚本。

需要 pygame（依赖见 environment.yml），启动方式：

    python run.py

如果项目使用独立的 conda 环境，用该环境的解释器运行即可：

    conda activate <环境名>
    python run.py

或直接指定解释器：

    <conda环境路径>\\python.exe run.py
"""

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

try:
    import pygame  # noqa: F401
except ImportError:
    sys.stderr.write(
        "未找到 pygame。请先按 environment.yml 准备运行环境，例如：\n"
        "    conda env create -p <目标环境路径> -f environment.yml\n"
        "然后使用该环境的解释器运行本脚本：\n"
        "    <目标环境路径>\\python.exe run.py\n"
        "也可以只安装游戏需要的库：\n"
        "    python -m pip install pygame==2.6.1\n"
    )
    raise SystemExit(1)

from sakura.app import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())

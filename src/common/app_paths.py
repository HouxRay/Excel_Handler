"""运行时路径工具 —— 统一"软件所在目录"的判定

**为什么必须有这个模块**：打包（PyInstaller）后 ``__file__`` 指向
``sys._MEIPASS`` 临时解包目录，进程退出即被删除。若据此定位运行时数据目录，
写入的数据会"看起来成功、实际随临时目录一起消失"。

因此凡是"放在软件目录下"的数据（``txt/``、``pic/`` 等）都必须走这里，
不要再各自写 ``os.path.dirname(os.path.dirname(os.path.abspath(__file__)))``。
"""
import os
import sys


def app_root() -> str:
    """软件所在目录。

    - **打包运行**：**exe 所在目录**，而不是 ``sys._MEIPASS``
    - **源码运行**：向上查找"包含 ``src/`` 目录"的那一层，即仓库根目录

    **为什么用标记查找而不是固定上溯级数**：本文件原在 ``src/`` 下，上溯两级即仓库根；
    重构搬到 ``src/common/`` 后，固定上溯两级会落到 ``src/``，导致 ``txt/``、``pic/``、
    ``mapping/``、``prompts/`` 这些运行时目录**全部定位错**（表现为数据"写入成功但找不到"）。
    """
    if getattr(sys, "frozen", False):
        return os.path.dirname(os.path.abspath(sys.executable))
    here = os.path.dirname(os.path.abspath(__file__))
    current = here
    for _ in range(5):
        if os.path.isdir(os.path.join(current, "src")):
            return current
        parent = os.path.dirname(current)
        if parent == current:
            break
        current = parent
    # 兜底：非常规布局下退回"上溯两级"的老行为
    return os.path.dirname(os.path.dirname(here))


def runtime_subdir(name: str) -> str:
    """软件目录下的运行时数据子目录。

    例：``runtime_subdir("txt")`` → ``<软件目录>/txt``
    """
    return os.path.join(app_root(), name)

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

    - **源码运行**：仓库根目录（本文件上溯两级）
    - **打包运行**：**exe 所在目录**，而不是 ``sys._MEIPASS``
    """
    if getattr(sys, "frozen", False):
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def runtime_subdir(name: str) -> str:
    """软件目录下的运行时数据子目录。

    例：``runtime_subdir("txt")`` → ``<软件目录>/txt``
    """
    return os.path.join(app_root(), name)

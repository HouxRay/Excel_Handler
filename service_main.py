"""无界面服务入口（与桌面入口 ``main.py`` 并列）

用法：

```bash
python service_main.py --ini service.ini
# 或全靠环境变量：APP_CONF / APP_TOKEN / APP_HOST / APP_PORT
```

容器里由 Dockerfile 的 ``CMD`` 调用（见 S6），启动后对外提供 HTTP 接口。
"""
import argparse
import os
import sys


#: 必须**全局保留** QApplication 的引用：
#: 只放在函数局部变量里会被 Python 回收，之后后台任务线程里 `QApplication.instance()`
#: 会返回 None 并**在新线程里再造一个**（Qt 报 "QApplication was not created in the main() thread"）。
_QT_APP = None


def _prepare_headless():
    """无界面预处理（**必须在导入业务模块之前**完成）

    1. ``QT_QPA_PLATFORM=offscreen`` —— 没有显示器也能运行 Qt
    2. 创建并**全局持有** QApplication —— ``Excel_Writer`` 等模块会用到
    3. 注入"不弹窗"的人工确认策略 —— 否则模态弹窗在容器里会**永久阻塞**
    4. 纯文件日志（不挂 GUI 文本框）
    """
    global _QT_APP

    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

    from PyQt5.QtWidgets import QApplication
    _QT_APP = QApplication.instance() or QApplication(sys.argv[:1])

    from src.Excel_Writer import headless_confirm, set_confirm_handler
    set_confirm_handler(headless_confirm)

    from src.log_setup import setup_logger
    setup_logger(None)
    return _QT_APP


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Excel 誊写器 —— 无界面服务")
    parser.add_argument("--ini", default=None,
                        help="配置文件路径（默认 service.ini 或环境变量 APP_CONF）")
    parser.add_argument("--host", default=None, help="监听地址（默认 127.0.0.1）")
    parser.add_argument("--port", type=int, default=None, help="监听端口（默认 8080）")
    parser.add_argument("--concurrency", type=int, default=1,
                        help="并发上限（默认 1，适配 2GB 内存的 NAS）")
    args = parser.parse_args(argv)

    _prepare_headless()

    from src.log_setup import logger
    from src.service.api import create_app
    from src.service.config import ServiceConfig, VERSION
    from src.service.jobs import JobStore

    cfg = ServiceConfig(ini_path=args.ini)
    if args.host:
        cfg.env["APP_HOST"] = args.host
    if args.port:
        cfg.env["APP_PORT"] = str(args.port)

    store = JobStore(base_dir=cfg.jobs_dir, preview_ttl=cfg.preview_ttl)
    interrupted = store.recover()
    if interrupted:
        logger.warning(f"上次退出时有 {len(interrupted)} 个任务处于写入中，"
                       f"已标记 interrupted（**不自动重试**，避免重复写入）")

    app = create_app(cfg, store, concurrency=args.concurrency)

    host, port = cfg.host, cfg.port
    profiles = ", ".join(cfg.profiles()) or "无"
    logger.info(f"服务启动 v{VERSION} → http://{host}:{port}（目标档案: {profiles}）")
    if not cfg.token:
        logger.warning("未配置 token：请确保只监听本机（127.0.0.1），不要暴露到局域网")

    from waitress import serve
    serve(app, host=host, port=port, threads=4)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""日志配置模块"""
import logging
import os
from datetime import datetime
from PyQt5.QtWidgets import QTextEdit


class QTextEditLogger(logging.Handler):
    def __init__(self, text_widget):
        super().__init__()
        self.text_widget = text_widget
        self.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))

    def emit(self, record):
        msg = self.format(record)
        self.text_widget.append(msg)


def setup_logger(text_widget=None):
    if not os.path.exists("logs"):
        os.makedirs("logs")

    log_filename = f"logs/app_{datetime.now().strftime('%Y-%m-%d')}.log"
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')

    file_handler = logging.FileHandler(log_filename, encoding='utf-8')
    file_handler.setFormatter(formatter)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)

    logger = logging.getLogger(__name__)
    logger.setLevel(logging.INFO)

    if not logger.handlers:
        logger.addHandler(file_handler)
        logger.addHandler(console_handler)

    if text_widget:
        gui_handler_exists = any(
            isinstance(h, QTextEditLogger) and h.text_widget == text_widget
            for h in logger.handlers
        )
        if not gui_handler_exists:
            gui_handler = QTextEditLogger(text_widget)
            gui_handler.setFormatter(formatter)
            logger.addHandler(gui_handler)

    logger.propagate = False
    return logger


logger = setup_logger()

"""AI 历史预测筛选对话框 — 按日期/文件名筛选历史记录"""
import os
from datetime import datetime, timedelta

from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QTableWidget,
                             QTableWidgetItem, QHeaderView, QPushButton,
                             QLabel, QComboBox)
from PyQt5.QtCore import Qt

from src import ai_storage


class AiHistoryDialog(QDialog):
    """历史预测筛选：日期下拉 + 文件下拉 + 结果表格"""

    def __init__(self, current_file: str = "", parent=None):
        super().__init__(parent)
        self.setWindowTitle("AI 历史预测")
        self.setGeometry(350, 200, 650, 420)
        self._selected_filepath = None

        layout = QVBoxLayout()

        # 筛选行
        filter_row = QHBoxLayout()
        filter_row.addWidget(QLabel("日期:"))
        self.date_combo = QComboBox()
        self._populate_dates()
        self.date_combo.currentIndexChanged.connect(self._refresh)
        filter_row.addWidget(self.date_combo)

        filter_row.addWidget(QLabel("文件:"))
        self.file_combo = QComboBox()
        self.file_combo.addItem("全部文件", "")
        for name in ai_storage.get_available_filenames():
            self.file_combo.addItem(name, name)
        # 默认选中当前打开的文件
        if current_file:
            idx = self.file_combo.findData(current_file)
            if idx >= 0:
                self.file_combo.setCurrentIndex(idx)
        self.file_combo.currentIndexChanged.connect(self._refresh)
        filter_row.addWidget(self.file_combo)
        filter_row.addStretch()
        layout.addLayout(filter_row)

        # 结果表格
        self.table = QTableWidget()
        self.table.setColumnCount(3)
        self.table.setHorizontalHeaderLabels(["时间", "文件", "预测条数"])
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setSelectionMode(QTableWidget.SingleSelection)
        layout.addWidget(self.table)

        # 底部按钮
        btn_layout = QHBoxLayout()
        reuse_btn = QPushButton("✅ 选择并复用")
        cancel_btn = QPushButton("取消")
        reuse_btn.clicked.connect(self._on_reuse)
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addStretch()
        btn_layout.addWidget(reuse_btn)
        btn_layout.addWidget(cancel_btn)
        layout.addLayout(btn_layout)

        self.setLayout(layout)
        self._refresh()

    def _populate_dates(self):
        """填充日期选项：今天/昨天/近7天/全部"""
        today = datetime.now().strftime("%Y-%m-%d")
        yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
        week_ago = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
        self.date_combo.addItem("今天", today)
        self.date_combo.addItem("昨天", yesterday)
        self.date_combo.addItem("近7天", week_ago)
        self.date_combo.addItem("全部", "")

    def _current_filters(self) -> tuple:
        """返回 (date_filter, file_filter)"""
        date_filter = self.date_combo.currentData() or ""
        file_filter = self.file_combo.currentData() or ""
        # 近7天需要按 >= week_ago 过滤
        return date_filter, file_filter

    def _refresh(self):
        """根据筛选条件刷新表格"""
        date_filter, file_filter = self._current_filters()
        results = ai_storage.load_ai_results_filtered(date_filter, file_filter)
        self.table.setRowCount(len(results))
        for row, r in enumerate(results):
            self.table.setItem(row, 0, QTableWidgetItem(r["timestamp"]))
            fname = os.path.splitext(os.path.basename(r["source_file"]))[0]
            self.table.setItem(row, 1, QTableWidgetItem(fname))
            self.table.setItem(row, 2, QTableWidgetItem(str(r["predictions_count"])))

    def _on_reuse(self):
        """选择并复用"""
        row = self.table.currentRow()
        if row < 0:
            return
        date_filter, file_filter = self._current_filters()
        results = ai_storage.load_ai_results_filtered(date_filter, file_filter)
        if row < len(results):
            self._selected_filepath = results[row]["filepath"]
            self.accept()

    def get_selected_filepath(self) -> str:
        return self._selected_filepath or ""

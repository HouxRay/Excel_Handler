"""AI 批量提取进度对话框 — 非模态实时进度窗

需求来源：Requires/Requirements/Update_require_2026-10-13_1.md

设计要点：
- **非模态**（setModal(False) + Qt.NonModal）：主窗口在批量处理过程中保持可响应
- 逐行显示每个文件的状态：⬜ 等待 / ⏳ 处理中 / ✅ 完成 / ❌ 失败
- 已完成的行提供 [查看]（只读预览，由主窗口用 AiPreviewDialog(read_only=True) 打开）
- 底部按钮：[重试失败项] [后台运行] [取消]

本对话框只负责界面与用户意图，**不做任何 AI 调用与数据写入**：
用户操作一律通过信号回传主窗口处理（主窗口负责线程、数据与落档）。
"""
from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
                             QProgressBar, QTableWidget, QTableWidgetItem,
                             QHeaderView, QMessageBox)
from PyQt5.QtCore import Qt, pyqtSignal


class BatchProgressDialog(QDialog):
    """AI 批量提取的实时进度窗口（非模态）"""

    # 用户意图 → 主窗口
    cancel_requested = pyqtSignal()          # 取消（停止派发新文件，已完成保留）
    background_requested = pyqtSignal()      # 后台运行（关窗但继续处理）
    retry_requested = pyqtSignal()           # 重试失败项
    view_requested = pyqtSignal(int)         # 查看某一行（0 基行号）

    STATUS_WAITING = "⬜ 等待"
    STATUS_RUNNING = "⏳ 处理中"
    STATUS_DONE = "✅ 完成"
    STATUS_FAILED = "❌ 失败"

    def __init__(self, labels: list, parent=None):
        super().__init__(parent)
        self.labels = list(labels)
        self._done = 0
        self._failed = 0
        self._finished = False
        self._view_btns = []

        self.setWindowTitle(f"AI 批量提取 (0/{len(self.labels)})")
        self.setModal(False)
        self.setWindowModality(Qt.NonModal)
        self.setGeometry(320, 220, 740, 540)

        self._build_ui()
        self._populate()

    # ---------------- 界面构建 ----------------

    def _build_ui(self):
        layout = QVBoxLayout()

        self.progress = QProgressBar()
        self.progress.setRange(0, max(1, len(self.labels)))
        self.progress.setValue(0)
        self.progress.setFormat("%v / %m")
        layout.addWidget(self.progress)

        self.summary = QLabel("准备中…")
        self.summary.setStyleSheet("color: #555; font-size: 11px;")
        layout.addWidget(self.summary)

        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["机构 / 比赛", "状态", "结果", "操作"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.table.setColumnWidth(1, 80)
        self.table.setColumnWidth(2, 70)
        self.table.setColumnWidth(3, 70)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        layout.addWidget(self.table)

        btn_layout = QHBoxLayout()
        self.retry_btn = QPushButton("🔁 重试失败项")
        self.retry_btn.setEnabled(False)
        self.retry_btn.clicked.connect(self.retry_requested.emit)

        self.background_btn = QPushButton("后台运行")
        self.background_btn.clicked.connect(self._on_background)

        self.cancel_btn = QPushButton("取消")
        self.cancel_btn.clicked.connect(self._on_cancel)

        btn_layout.addWidget(self.retry_btn)
        btn_layout.addStretch()
        btn_layout.addWidget(self.background_btn)
        btn_layout.addWidget(self.cancel_btn)
        layout.addLayout(btn_layout)

        self.setLayout(layout)

    def _populate(self):
        """按 labels 建立初始行（全部为"等待"），并挂上每行的 [查看] 按钮"""
        self.table.setRowCount(len(self.labels))
        self._view_btns = []

        for row, label in enumerate(self.labels):
            name_item = QTableWidgetItem(str(label))
            name_item.setToolTip(str(label))
            self.table.setItem(row, 0, name_item)

            self.table.setItem(row, 1, QTableWidgetItem(self.STATUS_WAITING))
            self.table.setItem(row, 2, QTableWidgetItem(""))

            btn = QPushButton("查看")
            btn.setEnabled(False)                       # 完成后才可点
            btn.clicked.connect(lambda _=False, r=row: self.view_requested.emit(r))
            self.table.setCellWidget(row, 3, btn)
            self._view_btns.append(btn)

    # ---------------- 主线程调用的状态更新 ----------------

    def mark_running(self, index: int, label: str, total: int):
        """index 为 1 基序号"""
        self.progress.setMaximum(max(1, total))
        self.progress.setValue(index - 1)
        self._set_status(index - 1, self.STATUS_RUNNING)
        self.summary.setText(f"正在处理：{label}")

    def mark_done(self, index: int, label: str, count: int):
        self._done += 1
        self._set_status(index - 1, self.STATUS_DONE)
        item = self.table.item(index - 1, 2)
        if item is not None:
            item.setText(f"{count} 条")
        btn = self._view_btns[index - 1]
        btn.setEnabled(True)
        self.progress.setValue(index)
        self._sync_title()

    def mark_failed(self, index: int, label: str, error: str):
        self._failed += 1
        self._set_status(index - 1, self.STATUS_FAILED)
        item = self.table.item(index - 1, 2)
        if item is not None:
            item.setText("失败")
            item.setToolTip(str(error))
        self.progress.setValue(index)
        self._sync_title()

    def mark_finished(self, failed_count: int, cancelled: bool):
        """批量结束（正常结束或被取消）"""
        self._finished = True
        if cancelled:
            self.summary.setText(
                f"已取消：完成 {self._done} 项，失败 {failed_count} 项（已完成的结果已保留）")
        else:
            self.summary.setText(f"全部完成：成功 {self._done} 项，失败 {failed_count} 项")

        self.background_btn.setEnabled(False)
        self.cancel_btn.setText("关闭")
        self.retry_btn.setEnabled(failed_count > 0)

    @property
    def is_finished(self) -> bool:
        return self._finished

    # ---------------- 内部 ----------------

    def _sync_title(self):
        self.setWindowTitle(f"AI 批量提取 ({self.progress.value()}/{self.progress.maximum()})")

    def _set_status(self, row: int, text: str):
        item = self.table.item(row, 1)
        if item is not None:
            item.setText(text)

    def _on_background(self):
        """后台运行：关窗但继续处理（主窗口保持批量线程运行）"""
        self.background_requested.emit()
        self.hide()

    def _on_cancel(self):
        if self._finished:
            self.close()
            return
        self.cancel_requested.emit()

    def closeEvent(self, event):
        """关窗(X) 等同取消：未完成时二次确认，已完成时直接关闭"""
        if self._finished:
            super().closeEvent(event)
            return

        reply = QMessageBox.question(
            self, "确认取消",
            "批量提取尚未完成，关闭窗口将停止处理后续文件。\n"
            "已完成的结果会保留在软件中，是否继续？",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            self.cancel_requested.emit()
            super().closeEvent(event)
        else:
            event.ignore()

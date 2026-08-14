"""AI 提取结果预览对话框 — 表格展示，可勾选行"""
from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QTableWidget,
                             QTableWidgetItem, QHeaderView, QPushButton,
                             QCheckBox, QLabel)
from PyQt5.QtCore import Qt


class AiPreviewDialog(QDialog):
    """AI 提取结果预览：表格展示，用户勾选要填入的行"""

    def __init__(self, predictions: list, mode: str = "bd", parent=None):
        super().__init__(parent)
        self.mode = mode
        self.setWindowTitle("AI 预测结果预览")
        self.setGeometry(300, 200, 720, 480)

        layout = QVBoxLayout()

        # 提示标签
        hint = QLabel("请核对 AI 提取的预测结果，勾选要填入的行：")
        hint.setStyleSheet("color: #555; font-size: 12px;")
        layout.addWidget(hint)

        # 表格
        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels(
            ["勾选", "机构/编号", "主队", "客队", "比分", "胜平负"]
        )
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self._populate(predictions)
        layout.addWidget(self.table)

        # 底部按钮
        btn_layout = QHBoxLayout()
        select_all_btn = QPushButton("全选")
        clear_btn = QPushButton("全不选")
        select_all_btn.clicked.connect(lambda: self._set_all_checked(True))
        clear_btn.clicked.connect(lambda: self._set_all_checked(False))
        btn_layout.addWidget(select_all_btn)
        btn_layout.addWidget(clear_btn)
        btn_layout.addStretch()

        ok_btn = QPushButton("✅ 确认填入")
        cancel_btn = QPushButton("取消")
        ok_btn.clicked.connect(self.accept)
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(ok_btn)
        btn_layout.addWidget(cancel_btn)
        layout.addLayout(btn_layout)

        self.setLayout(layout)

    def _populate(self, predictions: list):
        """填充表格数据"""
        self.predictions = predictions
        self.table.setRowCount(len(predictions))
        for row, pred in enumerate(predictions):
            # 勾选列（默认选中）
            checkbox = QCheckBox()
            checkbox.setChecked(True)
            checkbox.setStyleSheet("margin-left: 8px;")
            cb_widget = self.table.cellWidget(row, 0)
            self.table.setCellWidget(row, 0, checkbox)

            label = pred.get("label", "") or pred.get("category", "")
            code = str(pred.get("code", ""))
            home = pred.get("home", "")
            away = pred.get("away", "")
            scores = pred.get("scores", [])
            wdl = pred.get("wdl", [])

            if self.mode == "bd":
                # BD：机构名为主展示
                display_label = label or f"北单{code}"
            else:
                # JC：编号为主展示
                display_label = code.zfill(3) if code else label

            score_str = " ".join(str(s) for s in (scores[0] if scores and isinstance(scores[0], list) else scores))

            items = [
                display_label,
                home,
                away,
                score_str,
                " ".join(str(w) for w in wdl),
            ]
            for col, text in enumerate(items, start=1):
                item = QTableWidgetItem(text)
                item.setFlags(item.flags() & ~Qt.ItemIsEditable)
                self.table.setItem(row, col, item)

    def _set_all_checked(self, checked: bool):
        """全选/全不选"""
        for row in range(self.table.rowCount()):
            cb = self.table.cellWidget(row, 0)
            if isinstance(cb, QCheckBox):
                cb.setChecked(checked)

    def get_selected(self) -> list:
        """返回用户勾选的 predictions"""
        selected = []
        for row in range(self.table.rowCount()):
            cb = self.table.cellWidget(row, 0)
            if isinstance(cb, QCheckBox) and cb.isChecked():
                selected.append(self.predictions[row])
        return selected

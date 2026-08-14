"""AI 提取结果预览对话框 — 表格展示，可勾选行，可编辑比分，历史复用"""
import os

from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QTableWidget,
                             QTableWidgetItem, QHeaderView, QPushButton,
                             QCheckBox, QLabel, QTextEdit)
from PyQt5.QtCore import Qt


class AiPreviewDialog(QDialog):
    """AI 提取结果预览：表格展示，用户勾选/编辑要填入的行"""

    def __init__(self, predictions: list, mode: str = "bd", parent=None,
                 raw: str = "", method: str = "", source_file: str = ""):
        super().__init__(parent)
        self.mode = mode
        self.raw = raw
        self.method = method
        self.source_file = source_file
        self.setWindowTitle("AI 预测结果预览")
        self.setGeometry(300, 200, 760, 500)

        layout = QVBoxLayout()

        # 来源信息
        source_info = f"来源：{os.path.basename(source_file) if source_file else '未知'} | 解析方式：{method or '未知'}"
        hint = QLabel(source_info)
        hint.setStyleSheet("color: #555; font-size: 11px;")
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

        raw_btn = QPushButton("📄 AI 原始返回")
        raw_btn.clicked.connect(self._show_raw)
        btn_layout.addWidget(raw_btn)
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
            checkbox = QCheckBox()
            checkbox.setChecked(True)
            checkbox.setStyleSheet("margin-left: 8px;")
            self.table.setCellWidget(row, 0, checkbox)

            label = pred.get("label", "") or pred.get("category", "")
            code = str(pred.get("code", ""))
            home = pred.get("home", "")
            away = pred.get("away", "")
            scores = pred.get("scores", [])
            wdl = pred.get("wdl", [])

            if self.mode == "bd":
                display_label = label or f"北单{code}"
            else:
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
                # 比分列(col 4)可编辑，其余只读
                if col == 4:
                    item.setFlags(item.flags() | Qt.ItemIsEditable)
                else:
                    item.setFlags(item.flags() & ~Qt.ItemIsEditable)
                self.table.setItem(row, col, item)

    def _set_all_checked(self, checked: bool):
        """全选/全不选"""
        for row in range(self.table.rowCount()):
            cb = self.table.cellWidget(row, 0)
            if isinstance(cb, QCheckBox):
                cb.setChecked(checked)

    def _show_raw(self):
        """弹出只读对话框展示 AI 原始返回"""
        dlg = QDialog(self)
        dlg.setWindowTitle("AI 原始返回")
        dlg.setGeometry(300, 150, 700, 600)
        layout = QVBoxLayout(dlg)
        text = QTextEdit()
        text.setReadOnly(True)
        text.setPlainText(self.raw if self.raw else "(无原始返回)")
        layout.addWidget(text)
        close_btn = QPushButton("关闭")
        close_btn.clicked.connect(dlg.accept)
        layout.addWidget(close_btn)
        dlg.exec_()

    def get_selected(self) -> list:
        """返回用户勾选的 predictions（含表格中手动修改的比分）"""
        selected = []
        for row in range(self.table.rowCount()):
            cb = self.table.cellWidget(row, 0)
            if isinstance(cb, QCheckBox) and cb.isChecked():
                pred = dict(self.predictions[row])
                # 读取表格中可能被修改的比分
                score_item = self.table.item(row, 4)
                if score_item and score_item.text().strip():
                    edited = score_item.text().strip()
                    if self.mode == "bd":
                        # BD：空格分隔的多个比分对
                        parts = edited.split()
                        new_scores = []
                        i = 0
                        while i < len(parts):
                            if i + 1 < len(parts) and parts[i].isdigit() and parts[i+1].isdigit() and len(parts[i]) == 2 and len(parts[i+1]) == 2:
                                new_scores.append([parts[i], parts[i+1]])
                                i += 2
                            else:
                                new_scores.append([parts[i]])
                                i += 1
                        pred["scores"] = new_scores
                    else:
                        # JC：直接拆分
                        pred["scores"] = [s for s in edited.split() if s]
                selected.append(pred)
        return selected
import os
from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel,
                             QLineEdit, QPushButton, QFileDialog, QMessageBox,
                             QComboBox)
from PyQt5.QtCore import QSettings
from openpyxl import load_workbook


class SettingsDialog(QDialog):
    """设置对话框：配置 mapping/HTML/Excel/JSON 路径及 sheet"""

    def __init__(self, current_paths: dict, parent=None):
        """
        current_paths: {
            'mapping_path': str,
            'html_folder_path': str,
            'excel_path': str,
            'json_path': str,
            'sheet_name': str,
        }
        """
        super().__init__(parent)
        self.setWindowTitle("设置")
        self.setGeometry(400, 300, 620, 320)

        self.initial_paths = dict(current_paths)
        self.current_paths = dict(current_paths)
        self._changed = False

        layout = QVBoxLayout()

        # --- Mapping 文件 ---
        mapping_layout = QHBoxLayout()
        mapping_layout.addWidget(QLabel("映射文件路径:"))
        self.mapping_edit = QLineEdit(current_paths.get('mapping_path', ''))
        mapping_btn = QPushButton("浏览...")
        mapping_btn.clicked.connect(lambda: self._browse_file('mapping_edit'))
        mapping_layout.addWidget(self.mapping_edit)
        mapping_layout.addWidget(mapping_btn)
        layout.addLayout(mapping_layout)

        # --- HTML 文件夹 ---
        html_layout = QHBoxLayout()
        html_layout.addWidget(QLabel("HTML文件夹路径:"))
        self.html_edit = QLineEdit(current_paths.get('html_folder_path', ''))
        html_btn = QPushButton("浏览...")
        html_btn.clicked.connect(lambda: self._browse_folder('html_edit'))
        html_layout.addWidget(self.html_edit)
        html_layout.addWidget(html_btn)
        layout.addLayout(html_layout)

        # --- Excel 文件 ---
        excel_layout = QHBoxLayout()
        excel_layout.addWidget(QLabel("Excel文件路径:"))
        self.excel_edit = QLineEdit(current_paths.get('excel_path', ''))
        excel_btn = QPushButton("浏览...")
        excel_btn.clicked.connect(self._browse_excel)
        excel_layout.addWidget(self.excel_edit)
        excel_layout.addWidget(excel_btn)
        layout.addLayout(excel_layout)

        # --- Sheet 选择 ---
        sheet_layout = QHBoxLayout()
        sheet_layout.addWidget(QLabel("选择Sheet:"))
        self.sheet_combo = QComboBox()
        self.sheet_combo.setEnabled(False)
        sheet_layout.addWidget(self.sheet_combo)
        sheet_layout.addStretch()
        layout.addLayout(sheet_layout)

        # --- JSON 文件 ---
        json_layout = QHBoxLayout()
        json_layout.addWidget(QLabel("JSON文件路径:"))
        self.json_edit = QLineEdit(current_paths.get('json_path', ''))
        json_btn = QPushButton("浏览...")
        json_btn.clicked.connect(lambda: self._browse_file('json_edit'))
        json_layout.addWidget(self.json_edit)
        json_layout.addWidget(json_btn)
        layout.addLayout(json_layout)

        # --- 按钮 ---
        btn_layout = QHBoxLayout()
        apply_btn = QPushButton("应用")
        cancel_btn = QPushButton("取消")
        apply_btn.clicked.connect(self._on_apply)
        cancel_btn.clicked.connect(self._on_cancel)
        btn_layout.addWidget(apply_btn)
        btn_layout.addWidget(cancel_btn)
        layout.addLayout(btn_layout)

        self.setLayout(layout)

        # 路径变化检测
        self.mapping_edit.textChanged.connect(self._mark_changed)
        self.html_edit.textChanged.connect(self._mark_changed)
        self.excel_edit.textChanged.connect(self._mark_changed)
        self.json_edit.textChanged.connect(self._mark_changed)

        # Excel 路径变化时自动加载 sheet 列表（去抖动用用户手动操作）
        self.excel_edit.editingFinished.connect(self._load_sheets)
        # 初始化时加载 sheet
        if current_paths.get('excel_path'):
            self._load_sheets(init_sheet=current_paths.get('sheet_name', ''))

    def _mark_changed(self):
        self._changed = True

    def _browse_folder(self, target_edit):
        folder = QFileDialog.getExistingDirectory(self, "选择文件夹")
        if folder:
            getattr(self, target_edit).setText(folder)

    def _browse_file(self, target_edit):
        file, _ = QFileDialog.getOpenFileName(self, "选择文件", filter="All Files (*)")
        if file:
            getattr(self, target_edit).setText(file)

    def _browse_excel(self):
        file, _ = QFileDialog.getOpenFileName(self, "选择Excel文件",
                                              filter="Excel Files (*.xlsx *.xls)")
        if file:
            self.excel_edit.setText(file)
            self._load_sheets()

    def _load_sheets(self, init_sheet=None):
        """加载 Excel 文件的 sheet 列表"""
        excel_path = self.excel_edit.text()
        if not excel_path or not os.path.exists(excel_path):
            self.sheet_combo.clear()
            self.sheet_combo.setEnabled(False)
            return
        try:
            wb = load_workbook(filename=excel_path, read_only=True)
            sheet_names = wb.sheetnames
            self.sheet_combo.clear()
            self.sheet_combo.addItems(sheet_names)
            self.sheet_combo.setEnabled(True)
            # 选择指定的 sheet 或默认第一个
            if init_sheet and init_sheet in sheet_names:
                self.sheet_combo.setCurrentText(init_sheet)
            elif sheet_names:
                self.sheet_combo.setCurrentIndex(0)
        except Exception:
            self.sheet_combo.clear()
            self.sheet_combo.setEnabled(False)

    def _on_apply(self):
        """保存设置到 QSettings 并接受对话框"""
        settings = QSettings("config.ini", QSettings.IniFormat)
        settings.setValue("paths/mapping_path", self.mapping_edit.text())
        settings.setValue("paths/html_folder_path", self.html_edit.text())
        settings.setValue("paths/excel_path", self.excel_edit.text())
        settings.setValue("paths/json_path", self.json_edit.text())
        sheet = self.sheet_combo.currentText() if self.sheet_combo.isEnabled() else ""
        settings.setValue("paths/sheet_name", sheet)

        self.current_paths = {
            'mapping_path': self.mapping_edit.text(),
            'html_folder_path': self.html_edit.text(),
            'excel_path': self.excel_edit.text(),
            'json_path': self.json_edit.text(),
            'sheet_name': sheet,
        }
        self._changed = False
        self.accept()

    def _on_cancel(self):
        """取消时如有修改则提示是否保存"""
        if self._changed:
            reply = QMessageBox.question(
                self, "确认",
                "是否保存更改?",
                QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel,
                QMessageBox.Cancel
            )
            if reply == QMessageBox.Yes:
                self._on_apply()
                return
            elif reply == QMessageBox.Cancel:
                return
        self.reject()

    def get_paths(self) -> dict:
        return self.current_paths

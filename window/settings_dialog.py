import os
from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel,
                             QLineEdit, QPushButton, QFileDialog, QMessageBox,
                             QComboBox, QTabWidget, QTableWidget, QTableWidgetItem,
                             QGroupBox, QWidget, QHeaderView, QCheckBox, QTextEdit)
from PyQt5.QtCore import QSettings
from openpyxl import load_workbook
from src.mapping_manager import (get_match_dict, get_default_match_dict, save_match_dict,
                                  get_keyboard_mappings, get_default_keyboard_mappings,
                                  save_keyboard_mappings)
from src import ai_config


class SettingsDialog(QDialog):
    """设置对话框：路径配置 + 映射关系管理"""

    def __init__(self, current_paths: dict, parent=None, txt_dir: str = ""):
        super().__init__(parent)
        self.setWindowTitle("设置")
        self.setGeometry(400, 300, 650, 680)
        self.txt_dir = txt_dir

        self.initial_paths = dict(current_paths)
        self.current_paths = dict(current_paths)
        self._changed = False

        main_layout = QVBoxLayout()
        tabs = QTabWidget()

        # === Tab 1: 路径设置 ===
        path_tab = QWidget()
        path_layout = QVBoxLayout(path_tab)

        # -- JC 模式 --
        jc_group = QGroupBox("JC模式")
        jc_layout = QVBoxLayout(jc_group)
        self._build_path_row(jc_layout, "映射文件路径:", 'mapping_path',
                             lambda: self._browse_file('mapping_edit'))
        self._build_path_row(jc_layout, "HTML文件夹路径:", 'html_folder_path',
                             lambda: self._browse_folder('html_edit'))
        self._build_path_row(jc_layout, "Excel文件路径:", 'excel_path',
                             lambda: self._browse_excel('excel_edit', 'sheet_combo'))

        jc_sheet_layout = QHBoxLayout()
        jc_sheet_layout.addWidget(QLabel("选择Sheet:"))
        self.sheet_combo = QComboBox()
        self.sheet_combo.setEnabled(False)
        jc_sheet_layout.addWidget(self.sheet_combo)
        jc_sheet_layout.addStretch()
        jc_layout.addLayout(jc_sheet_layout)

        self._build_path_row(jc_layout, "JSON文件路径:", 'json_path',
                             lambda: self._browse_file('json_edit'))
        path_layout.addWidget(jc_group)

        # -- BD 模式 --
        bd_group = QGroupBox("北单模式")
        bd_layout = QVBoxLayout(bd_group)
        self._build_path_row(bd_layout, "北单文件夹路径:", 'bd_folder_path',
                             lambda: self._browse_folder('bd_folder_edit'))
        self._build_path_row(bd_layout, "BD Excel文件路径:", 'bd_excel_path',
                             lambda: self._browse_excel('bd_excel_edit', 'bd_sheet_combo'))

        bd_sheet_layout = QHBoxLayout()
        bd_sheet_layout.addWidget(QLabel("选择Sheet:"))
        self.bd_sheet_combo = QComboBox()
        self.bd_sheet_combo.setEnabled(False)
        bd_sheet_layout.addWidget(self.bd_sheet_combo)
        bd_sheet_layout.addStretch()
        bd_layout.addLayout(bd_sheet_layout)

        self._build_path_row(bd_layout, "BD JSON文件路径:", 'bd_json_path',
                             lambda: self._browse_file('bd_json_edit'))
        path_layout.addWidget(bd_group)

        # -- 图片数据目录 --
        txt_group = QGroupBox("图片数据")
        txt_layout = QHBoxLayout(txt_group)
        txt_layout.addWidget(QLabel("图片数据目录:"))
        self.txt_dir_edit = QLineEdit(self.txt_dir)
        self.txt_dir_edit.setReadOnly(True)
        txt_layout.addWidget(self.txt_dir_edit)
        open_txt_btn = QPushButton("打开目录")
        open_txt_btn.clicked.connect(self._open_txt_dir)
        txt_layout.addWidget(open_txt_btn)
        path_layout.addWidget(txt_group)

        path_layout.addStretch()
        tabs.addTab(path_tab, "路径设置")

        # === Tab 2: 映射设置 ===
        mapping_tab = QWidget()
        mapping_layout = QVBoxLayout(mapping_tab)

        # -- MATCH_DICT 表格 --
        match_group = QGroupBox("比赛结果映射 (MATCH_DICT)")
        match_group_layout = QVBoxLayout(match_group)
        self.match_table = QTableWidget()
        self.match_table.setColumnCount(2)
        self.match_table.setHorizontalHeaderLabels(["简写", "中文含义"])
        self.match_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self._init_mapping_table(self.match_table)
        match_btn_layout = self._build_table_buttons(
            self.match_table,
            lambda: self._add_table_row(self.match_table),
            lambda: self._delete_selected_rows(self.match_table),
            lambda: self._reset_match_table()
        )
        match_group_layout.addWidget(self.match_table)
        match_group_layout.addLayout(match_btn_layout)
        mapping_layout.addWidget(match_group)

        # -- 键盘映射表格 --
        key_group = QGroupBox("键盘映射")
        key_group_layout = QVBoxLayout(key_group)
        self.keyboard_table = QTableWidget()
        self.keyboard_table.setColumnCount(2)
        self.keyboard_table.setHorizontalHeaderLabels(["按键", "替换为"])
        self.keyboard_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self._init_mapping_table(self.keyboard_table)
        key_btn_layout = self._build_table_buttons(
            self.keyboard_table,
            lambda: self._add_table_row(self.keyboard_table),
            lambda: self._delete_selected_rows(self.keyboard_table),
            lambda: self._reset_keyboard_table()
        )
        key_group_layout.addWidget(self.keyboard_table)
        key_group_layout.addLayout(key_btn_layout)
        mapping_layout.addWidget(key_group)

        tabs.addTab(mapping_tab, "映射设置")

        # === Tab 3: 名称映射 ===
        name_tab = QWidget()
        name_layout = QVBoxLayout(name_tab)
        self.name_mapping_table = QTableWidget()
        self.name_mapping_table.setColumnCount(2)
        self.name_mapping_table.setHorizontalHeaderLabels(["短名称", "全名称"])
        self.name_mapping_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self._init_mapping_table(self.name_mapping_table)
        name_btn_layout = self._build_table_buttons(
            self.name_mapping_table,
            lambda: self._add_table_row(self.name_mapping_table),
            lambda: self._delete_selected_rows(self.name_mapping_table),
            lambda: self._reset_name_mapping_table()
        )
        name_layout.addWidget(self.name_mapping_table)
        name_layout.addLayout(name_btn_layout)
        tabs.addTab(name_tab, "名称映射")

        # === Tab 4: AI 设置 ===
        ai_tab = QWidget()
        ai_layout = QVBoxLayout(ai_tab)

        # API Key
        ai_key_row = QHBoxLayout()
        ai_key_row.addWidget(QLabel("API Key:"))
        self.ai_key_edit = QLineEdit()
        self.ai_key_edit.setEchoMode(QLineEdit.Password)
        self.ai_key_edit.setPlaceholderText("输入 API Key（保存后不可见）")
        ai_key_row.addWidget(self.ai_key_edit)
        ai_key_row.addWidget(QLabel("显示"))
        self.ai_show_check = QCheckBox()
        self.ai_show_check.toggled.connect(self._on_ai_show_toggle)
        ai_key_row.addWidget(self.ai_show_check)
        ai_layout.addLayout(ai_key_row)

        # 状态标签
        self.ai_status_label = QLabel()
        ai_layout.addWidget(self.ai_status_label)

        # 模型
        ai_model_row = QHBoxLayout()
        ai_model_row.addWidget(QLabel("模型:"))
        self.ai_model_edit = QLineEdit(ai_config.get_model())
        ai_model_row.addWidget(self.ai_model_edit)
        ai_layout.addLayout(ai_model_row)

        # 基址
        ai_base_row = QHBoxLayout()
        ai_base_row.addWidget(QLabel("API 基址:"))
        self.ai_base_edit = QLineEdit(ai_config.get_base_url())
        ai_base_row.addWidget(self.ai_base_edit)
        ai_layout.addLayout(ai_base_row)

        # 删除按钮
        ai_del_row = QHBoxLayout()
        ai_del_btn = QPushButton("🗑️ 删除 API Key")
        ai_del_btn.clicked.connect(self._on_ai_key_delete)
        ai_del_row.addWidget(ai_del_btn)
        ai_del_row.addStretch()
        ai_layout.addLayout(ai_del_row)

        # HTML/文本提示词
        ai_layout.addWidget(QLabel("HTML/文本提示词（AI 分析时使用）："))
        self.ai_prompt_edit = QTextEdit(ai_config.get_system_prompt())
        self.ai_prompt_edit.setMaximumHeight(140)
        ai_layout.addWidget(self.ai_prompt_edit)

        # 图片提示词
        ai_layout.addWidget(QLabel("图片提示词（OCR 识别后使用）："))
        self.ai_prompt_pic_edit = QTextEdit(ai_config.get_system_prompt_pic())
        self.ai_prompt_pic_edit.setMaximumHeight(140)
        ai_layout.addWidget(self.ai_prompt_pic_edit)

        # 恢复默认提示词
        prompt_reset_row = QHBoxLayout()
        prompt_reset_btn = QPushButton("🔄 恢复默认提示词")
        prompt_reset_btn.clicked.connect(self._on_ai_prompt_reset)
        prompt_reset_row.addWidget(prompt_reset_btn)
        prompt_reset_row.addStretch()
        ai_layout.addLayout(prompt_reset_row)

        ai_layout.addStretch()
        tabs.addTab(ai_tab, "AI 设置")

        main_layout.addWidget(tabs)

        # --- 底部按钮 ---
        btn_layout = QHBoxLayout()
        apply_btn = QPushButton("应用")
        cancel_btn = QPushButton("取消")
        apply_btn.clicked.connect(self._on_apply)
        cancel_btn.clicked.connect(self._on_cancel)
        btn_layout.addWidget(apply_btn)
        btn_layout.addWidget(cancel_btn)
        main_layout.addLayout(btn_layout)

        self.setLayout(main_layout)

        # 路径变化检测
        self.mapping_edit.textChanged.connect(self._mark_changed)
        self.html_edit.textChanged.connect(self._mark_changed)
        self.excel_edit.textChanged.connect(self._mark_changed)
        self.json_edit.textChanged.connect(self._mark_changed)
        self.bd_folder_edit.textChanged.connect(self._mark_changed)
        self.bd_excel_edit.textChanged.connect(self._mark_changed)
        self.bd_json_edit.textChanged.connect(self._mark_changed)

        # Excel 路径变化时加载 sheet（JC + BD）
        self.excel_edit.editingFinished.connect(
            lambda: self._load_sheets(self.excel_edit, self.sheet_combo))
        self.bd_excel_edit.editingFinished.connect(
            lambda: self._load_sheets(self.bd_excel_edit, self.bd_sheet_combo))
        if current_paths.get('excel_path'):
            self._load_sheets(self.excel_edit, self.sheet_combo,
                              init_sheet=current_paths.get('sheet_name', ''))
        if current_paths.get('bd_excel_path'):
            self._load_sheets(self.bd_excel_edit, self.bd_sheet_combo,
                              init_sheet=current_paths.get('bd_sheet_name', ''))

        # 填充映射表格
        self._populate_table(self.match_table, get_match_dict())
        self._populate_table(self.keyboard_table, get_keyboard_mappings())
        self._load_name_mapping_table()
        self._update_ai_status()

    # ---- Path tab helpers ----

    def _build_path_row(self, parent_layout, label_text, key, browse_callback):
        row = QHBoxLayout()
        row.addWidget(QLabel(label_text))
        edit = QLineEdit(self.current_paths.get(key, ''))
        btn = QPushButton("浏览...")
        btn.clicked.connect(browse_callback)
        row.addWidget(edit)
        row.addWidget(btn)
        parent_layout.addLayout(row)
        # Store edit widgets for access
        edit_map = {
            'mapping_path': 'mapping_edit',
            'html_folder_path': 'html_edit',
            'excel_path': 'excel_edit',
            'json_path': 'json_edit',
            'bd_folder_path': 'bd_folder_edit',
            'bd_excel_path': 'bd_excel_edit',
            'bd_json_path': 'bd_json_edit',
        }
        setattr(self, edit_map.get(key, f"{key}_edit"), edit)

    # ---- Mapping tab helpers ----

    def _init_mapping_table(self, table):
        table.setSelectionBehavior(QTableWidget.SelectRows)
        table.setColumnWidth(0, 100)

    def _build_table_buttons(self, table, add_fn, del_fn, reset_fn):
        layout = QHBoxLayout()
        add_btn = QPushButton("添加行")
        del_btn = QPushButton("删除选中行")
        reset_btn = QPushButton("重置默认值")
        add_btn.clicked.connect(add_fn)
        del_btn.clicked.connect(del_fn)
        reset_btn.clicked.connect(reset_fn)
        layout.addWidget(add_btn)
        layout.addWidget(del_btn)
        layout.addWidget(reset_btn)
        layout.addStretch()
        return layout

    def _add_table_row(self, table):
        row = table.rowCount()
        table.insertRow(row)
        table.setItem(row, 0, QTableWidgetItem(""))
        table.setItem(row, 1, QTableWidgetItem(""))
        table.editItem(table.item(row, 0))
        self._mark_changed()

    def _delete_selected_rows(self, table):
        selected = set()
        for idx in table.selectedIndexes():
            selected.add(idx.row())
        for row in sorted(selected, reverse=True):
            table.removeRow(row)
        if selected:
            self._mark_changed()

    def _read_table_to_dict(self, table) -> dict:
        result = {}
        for row in range(table.rowCount()):
            key_item = table.item(row, 0)
            val_item = table.item(row, 1)
            if key_item and key_item.text():
                key = key_item.text()
                # 保留空格等有效空白字符，仅去除首尾换行
                key = key.rstrip('\n\r')
                if key:
                    result[key] = val_item.text().rstrip('\n\r') if val_item else ""
        return result

    def _populate_table(self, table, data_dict: dict):
        table.setRowCount(0)
        for key, val in data_dict.items():
            row = table.rowCount()
            table.insertRow(row)
            table.setItem(row, 0, QTableWidgetItem(key))
            table.setItem(row, 1, QTableWidgetItem(val))

    def _reset_match_table(self):
        self._populate_table(self.match_table, get_default_match_dict())
        self._mark_changed()

    def _reset_keyboard_table(self):
        self._populate_table(self.keyboard_table, get_default_keyboard_mappings())
        self._mark_changed()

    def _load_name_mapping_table(self):
        """从 mapping_data.txt 加载名称映射到表格

        文件格式：短名称：全名称
        表格显示：Col0=短名称, Col1=全名称（与表头一致）
        """
        mapping_path = self.mapping_edit.text()
        mapping_dict = {}
        if mapping_path and os.path.exists(mapping_path):
            try:
                with open(mapping_path, 'r', encoding='utf-8') as f:
                    for line in f:
                        line = line.strip()
                        if line and "：" in line:
                            short_name, full_name = line.split("：", 1)
                            mapping_dict[short_name.strip()] = full_name.strip()
            except Exception:
                pass  # 文件无法读取时使用空表格
        self._populate_table(self.name_mapping_table, mapping_dict)

    def _reset_name_mapping_table(self):
        """重置名称映射表格为空（清空表格让用户手动输入）"""
        self.name_mapping_table.setRowCount(0)
        self._mark_changed()

    def _save_name_mapping_table(self):
        """将名称映射表格内容保存到 mapping_data.txt"""
        mapping_path = self.mapping_edit.text()
        if not mapping_path:
            return
        mapping_dict = self._read_table_to_dict(self.name_mapping_table)
        try:
            # 写入格式：短名称：全名称
            with open(mapping_path, 'w', encoding='utf-8') as f:
                for short_name, full_name in mapping_dict.items():
                    f.write(f"{short_name}：{full_name}\n")
        except Exception as e:
            QMessageBox.warning(self, "错误", f"保存名称映射文件失败: {str(e)}")

    # ---- Common ----

    def _mark_changed(self):
        self._changed = True

    # ---- AI 设置 ----
    def _on_ai_show_toggle(self, checked: bool):
        """显示勾选：临时显示明文"""
        self.ai_key_edit.setEchoMode(QLineEdit.Normal if checked else QLineEdit.Password)

    def _on_ai_key_delete(self):
        """删除 API Key"""
        if not ai_config.has_api_key():
            QMessageBox.information(self, "提示", "尚未配置 API Key")
            return
        reply = QMessageBox.question(
            self, "确认删除", "确定删除 API Key 吗？",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            ai_config.clear_api_key()
            self.ai_key_edit.clear()
            self._update_ai_status()
            self._mark_changed()

    def _update_ai_status(self):
        """更新 AI 状态标签"""
        if ai_config.has_api_key():
            self.ai_status_label.setText("状态：✅ 已配置（保存后不可见明文）")
            self.ai_status_label.setStyleSheet("color: #2E7D32; font-size: 11px;")
        else:
            self.ai_status_label.setText("状态：⚪ 未配置")
            self.ai_status_label.setStyleSheet("color: #999; font-size: 11px;")

    def _on_ai_prompt_reset(self):
        """恢复默认提示词"""
        self.ai_prompt_edit.setPlainText(ai_config.DEFAULT_SYSTEM_PROMPT)
        self.ai_prompt_pic_edit.setPlainText(ai_config.DEFAULT_SYSTEM_PROMPT_PIC)
        self._mark_changed()

    @staticmethod
    def _get_last_dir(key: str, default: str = "") -> str:
        settings = QSettings("config.ini", QSettings.IniFormat)
        return settings.value(f"last_dirs/{key}", default) or default

    @staticmethod
    def _save_last_dir(key: str, path: str):
        parent = os.path.dirname(path)
        if parent:
            settings = QSettings("config.ini", QSettings.IniFormat)
            settings.setValue(f"last_dirs/{key}", parent)

    def _browse_folder(self, target_edit):
        """先让用户选择 ZIP 或文件夹，再打开对应对话框"""
        msg = QMessageBox(self)
        msg.setWindowTitle("选择类型")
        msg.setText("请选择要添加的路径类型：")
        btn_zip = msg.addButton("📦 ZIP 压缩包", QMessageBox.ActionRole)
        btn_folder = msg.addButton("📁 文件夹", QMessageBox.ActionRole)
        msg.addButton("取消", QMessageBox.RejectRole)
        msg.exec_()

        clicked = msg.clickedButton()

        if clicked == btn_zip:
            last_dir = self._get_last_dir("html_folder")
            file_path, _ = QFileDialog.getOpenFileName(
                self, "选择ZIP压缩包", directory=last_dir, filter="ZIP 文件 (*.zip)"
            )
            if file_path:
                getattr(self, target_edit).setText(file_path)
                self._save_last_dir("html_folder", file_path)
        elif clicked == btn_folder:
            last_dir = self._get_last_dir("html_folder")
            folder = QFileDialog.getExistingDirectory(self, "选择文件夹", directory=last_dir)
            if folder:
                getattr(self, target_edit).setText(folder)
                self._save_last_dir("html_folder", folder)

    def _open_txt_dir(self):
        """在系统文件管理器中打开图片数据目录"""
        if not self.txt_dir or not os.path.exists(self.txt_dir):
            QMessageBox.warning(self, "提示", "图片数据目录不存在")
            return
        try:
            os.startfile(self.txt_dir)
        except Exception as e:
            QMessageBox.warning(self, "错误", f"打开目录失败: {str(e)}")

    def _browse_file(self, target_edit):
        last_dir = self._get_last_dir("json")
        file, _ = QFileDialog.getOpenFileName(self, "选择文件", directory=last_dir, filter="All Files (*)")
        if file:
            getattr(self, target_edit).setText(file)
            self._save_last_dir("json", file)

    def _browse_excel(self, edit_attr, combo_attr):
        last_dir = self._get_last_dir("excel")
        file, _ = QFileDialog.getOpenFileName(self, "选择Excel文件",
                                              directory=last_dir,
                                              filter="Excel Files (*.xlsx *.xls)")
        if file:
            getattr(self, edit_attr).setText(file)
            self._load_sheets(getattr(self, edit_attr), getattr(self, combo_attr))
            self._save_last_dir("excel", file)

    def _load_sheets(self, edit, combo, init_sheet=None):
        excel_path = edit.text()
        if not excel_path or not os.path.exists(excel_path):
            combo.clear()
            combo.setEnabled(False)
            return
        try:
            wb = load_workbook(filename=excel_path, read_only=True)
            sheet_names = wb.sheetnames
            combo.clear()
            combo.addItems(sheet_names)
            combo.setEnabled(True)
            if init_sheet and init_sheet in sheet_names:
                combo.setCurrentText(init_sheet)
            elif sheet_names:
                combo.setCurrentIndex(0)
        except Exception:
            combo.clear()
            combo.setEnabled(False)

    def _on_apply(self):
        """保存所有设置到 QSettings 并接受对话框"""
        settings = QSettings("config.ini", QSettings.IniFormat)
        # JC 路径设置
        settings.setValue("paths/mapping_path", self.mapping_edit.text())
        settings.setValue("paths/html_folder_path", self.html_edit.text())
        settings.setValue("paths/excel_path", self.excel_edit.text())
        settings.setValue("paths/json_path", self.json_edit.text())
        sheet = self.sheet_combo.currentText() if self.sheet_combo.isEnabled() else ""
        settings.setValue("paths/sheet_name", sheet)

        # BD 路径设置
        settings.setValue("paths/bd_folder_path", self.bd_folder_edit.text())
        settings.setValue("paths/bd_excel_path", self.bd_excel_edit.text())
        bd_sheet = self.bd_sheet_combo.currentText() if self.bd_sheet_combo.isEnabled() else ""
        settings.setValue("paths/bd_sheet_name", bd_sheet)
        settings.setValue("paths/bd_json_path", self.bd_json_edit.text())

        # AI 设置（api_key 为空时保留原值）
        ai_config.save_ai_config(
            self.ai_key_edit.text(),
            self.ai_model_edit.text(),
            self.ai_base_edit.text(),
        )
        # 保存提示词
        ai_config.save_system_prompts(
            self.ai_prompt_edit.toPlainText(),
            self.ai_prompt_pic_edit.toPlainText(),
        )

        self.current_paths = {
            'mapping_path': self.mapping_edit.text(),
            'html_folder_path': self.html_edit.text(),
            'excel_path': self.excel_edit.text(),
            'json_path': self.json_edit.text(),
            'sheet_name': sheet,
            'bd_folder_path': self.bd_folder_edit.text(),
            'bd_excel_path': self.bd_excel_edit.text(),
            'bd_sheet_name': bd_sheet,
            'bd_json_path': self.bd_json_edit.text(),
        }

        # 映射设置
        save_match_dict(self._read_table_to_dict(self.match_table))
        save_keyboard_mappings(self._read_table_to_dict(self.keyboard_table))
        self._save_name_mapping_table()

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

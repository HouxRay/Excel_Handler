import sys
from PyQt5.QtWidgets import (QApplication, QWidget, QPushButton,
                             QLineEdit, QLabel, QFileDialog, QHBoxLayout,
                             QVBoxLayout, QMessageBox, QDialog, QComboBox,
                             QGroupBox)
from PyQt5.QtGui import QTextCursor, QIcon
from PyQt5.QtCore import QSettings
import os, logging
from datetime import datetime
from openpyxl import load_workbook


def setup_logger(text_widget=None):
    # 创建logs目录（如果不存在）
    if not os.path.exists("logs"):
        os.makedirs("logs")

    # 生成日志文件名（使用当前日期）
    log_filename = f"logs/app_{datetime.now().strftime('%Y-%m-%d')}.log"

    # 配置日志格式
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')

    # 创建文件处理器
    file_handler = logging.FileHandler(log_filename, encoding='utf-8')
    file_handler.setFormatter(formatter)

    # 创建控制台处理器
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)

    # 创建日志记录器
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.INFO)

    # 防止重复添加处理器
    if not logger.handlers:
        # 添加处理器
        logger.addHandler(file_handler)
        logger.addHandler(console_handler)

    # 禁用日志传播，防止重复输出
    logger.propagate = False

    return logger

# 创建logger实例
logger = setup_logger()

class PathSelector(QDialog):
    def __init__(self):
        super().__init__()
        # (jc_folder, jc_excel, jc_json, jc_sheet, bd_folder, bd_excel, bd_sheet, bd_json)
        self.selected_paths = (None, None, None, None, None, None, None, None)
        self.jc_sheet_names = []
        self.bd_sheet_names = []
        self.initUI()

    def initUI(self):
        # 窗口设置
        self.setWindowTitle('路径选择器')
        self.setGeometry(300, 300, 550, 450)

        try:
            icon_path = "assets/pic.ico"  # 图标文件路径
            if os.path.exists(icon_path):
                self.setWindowIcon(QIcon(icon_path))
            else:
                logger.warning(f"图标文件未找到: {icon_path}")
        except Exception as e:
            logger.exception("设置窗口图标时发生错误")

        # =============================================
        # JC 模式分组
        # =============================================
        jc_group = QGroupBox("JC模式（HTML/图片）")
        jc_layout = QVBoxLayout()

        # JC 自动填入上次路径按钮
        jc_auto_row = QHBoxLayout()
        jc_auto_btn = QPushButton("🔄 自动填入上次JC路径")
        jc_auto_btn.setStyleSheet("""
            QPushButton {
                background-color: #E3F2FD; color: #1565C0; font-weight: bold;
                padding: 4px 8px; border-radius: 4px; border: 1px solid #90CAF9;
            }
            QPushButton:hover { background-color: #BBDEFB; }
        """)
        jc_auto_btn.clicked.connect(self._auto_fill_jc)
        jc_auto_row.addWidget(jc_auto_btn)
        jc_auto_row.addStretch()
        jc_layout.addLayout(jc_auto_row)

        # JC 文件夹
        jc_folder_layout = QHBoxLayout()
        self.jc_folder_label = QLabel('HTML文件夹路径:')
        self.jc_folder_line = QLineEdit()
        self.jc_folder_line.textChanged.connect(
            lambda t: self._update_path_indicator(t, self.jc_path_type))
        self.jc_path_type = QLabel('')
        self.jc_path_type.setFixedWidth(50)
        self.jc_path_type.setStyleSheet("color: #999; font-size: 10px;")
        self.jc_folder_btn = QPushButton('浏览...')
        self.jc_folder_btn.clicked.connect(self.select_jc_folder)
        jc_folder_layout.addWidget(self.jc_folder_label)
        jc_folder_layout.addWidget(self.jc_folder_line)
        jc_folder_layout.addWidget(self.jc_path_type)
        jc_folder_layout.addWidget(self.jc_folder_btn)

        # JC Excel
        jc_excel_layout = QHBoxLayout()
        self.jc_excel_label = QLabel('Excel文件路径:')
        self.jc_excel_line = QLineEdit()
        self.jc_excel_btn = QPushButton('浏览...')
        self.jc_excel_btn.clicked.connect(self.select_jc_excel)
        jc_excel_layout.addWidget(self.jc_excel_label)
        jc_excel_layout.addWidget(self.jc_excel_line)
        jc_excel_layout.addWidget(self.jc_excel_btn)

        # JC JSON
        jc_json_layout = QHBoxLayout()
        self.jc_json_label = QLabel('JSON文件路径:')
        self.jc_json_line = QLineEdit()
        self.jc_json_btn = QPushButton('浏览...')
        self.jc_json_btn.clicked.connect(self.select_jc_json)
        jc_json_layout.addWidget(self.jc_json_label)
        jc_json_layout.addWidget(self.jc_json_line)
        jc_json_layout.addWidget(self.jc_json_btn)

        # JC Sheet 下拉框
        jc_sheet_layout = QHBoxLayout()
        self.jc_sheet_label = QLabel('选择Sheet:')
        self.jc_sheet_combo = QComboBox()
        self.jc_sheet_combo.setEnabled(False)
        jc_sheet_layout.addWidget(self.jc_sheet_label)
        jc_sheet_layout.addWidget(self.jc_sheet_combo)

        jc_layout.addLayout(jc_folder_layout)
        jc_layout.addLayout(jc_excel_layout)
        jc_layout.addLayout(jc_json_layout)
        jc_layout.addLayout(jc_sheet_layout)
        jc_group.setLayout(jc_layout)

        # =============================================
        # BD 模式分组
        # =============================================
        bd_group = QGroupBox("北单模式")
        bd_layout = QVBoxLayout()

        # BD 自动填入上次路径按钮
        bd_auto_row = QHBoxLayout()
        bd_auto_btn = QPushButton("🔄 自动填入上次BD路径")
        bd_auto_btn.setStyleSheet("""
            QPushButton {
                background-color: #FFF3E0; color: #E65100; font-weight: bold;
                padding: 4px 8px; border-radius: 4px; border: 1px solid #FFCC80;
            }
            QPushButton:hover { background-color: #FFE0B2; }
        """)
        bd_auto_btn.clicked.connect(self._auto_fill_bd)
        bd_auto_row.addWidget(bd_auto_btn)
        bd_auto_row.addStretch()
        bd_layout.addLayout(bd_auto_row)

        # BD 文件夹
        bd_folder_layout = QHBoxLayout()
        self.bd_folder_label = QLabel('北单文件夹路径:')
        self.bd_folder_line = QLineEdit()
        self.bd_folder_line.textChanged.connect(
            lambda t: self._update_path_indicator(t, self.bd_path_type))
        self.bd_path_type = QLabel('')
        self.bd_path_type.setFixedWidth(50)
        self.bd_path_type.setStyleSheet("color: #999; font-size: 10px;")
        self.bd_folder_btn = QPushButton('浏览...')
        self.bd_folder_btn.clicked.connect(self.select_bd_folder)
        bd_folder_layout.addWidget(self.bd_folder_label)
        bd_folder_layout.addWidget(self.bd_folder_line)
        bd_folder_layout.addWidget(self.bd_path_type)
        bd_folder_layout.addWidget(self.bd_folder_btn)

        # BD Excel
        bd_excel_layout = QHBoxLayout()
        self.bd_excel_label = QLabel('BD Excel文件路径:')
        self.bd_excel_line = QLineEdit()
        self.bd_excel_btn = QPushButton('浏览...')
        self.bd_excel_btn.clicked.connect(self.select_bd_excel)
        bd_excel_layout.addWidget(self.bd_excel_label)
        bd_excel_layout.addWidget(self.bd_excel_line)
        bd_excel_layout.addWidget(self.bd_excel_btn)

        # BD JSON
        bd_json_layout = QHBoxLayout()
        self.bd_json_label = QLabel('BD JSON文件路径:')
        self.bd_json_line = QLineEdit()
        self.bd_json_btn = QPushButton('浏览...')
        self.bd_json_btn.clicked.connect(self.select_bd_json)
        bd_json_layout.addWidget(self.bd_json_label)
        bd_json_layout.addWidget(self.bd_json_line)
        bd_json_layout.addWidget(self.bd_json_btn)

        # BD Sheet 下拉框
        bd_sheet_layout = QHBoxLayout()
        self.bd_sheet_label = QLabel('选择Sheet:')
        self.bd_sheet_combo = QComboBox()
        self.bd_sheet_combo.setEnabled(False)
        bd_sheet_layout.addWidget(self.bd_sheet_label)
        bd_sheet_layout.addWidget(self.bd_sheet_combo)

        bd_layout.addLayout(bd_folder_layout)
        bd_layout.addLayout(bd_excel_layout)
        bd_layout.addLayout(bd_json_layout)
        bd_layout.addLayout(bd_sheet_layout)
        bd_group.setLayout(bd_layout)

        # =============================================
        # 确认按钮
        # =============================================
        self.confirm_btn = QPushButton('确认')
        self.confirm_btn.clicked.connect(self.on_confirm)

        # 主布局
        main_layout = QVBoxLayout()
        main_layout.addWidget(jc_group)
        main_layout.addWidget(bd_group)
        main_layout.addWidget(self.confirm_btn)

        self.setLayout(main_layout)
        self._load_from_settings()

    # ---------- JC 相关 ----------
    @staticmethod
    def _get_path_type(path: str) -> str:
        """判断路径是 ZIP 还是文件夹"""
        if not path:
            return ''
        if path.lower().endswith('.zip'):
            return 'ZIP'
        return '文件夹'

    def _update_path_indicator(self, path, label):
        """更新路径类型指示标签"""
        t = self._get_path_type(path)
        if t == 'ZIP':
            label.setText('📦ZIP')
            label.setStyleSheet("color: #E65100; font-size: 10px; font-weight: bold;")
        elif t == '文件夹':
            label.setText('📁文件夹')
            label.setStyleSheet("color: #2E7D32; font-size: 10px;")
        else:
            label.setText('')
            label.setStyleSheet("color: #999; font-size: 10px;")

    @staticmethod
    def _get_last_dir(key: str, default: str = "") -> str:
        """从 QSettings 读取上次浏览的目录"""
        settings = QSettings("config.ini", QSettings.IniFormat)
        return settings.value(f"last_dirs/{key}", default) or default

    @staticmethod
    def _save_last_dir(key: str, path: str):
        """保存目录到 QSettings"""
        parent = os.path.dirname(path)
        if parent:
            settings = QSettings("config.ini", QSettings.IniFormat)
            settings.setValue(f"last_dirs/{key}", parent)

    def _browse_html_path(self, line_edit, type_label, title):
        """先让用户选择 ZIP 或文件夹，再打开对应对话框"""
        msg = QMessageBox(self)
        msg.setWindowTitle("选择类型")
        msg.setText(f"{title}\n请选择要添加的路径类型：")
        btn_zip = msg.addButton("📦 ZIP 压缩包", QMessageBox.ActionRole)
        btn_folder = msg.addButton("📁 文件夹", QMessageBox.ActionRole)
        msg.addButton("取消", QMessageBox.RejectRole)
        msg.exec_()

        clicked = msg.clickedButton()

        if clicked == btn_zip:
            last_dir = self._get_last_dir("html_folder")
            file_path, _ = QFileDialog.getOpenFileName(
                self, title, directory=last_dir, filter="ZIP 文件 (*.zip)"
            )
            if file_path:
                line_edit.setText(file_path)
                self._update_path_indicator(file_path, type_label)
                self._save_last_dir("html_folder", file_path)
        elif clicked == btn_folder:
            last_dir = self._get_last_dir("html_folder")
            folder = QFileDialog.getExistingDirectory(self, title, directory=last_dir)
            if folder:
                line_edit.setText(folder)
                self._update_path_indicator(folder, type_label)
                self._save_last_dir("html_folder", folder)

    def select_jc_folder(self):
        self._browse_html_path(self.jc_folder_line, self.jc_path_type, '选择HTML文件夹或ZIP压缩包')

    def select_bd_folder(self):
        self._browse_html_path(self.bd_folder_line, self.bd_path_type, '选择北单文件夹或ZIP压缩包')

    def select_jc_excel(self):
        last_dir = self._get_last_dir("excel")
        file, _ = QFileDialog.getOpenFileName(self, '选择JC Excel文件',
                                            directory=last_dir,
                                            filter='Excel Files (*.xlsx *.xls)')
        if file:
            self.jc_excel_line.setText(file)
            self.load_jc_sheet_names(file)
            self._save_last_dir("excel", file)

    def select_jc_json(self):
        last_dir = self._get_last_dir("json")
        file, _ = QFileDialog.getOpenFileName(self, '选择JC JSON文件',
                                            directory=last_dir,
                                            filter='JSON Files (*.json)')
        if file:
            self.jc_json_line.setText(file)
            self._save_last_dir("json", file)

    def load_jc_sheet_names(self, excel_file):
        """加载JC Excel文件中的所有sheet名称"""
        try:
            wb = load_workbook(filename=excel_file, read_only=True)
            self.jc_sheet_names = wb.sheetnames
            self.jc_sheet_combo.clear()
            self.jc_sheet_combo.addItems(self.jc_sheet_names)
            self.jc_sheet_combo.setEnabled(True)
            if self.jc_sheet_names:
                self.jc_sheet_combo.setCurrentIndex(0)
            logger.info(f"加载JC Excel: {excel_file}, 找到 {len(self.jc_sheet_names)} 个sheet")
        except Exception as e:
            logger.error(f"加载JC Excel文件失败: {e}")
            QMessageBox.warning(self, "错误", f"无法读取JC Excel文件: {str(e)}")
            self.jc_sheet_combo.setEnabled(False)

    # ---------- BD 相关 ----------
    def select_bd_excel(self):
        last_dir = self._get_last_dir("excel")
        file, _ = QFileDialog.getOpenFileName(self, '选择BD Excel文件',
                                            directory=last_dir,
                                            filter='Excel Files (*.xlsx *.xls)')
        if file:
            self.bd_excel_line.setText(file)
            self.load_bd_sheet_names(file)
            self._save_last_dir("excel", file)

    def select_bd_json(self):
        last_dir = self._get_last_dir("json")
        file, _ = QFileDialog.getOpenFileName(self, '选择BD JSON文件',
                                            directory=last_dir,
                                            filter='JSON Files (*.json)')
        if file:
            self.bd_json_line.setText(file)
            self._save_last_dir("json", file)

    def load_bd_sheet_names(self, excel_file):
        """加载BD Excel文件中的所有sheet名称"""
        try:
            wb = load_workbook(filename=excel_file, read_only=True)
            self.bd_sheet_names = wb.sheetnames
            self.bd_sheet_combo.clear()
            self.bd_sheet_combo.addItems(self.bd_sheet_names)
            self.bd_sheet_combo.setEnabled(True)
            if self.bd_sheet_names:
                self.bd_sheet_combo.setCurrentIndex(0)
            logger.info(f"加载BD Excel: {excel_file}, 找到 {len(self.bd_sheet_names)} 个sheet")
        except Exception as e:
            logger.error(f"加载BD Excel文件失败: {e}")
            QMessageBox.warning(self, "错误", f"无法读取BD Excel文件: {str(e)}")
            self.bd_sheet_combo.setEnabled(False)

    # ---------- 自动填入上次路径 ----------
    def _auto_fill_jc(self):
        """从 config.ini 自动填入上次的 JC 路径"""
        settings = QSettings("config.ini", QSettings.IniFormat)
        folder = settings.value("paths/html_folder_path", "")
        excel = settings.value("paths/excel_path", "")
        json = settings.value("paths/json_path", "")
        sheet = settings.value("paths/sheet_name", "")

        if not folder and not excel:
            QMessageBox.information(self, "提示", "无上次 JC 路径记录")
            return

        if folder:
            self.jc_folder_line.setText(folder)
        if excel and os.path.exists(excel):
            self.jc_excel_line.setText(excel)
            self.load_jc_sheet_names(excel)
            if sheet and sheet in self.jc_sheet_names:
                self.jc_sheet_combo.setCurrentText(sheet)
        if json and os.path.exists(json):
            self.jc_json_line.setText(json)

    def _auto_fill_bd(self):
        """从 config.ini 自动填入上次的 BD 路径"""
        settings = QSettings("config.ini", QSettings.IniFormat)
        folder = settings.value("paths/bd_folder_path", "")
        excel = settings.value("paths/bd_excel_path", "")
        sheet = settings.value("paths/bd_sheet_name", "")
        json = settings.value("paths/bd_json_path", "")

        if not folder and not excel:
            QMessageBox.information(self, "提示", "无上次 BD 路径记录")
            return

        if folder:
            self.bd_folder_line.setText(folder)
        if excel and os.path.exists(excel):
            self.bd_excel_line.setText(excel)
            self.load_bd_sheet_names(excel)
            if sheet and sheet in self.bd_sheet_names:
                self.bd_sheet_combo.setCurrentText(sheet)
        if json and os.path.exists(json):
            self.bd_json_line.setText(json)

    # ---------- 通用 ----------
    def on_confirm(self):
        jc_folder = self.jc_folder_line.text()
        jc_excel = self.jc_excel_line.text()
        jc_json = self.jc_json_line.text()
        jc_sheet = self.jc_sheet_combo.currentText() if self.jc_sheet_combo.isEnabled() else None

        bd_folder = self.bd_folder_line.text()
        bd_excel = self.bd_excel_line.text()
        bd_sheet = self.bd_sheet_combo.currentText() if self.bd_sheet_combo.isEnabled() else None
        bd_json = self.bd_json_line.text()

        # 至少选择一个模式
        if not jc_folder and not jc_excel and not bd_folder and not bd_excel:
            QMessageBox.warning(self, "警告", "请至少填写 JC 或 BD 的路径信息")
            return

        # JC Excel 必填（如果有 JC 文件夹）
        if jc_folder and not jc_excel:
            QMessageBox.warning(self, "警告", "选择了 JC HTML 文件夹，请选择对应的 JC Excel 文件")
            return

        # 如果填了 JC Excel，必须有 JC Sheet
        if jc_excel and not jc_sheet:
            QMessageBox.warning(self, "警告", "请为 JC Excel 选择 Sheet")
            return

        # 如果填了 BD Excel，必须有 BD Sheet
        if bd_excel and not bd_sheet:
            QMessageBox.warning(self, "警告", "请为 BD Excel 选择 Sheet")
            return

        self.selected_paths = (jc_folder, jc_excel, jc_json, jc_sheet,
                               bd_folder, bd_excel, bd_sheet, bd_json)
        self.accept()

    def _load_from_settings(self):
        """从 config.ini 加载非路径设置（如 mapping_path、sheet 匹配）"""
        settings = QSettings("config.ini", QSettings.IniFormat)

        # 只保留 sheet 名称的匹配（不预填路径）
        bd_sheet = settings.value("paths/bd_sheet_name", "")
        if bd_sheet and bd_sheet in self.bd_sheet_names:
            idx = self.bd_sheet_combo.findText(bd_sheet)
            if idx >= 0:
                self.bd_sheet_combo.setCurrentIndex(idx)

    def run(self):
        app = QApplication(sys.argv)
        self.show()
        app.exec_()
        return getattr(self, 'selected_paths', (None, None, None, None, None, None, None, None))

if __name__ == '__main__':
    app = QApplication(sys.argv)
    ex = PathSelector()
    paths = ex.run()
    print(paths)

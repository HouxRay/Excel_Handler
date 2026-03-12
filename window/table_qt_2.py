import sys
from PyQt5.QtWidgets import (QApplication, QWidget, QPushButton, 
                             QLineEdit, QLabel, QFileDialog, QHBoxLayout, 
                             QVBoxLayout, QMessageBox, QDialog, QComboBox)
from PyQt5.QtGui import QTextCursor, QIcon
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
        self.selected_paths = (None, None, None, None)  # 初始化路径存储 (folder, file, json, sheet)
        self.sheet_names = []
        self.initUI()

    def initUI(self):
        # 窗口设置
        self.setWindowTitle('路径选择器')
        self.setGeometry(300, 300, 500, 200)
        
        try:
            icon_path = "assets/pic.ico"  # 图标文件路径
            if os.path.exists(icon_path):
                self.setWindowIcon(QIcon(icon_path))
            else:
                logger.warning(f"图标文件未找到: {icon_path}")
        except Exception as e:
            logger.exception("设置窗口图标时发生错误")

        # 文件夹路径选择组件
        self.folder_label = QLabel('文件夹路径:')
        self.folder_line = QLineEdit()
        self.folder_btn = QPushButton('浏览...')
        self.folder_btn.clicked.connect(self.select_folder)

        # Excel文件选择组件
        self.file_label = QLabel('Excel文件路径:')
        self.file_line = QLineEdit()
        self.file_btn = QPushButton('浏览...')
        self.file_btn.clicked.connect(self.select_file)

        # JSON文件选择组件
        self.json_label = QLabel('JSON文件路径:')
        self.json_line = QLineEdit()
        self.json_btn = QPushButton('浏览...')
        self.json_btn.clicked.connect(self.select_json)

        # Sheet选择组件
        self.sheet_label = QLabel('选择Sheet:')
        self.sheet_combo = QComboBox()
        self.sheet_combo.setEnabled(False)  # 初始禁用，选择Excel文件后启用

        # 确认按钮
        self.confirm_btn = QPushButton('确认')
        self.confirm_btn.clicked.connect(self.on_confirm)

        # 布局管理
        folder_layout = QHBoxLayout()
        folder_layout.addWidget(self.folder_label)
        folder_layout.addWidget(self.folder_line)
        folder_layout.addWidget(self.folder_btn)

        file_layout = QHBoxLayout()
        file_layout.addWidget(self.file_label)
        file_layout.addWidget(self.file_line)
        file_layout.addWidget(self.file_btn)

        json_layout = QHBoxLayout()
        json_layout.addWidget(self.json_label)
        json_layout.addWidget(self.json_line)
        json_layout.addWidget(self.json_btn)

        sheet_layout = QHBoxLayout()
        sheet_layout.addWidget(self.sheet_label)
        sheet_layout.addWidget(self.sheet_combo)

        main_layout = QVBoxLayout()
        main_layout.addLayout(folder_layout)
        main_layout.addLayout(file_layout)
        main_layout.addLayout(json_layout)
        main_layout.addLayout(sheet_layout)
        main_layout.addWidget(self.confirm_btn)

        self.setLayout(main_layout)

    def select_folder(self):
        folder = QFileDialog.getExistingDirectory(self, '选择文件夹')
        if folder:
            self.folder_line.setText(folder)

    def select_file(self):
        file, _ = QFileDialog.getOpenFileName(self, '选择Excel文件', 
                                            filter='Excel Files (*.xlsx *.xls)')
        if file:
            self.file_line.setText(file)
            # 加载Excel文件的sheet名称
            self.load_sheet_names(file)
    
    def load_sheet_names(self, excel_file):
        """加载Excel文件中的所有sheet名称"""
        try:
            # 使用openpyxl加载工作簿（只读取sheet名称，不加载数据）
            wb = load_workbook(filename=excel_file, read_only=True)
            self.sheet_names = wb.sheetnames
            
            # 清空并更新下拉框
            self.sheet_combo.clear()
            self.sheet_combo.addItems(self.sheet_names)
            self.sheet_combo.setEnabled(True)
            
            # 默认选择第一个sheet
            if self.sheet_names:
                self.sheet_combo.setCurrentIndex(0)
                
            logger.info(f"加载Excel文件: {excel_file}, 找到 {len(self.sheet_names)} 个sheet")
            
        except Exception as e:
            logger.error(f"加载Excel文件失败: {e}")
            QMessageBox.warning(self, "错误", f"无法读取Excel文件: {str(e)}")
            self.sheet_combo.setEnabled(False)

    def select_json(self):
        file, _ = QFileDialog.getOpenFileName(self, '选择JSON文件', 
                                            filter='JSON Files (*.json)')
        if file:
            self.json_line.setText(file)

    def on_confirm(self):
        folder_path = self.folder_line.text()
        file_path = self.file_line.text()
        json_path = self.json_line.text()
        selected_sheet = self.sheet_combo.currentText() if self.sheet_combo.isEnabled() else None
        
        if not folder_path or not file_path:
            QMessageBox.warning(self, "警告", "必须选择文件夹和Excel文件")
            return
        
        if not selected_sheet:
            QMessageBox.warning(self, "警告", "请选择Excel sheet！")
            return
            
        self.selected_paths = (folder_path, file_path, json_path, selected_sheet)
        self.accept()  # 使用accept()关闭对话框

    def run(self):
        app = QApplication(sys.argv)
        self.show()
        app.exec_()
        # 返回存储的路径 (folder, file, json, sheet)
        return getattr(self, 'selected_paths', (None, None, None, None))

if __name__ == '__main__':
    app = QApplication(sys.argv)
    ex = PathSelector()
    paths = ex.run()
    print(paths)
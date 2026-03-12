import sys
from PyQt5.QtWidgets import (QApplication, QWidget, QPushButton, 
                             QLineEdit, QLabel, QFileDialog, QHBoxLayout, QVBoxLayout, QMessageBox, QDialog)

class PathSelector(QDialog):
    def __init__(self):
        super().__init__()
        self.selected_paths = (None, None)  # 初始化路径存储
        self.initUI()

    def initUI(self):
        # 窗口设置
        self.setWindowTitle('路径选择器')
        self.setGeometry(300, 300, 500, 150)

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

        main_layout = QVBoxLayout()
        main_layout.addLayout(folder_layout)
        main_layout.addLayout(file_layout)
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

    def on_confirm(self):
        folder_path = self.folder_line.text()
        file_path = self.file_line.text()
        
        if not folder_path or not file_path:
            QMessageBox.warning(self, "警告", "必须选择文件夹和Excel文件")
            return
            
        self.selected_paths = (folder_path, file_path)
        self.accept()  # 使用accept()关闭对话框

    def run(self):
        app = QApplication(sys.argv)
        self.show()
        app.exec_()
        # 返回存储的路径
        return getattr(self, 'selected_paths', (None, None))

if __name__ == '__main__':
    app = QApplication(sys.argv)
    ex = PathSelector()
    paths = ex.run()
    print(paths)
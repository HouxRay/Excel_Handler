import sys
from PyQt5.QtCore import QUrl  # 添加 QUrl 导入
from PyQt5.QtWidgets import QApplication, QWidget, QVBoxLayout, QPushButton, QFileDialog
from PyQt5.QtWebEngineWidgets import QWebEngineView

class HtmlViewer(QWidget):
    def __init__(self):
        super().__init__()
        self.initUI()

    def initUI(self):
        self.setWindowTitle('HTML 查看器')
        self.setGeometry(100, 100, 800, 600)
        
        layout = QVBoxLayout()
        self.setLayout(layout)
        
        self.btn = QPushButton('打开 HTML 文件', self)
        self.btn.clicked.connect(self.open_file)
        layout.addWidget(self.btn)
        
        self.webView = QWebEngineView()
        layout.addWidget(self.webView)

    def open_file(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, '选择 HTML 文件', '', 'HTML 文件 (*.html);;所有文件 (*)'
        )
        if file_path:
            # 将文件路径转换为 QUrl 格式
            url = QUrl.fromLocalFile(file_path)
            self.webView.load(url)  # 传递 QUrl 对象

if __name__ == '__main__':
    app = QApplication(sys.argv)
    viewer = HtmlViewer()
    viewer.show()
    sys.exit(app.exec_())
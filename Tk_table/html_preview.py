from PyQt5.QtWidgets import QFileDialog
from PyQt5.QtWebEngineWidgets import QWebEngineView
from PyQt5.QtCore import QUrl


class HTMLPreview:
    def __init__(self, parent):
        self.parent = parent
        self.web_view = QWebEngineView()

    def open_html(self):
        path, _ = QFileDialog.getOpenFileName(
            self.parent, '选择HTML文件', '', 'HTML文件 (*.html);;所有文件 (*)'
        )
        if path:
            self.web_view.load(QUrl.fromLocalFile(path))

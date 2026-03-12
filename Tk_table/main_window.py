from PyQt5.QtWidgets import QMainWindow
from Tk_table.excel_operations import ExcelOperations
from Tk_table.html_preview import HTMLPreview
from Tk_table.ui_setup import UISetup


class EnhancedDataEditor(QMainWindow):
    def __init__(self, top_data=None, left_items=None):
        super().__init__()
        self.setWindowTitle("增强型数据编辑器(Qt版)")
        self.setGeometry(100, 100, 1200, 1000)

        self.excel_ops = ExcelOperations(top_data, left_items)
        self.html_preview = HTMLPreview(self)
        self.ui_setup = UISetup(self, self.excel_ops, self.html_preview)

        self.ui_setup.setup_ui()

    def refresh_table(self):
        self.ui_setup.refresh_table()

    def save_changes(self):
        self.excel_ops.save_changes()

    def export_data(self):
        self.excel_ops.export_data()

    def clear_table(self):
        self.ui_setup.clear_table()

    def open_html(self):
        self.html_preview.open_html()

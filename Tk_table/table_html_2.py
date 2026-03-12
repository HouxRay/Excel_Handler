import sys
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                             QScrollArea, QRadioButton, QTableWidget, QTableWidgetItem,
                             QHeaderView, QPushButton, QButtonGroup, QSplitter, QFileDialog, QLabel)
from PyQt5.QtCore import Qt, QUrl
from PyQt5.QtWebEngineWidgets import QWebEngineView
from src.Excel_Info import GetWriteInfo
from src.Excel_Writer import ExcelWriter
from typing import Dict
import time


class EnhancedDataEditor(QMainWindow):
    def __init__(self, top_data: list = [], left_items: list = [], file_dict: Dict = {}):
        super().__init__()
        self.setWindowTitle("增强型数据编辑器(Qt版)")
        self.data_dir = ""
        self.excel_path = ""
        self.setGeometry(100, 100, 1200, 1000)
        
        # 初始化数据
        self.initialize_data(top_data, left_items, file_dict)
        
        # 初始化Excel组件
        self.init_excel_components()
        
        # 构建界面
        self.init_ui()    

    def initialize_data(self, top_data, left_items, file_dict):
        """初始化数据存储结构"""
        if self.data_dir == '' or self.excel_path == '':
            self.left_items = left_items 
            self.top_data = top_data
        else:
            self.info = GetWriteInfo(self.data_dir, self.excel_path)
            self.top_data = self.info.get_tabel_info()
            self.left_items = self.info.get_file_and_excel_info()[0]

        self.fixed_values = {row[0]: row[1] for row in self.top_data}
        self.data_storage = {
            item: {row[0]: list(row[2:]) for row in self.top_data}
            for item in self.left_items
        }
        self.file_dict = file_dict
    
    def init_ui(self):
        """构建主界面"""
        main_splitter = QSplitter(Qt.Vertical)
        
        # 上半部分：数据编辑区
        data_widget = QWidget()
        self.setup_data_ui(data_widget)
        main_splitter.addWidget(data_widget)
        
        # 下半部分：HTML预览区
        html_widget = QWidget()
        self.setup_html_ui(html_widget)
        main_splitter.addWidget(html_widget)
        
        # 设置分割比例
        main_splitter.setSizes([600, 400])
        
        self.setCentralWidget(main_splitter)
        self.create_toolbar()

    def create_toolbar(self):
        """创建顶部工具栏"""
        toolbar = self.addToolBar("文件工具")
        # 数据目录选择按钮
        self.data_dir_btn = QPushButton("选择数据目录")
        self.data_dir_btn.clicked.connect(self.choose_data_dir)
        toolbar.addWidget(self.data_dir_btn)
        # Excel文件选择按钮
        self.excel_btn = QPushButton("选择Excel文件")
        self.excel_btn.clicked.connect(self.choose_excel_file)
        toolbar.addWidget(self.excel_btn)
        # 状态显示标签
        self.status_label = QLabel("未选择文件")
        toolbar.addWidget(self.status_label)
    
    def choose_data_dir(self):
        """选择数据目录"""
        directory = QFileDialog.getExistingDirectory(
            self, "选择数据目录", "", QFileDialog.ShowDirsOnly
        )
        if directory:
            self.data_dir = directory
            self.update_status()

    def confirm_import(self):
        """确认导入选中的路径"""
        # 检查是否已经选择了数据目录和Excel文件
        if not self.data_dir or not self.excel_path:
            self.status_label.setText("请先选择数据目录和Excel文件！")
            return

        # 假设这里进行一些处理，比如读取数据
        print(f"数据目录: {self.data_dir}")
        print(f"Excel文件: {self.excel_path}")
        
        # 初始化Excel相关组件
        self.init_excel_components()

        # 更新状态显示
        self.update_status()

        # 设置默认选中的按钮
        if self.left_items:
            self.radio_group.button(0).setChecked(True)

        self.refresh_table()

    def update_status(self):
        """更新状态栏显示"""
        status = []
        if hasattr(self, 'data_dir'):
            status.append(f"数据目录: {self.data_dir}")
        if hasattr(self, 'excel_path'):
            status.append(f"Excel文件: {self.excel_path}")
        self.status_label.setText(" | ".join(status) if status else "未选择文件")

    def setup_data_ui(self, parent):
        """构建数据操作界面"""
        layout = QHBoxLayout(parent)
        
        # 左侧项目列表
        left_scroll = QScrollArea()
        left_scroll.setFixedWidth(150)
        left_scroll.setWidgetResizable(True)
        
        self.radio_group = QButtonGroup()
        radio_container = QWidget()
        radio_layout = QVBoxLayout(radio_container)
        radio_layout.setAlignment(Qt.AlignTop)
        
        for idx, item in enumerate(self.left_items):
            radio = QRadioButton(item)
            self.radio_group.addButton(radio, idx)
            radio_layout.addWidget(radio)
        
        left_scroll.setWidget(radio_container)
        layout.addWidget(left_scroll)
        
        # 右侧数据操作区
        right_layout = QVBoxLayout()
        
        # 表格设置
        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels(['编号', '队伍', '比分1', '比分2', '比分3', '比分4'])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        right_layout.addWidget(self.table)
        
        # 功能按钮区
        btn_layout = QHBoxLayout()
        self.create_buttons(btn_layout)
        right_layout.addLayout(btn_layout)
        
        layout.addLayout(right_layout)

        # 不要在这里调用 self.refresh_table()
        # self.refresh_table()

    def setup_html_ui(self, parent):
        """构建HTML预览界面"""
        layout = QVBoxLayout(parent)
        
        # HTML控制按钮
        html_btn_layout = QHBoxLayout()
        open_btn = QPushButton('打开HTML文件')
        open_btn.clicked.connect(self.open_html)
        refresh_btn = QPushButton('刷新预览')
        refresh_btn.clicked.connect(lambda: self.web_view.reload())
        html_btn_layout.addWidget(open_btn)
        html_btn_layout.addWidget(refresh_btn)
        html_btn_layout.addStretch()
        
        layout.addLayout(html_btn_layout)
        
        # 网页视图
        self.web_view = QWebEngineView()
        layout.addWidget(self.web_view)

    def create_buttons(self, layout):
        """创建数据操作按钮"""
        buttons = [
            ('刷新数据', self.refresh_table),
            ('保存修改', self.save_changes),
            ('确认导入', self.confirm_import),
            ('导出Excel', self.export_data),
            # ('清空表格', self.clear_table)
        ]
        
        for text, handler in buttons:
            btn = QPushButton(text)
            btn.clicked.connect(handler)
            layout.addWidget(btn)
        layout.addStretch()

    def refresh_table(self):
        """刷新表格内容"""        
        if self.radio_group.checkedButton() is None:
            return
        selected = self.radio_group.checkedButton().text()
        data = self.data_storage[selected]
        self.table.setRowCount(len(data))
        for row, (code, values) in enumerate(data.items()):
            self.table.setItem(row, 0, QTableWidgetItem(code))
            self.table.setItem(row, 1, QTableWidgetItem(self.fixed_values[code]))
            for col, value in enumerate(values, start=2):
                self.table.setItem(row, col, QTableWidgetItem(value))

    def save_changes(self):
        """保存表格修改"""
        if self.radio_group.checkedButton() is None:
            return
        selected = self.radio_group.checkedButton().text()
        for row in range(self.table.rowCount()):
            code = self.table.item(row, 0).text()
            new_values = [self.table.item(row, col).text() for col in range(2, 6)]
            self.data_storage[selected][code] = new_values

    """--------------------------Excel相关功能-"""
    def choose_excel_file(self):
        """选择Excel文件"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "选择Excel文件", "", "Excel文件 (*.xlsx);;所有文件 (*)"
        )
        if file_path:
            self.excel_path = file_path
            self.update_status()
            self.init_excel_components()

    def init_excel_components(self):
        """初始化Excel相关组件"""
        if not hasattr(self, 'data_dir') or not hasattr(self, 'excel_path'):
            return

        try:
            self.get_info = GetWriteInfo(self.data_dir, self.excel_path)
            self.writer = ExcelWriter(self.excel_path)
            self.file_name, self.excel_name = self.get_info.get_file_and_excel_info()
            self.mapping = self.get_info.get_mapping()
            self.header_bases = self.get_info.get_header_bases()
            self.top_data = self.get_info.get_tabel_info()
            self.left_items = self.get_info.get_file_and_excel_info()[0]

            # 重新初始化数据存储结构
            self.fixed_values = {row[0]: row[1] for row in self.top_data}
            self.data_storage = {
                item: {row[0]: list(row[2:]) for row in self.top_data}
                for item in self.left_items
            }
        except Exception as e:
            print(f"初始化Excel组件失败: {str(e)}")

    def export_data(self):
        """导出数据到Excel"""
        if not hasattr(self, 'get_info') or not hasattr(self, 'writer'):
            self.status_label.setText("请先选择数据目录和Excel文件！")
            return
        self.save_changes()
        selected = self.radio_group.checkedButton().text()
        
        export_data = {
                'category': selected,
                'data': [{
                    code: {'fixed': self.fixed_values[code], 'fields': values}
                } for code, values in self.data_storage[selected].items()]
            }
        
        # Excel写入操作
        print("开始写入Excel...")
        for item in export_data['data']:
            code = list(item.keys())[0]
            values = item[code]['fields']
            try:
                line, col = self.get_info.get_location(export_data['category'], code, self.excel_name)
                self.writer.write_info(line, col, value=values)
                time.sleep(0.1)
            except Exception as e:
                print(f"写入错误：{str(e)}")
                continue
        print("数据导出完成！")
        return export_data


    """--------------------------html相关功能-----------------------------------"""

    def get_html_path(self):
        """获取HTML文件路径"""
        self.file_path, _ = QFileDialog.getOpenFileName(
            self, '选择HTML文件', '', 'HTML文件 (*.html);;所有文件 (*)'
        )
        if self.file_path:
            return 1
        else:
            return 0

    def open_html(self):
        """打开HTML文件"""   
        if self.get_html_path():
            self.web_view.load(QUrl.fromLocalFile(self.file_path))

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = EnhancedDataEditor()
    window.show()
    sys.exit(app.exec_())




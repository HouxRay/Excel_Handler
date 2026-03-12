import sys
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                             QScrollArea, QRadioButton, QTableWidget, QTableWidgetItem,
                             QHeaderView, QPushButton, QButtonGroup, QDialog, QLabel)
from PyQt5.QtWebEngineWidgets import QWebEngineView  # 新增Web引擎组件
from PyQt5.QtCore import Qt, QUrl
from src.Excel_Info import GetWriteInfo
from src.Excel_Writer import ExcelWriter
import time
from pathlib import Path


class NewWindow(QDialog):
    def __init__(self, selected_item, html_base_path, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"HTML查看器 - {selected_item}")
        self.setGeometry(0, 0, 1100, 800)
        
        layout = QVBoxLayout()
        
        # 创建Web视图组件
        self.web_view = QWebEngineView()
        
        # 构建完整文件路径
        self.html_path = Path(html_base_path)
        
        if self.html_path.exists():
            self.web_view.load(QUrl.fromLocalFile(str(self.html_path)))
        else:
            self.web_view.setHtml(f"<h1>文件未找到</h1><p>{self.html_path}</p>")
        
        layout.addWidget(self.web_view)
        self.setLayout(layout)



class EnhancedDataEditor(QMainWindow):
    def __init__(self, top_data:list = None, 
                 left_items:list = None, 
                 excel_name:list = None, 
                 excel_path:str = None, 
                 file_path:str = None):
        """
        top_data：队伍数据
        left_items：html文件名称
        excel_name：excel文件名称
        excel_path：excel文件路径
        """
        super().__init__()
        self.setWindowTitle("增强型数据编辑器(Qt版)")
        self.setGeometry(300, 300, 800, 600)
        
        # 测试数据
        if left_items is None:
            self.left_items = ['八神竞猜', '财神密码', '红龙'] + [f"项目{i}" for i in range(4, 15)]
            self.flag = False
        else:
            self.left_items = left_items
            self.flag = True
        if top_data is  None:
            self.top_data = [
                ['001', 'xxx', 'a1', 'b1', 'c1','d1'],
                ['002', 'yyy', 'a2', 'b2', 'c2','d2'],
                ['003', 'zzz', 'a3', 'b3', 'c3',"d2"]
            ]
            self.flag = False
        else:
            self.top_data = top_data
            self.flag = True
        self.fixed_values = {row[0]: row[1] for row in self.top_data}
        self.data_storage = {item: {row[0]: list(row[2:]) for row in self.top_data} 
                           for item in self.left_items}
        
        self.get_info = GetWriteInfo(file_path, excel_path)
        self.writer = ExcelWriter(excel_path)
        self.excel_name = excel_name
        self.mapping = self.get_info.get_mapping()
        self.header_bases = self.get_info.get_header_bases()
        self.url = self.get_info.get_file_dict()
        self.current_window = None
        
        self.init_ui()
        
    def init_ui(self):
        main_widget = QWidget()
        main_layout = QHBoxLayout(main_widget)
        
        # 左侧滚动区域
        left_scroll = QScrollArea()
        left_scroll.setFixedWidth(150)
        left_scroll.setWidgetResizable(True)
        
        self.radio_group = QButtonGroup()
        radio_container = QWidget()
        radio_layout = QVBoxLayout(radio_container)
        radio_layout.setAlignment(Qt.AlignTop)
        
        # 创建单选按钮（自动分页）
        for idx, item in enumerate(self.left_items):
            radio = QRadioButton(item)
            if item not in self.mapping:
                radio.setStyleSheet("color: red;")
            else:
                radio.setStyleSheet("color: green;")
            self.radio_group.addButton(radio, idx)
            radio_layout.addWidget(radio)
            if idx == 0:
                radio.setChecked(True)
        
        left_scroll.setWidget(radio_container)
        main_layout.addWidget(left_scroll)
        
        # 右侧表格区域
        right_layout = QVBoxLayout()
        
        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels(['编号', '队伍', '比分1', '比分2', '比分3','比分4'])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        right_layout.addWidget(self.table)
        
        # 按钮区域
        btn_layout = QHBoxLayout()
        refresh_btn = QPushButton("刷新")
        save_btn = QPushButton("保存")
        export_btn = QPushButton("导出")
        open_btn = QPushButton("打开")
        
        refresh_btn.clicked.connect(self.refresh_table)
        save_btn.clicked.connect(self.save_changes)
        export_btn.clicked.connect(self.export_data)
        open_btn.clicked.connect(self.on_open_clicked)
        
        btn_layout.addWidget(refresh_btn)
        btn_layout.addWidget(save_btn)
        btn_layout.addWidget(export_btn)
        right_layout.addLayout(btn_layout)
        btn_layout.addWidget(open_btn)
        
        main_layout.addLayout(right_layout)
        self.setCentralWidget(main_widget)
        
        # 初始化显示
        self.radio_group.buttonClicked.connect(self.refresh_table)
        self.refresh_table()
        
    def refresh_table(self):
        selected_item = self.radio_group.checkedButton().text()
        current_data = self.data_storage[selected_item]
        
        self.table.setRowCount(len(current_data))
        for row_idx, (code, values) in enumerate(current_data.items()):
            # 编号
            self.table.setItem(row_idx, 0, QTableWidgetItem(code))
            # 固定值
            self.table.setItem(row_idx, 1, QTableWidgetItem(self.fixed_values[code]))
            # 可编辑字段
            for col_idx, value in enumerate(values, start=2):
                self.table.setItem(row_idx, col_idx, QTableWidgetItem(value))
                
    def save_changes(self):
        selected_item = self.radio_group.checkedButton().text()
        for row in range(self.table.rowCount()):
            code = self.table.item(row, 0).text()
            new_values = [self.table.item(row, col).text() for col in range(2, 6)]
            self.data_storage[selected_item][code] = new_values

    def on_open_clicked(self):
        if self.current_window:
            self.current_window.close()
        selected_item = self.radio_group.checkedButton().text()
        url = self.url[selected_item]
        self.current_window = NewWindow(selected_item, 
                                      html_base_path=url,
                                      parent=self)
        
        self.current_window.destroyed.connect(lambda: setattr(self, 'current_window', None))
        self.current_window.show()

            
    def export_data(self):
        self.save_changes()
        selected_item = self.radio_group.checkedButton().text()
        export_list = {
            'category': selected_item,
            'data': [{
                code: {
                    'fixed': self.fixed_values[code],
                    'fields': values
                }
            } for code, values in self.data_storage[selected_item].items()]
        }
        print("导出数据:", export_list)

        # 写入Excel
        header = export_list['category']
        info_dicts = export_list['data']
        print('*************写入Excel*************')
        print(header)
        print(type(info_dicts))

        for info_dict in info_dicts:  # info_dict: {'001': {'fixed': 'xxx', 'fields': ['a1', 'b1', 'c1', 'd1']}}           
            key = list(info_dict.keys())[0]
            print(key)
            value = info_dict[key]
            print(key, value)  #  key: 001 value: {'fixed': 'xxx', 'fields': ['a1', 'b1', 'c1', 'd1']}
            pre_scores = value['fields']
            print(pre_scores)  # pre_scores: ['a1', 'b2', 'c1', 'd1']
            try:     
                line_location, column_location = self.get_info.get_location(header, key, self.excel_name)           
                self.writer.write_info(line_location, column_location,value = pre_scores)
                time.sleep(0.1)
            except Exception as e:
                print(e)
                continue

        return export_list

if __name__ == "__main__":
    from src.Excel_Info import GetWriteInfo
    Eif = GetWriteInfo("src\\2025-03-03-竞彩", "src\sample.xlsx")
    top_data = Eif.get_tabel_info()
    files_names, excel_name = Eif.get_file_and_excel_info()
    app = QApplication(sys.argv)
    window = EnhancedDataEditor(top_data, files_names, excel_name, "src\sample.xlsx", "src\\2025-03-03-竞彩")
    window.show()
    sys.exit(app.exec_())
import sys
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                             QScrollArea, QRadioButton, QTableWidget, QTableWidgetItem,
                             QHeaderView, QPushButton, QButtonGroup, QDialog, QLabel, QMessageBox, QTextEdit, )
from PyQt5.QtWebEngineWidgets import QWebEngineView  # 新增Web引擎组件
from PyQt5.QtCore import Qt, QUrl
from PyQt5.QtGui import QTextCursor, QIcon
from src.Excel_Info import GetWriteInfo
from src.Excel_Writer import ExcelWriter
import time
from pathlib import Path
from collections import Counter, defaultdict
import logging
import os
from datetime import datetime

# 自定义日志处理器，用于将日志输出到GUI窗口
class QTextEditLogger(logging.Handler):
    def __init__(self, text_widget):
        super().__init__()
        self.text_widget = text_widget
        self.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))

    def emit(self, record):
        msg = self.format(record)
        self.text_widget.append(msg)

# 配置日志
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
    
    # 添加处理器
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    # 如果提供了文本窗口，添加GUI处理器
    if text_widget:
        gui_handler = QTextEditLogger(text_widget)
        gui_handler.setFormatter(formatter)
        logger.addHandler(gui_handler)
    
    return logger

# 创建logger实例
logger = setup_logger()

class NewWindow(QDialog):
    def __init__(self, selected_item, html_base_path, parent=None):
        super().__init__(parent)
        try:
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
            
        except Exception as e:
            QMessageBox.warning(self, "错误", "当前HTML文件路径错误，请检查！")



class EnhancedDataEditor(QMainWindow):
    def __init__(self, top_data:list = None, 
                 left_items:list = None, 
                 excel_name:list = None, 
                 excel_path:str = None, 
                 file_path:str = None,
                 json_path:str = None):
        """
        top_data：队伍数据
        left_items：html文件名称
        excel_name：excel文件名称
        excel_path：excel文件路径
        file_path：html文件路径
        json_path：json文件路径（用于二次整理时引入新数据）
        """
        super().__init__()
        self.setWindowTitle("Doro统治世界")
        self.setGeometry(300, 300, 800, 600)
        
        # 设置窗口图标
        try:
            icon_path = "assets/pic.ico"  # 图标文件路径
            if os.path.exists(icon_path):
                self.setWindowIcon(QIcon(icon_path))
            else:
                logger.warning(f"图标文件未找到: {icon_path}")
        except Exception as e:
            logger.exception("设置窗口图标时发生错误")
        
        if top_data is None or left_items is None or excel_name is None:
            self.get_info = GetWriteInfo(file_path, excel_path)
            top_data = self.get_info.get_tabel_info()
            left_items, excel_name = self.get_info.get_file_and_excel_info()
        # 初始化数据
        if left_items is None:
            self.left_items = ['八神竞猜', '财神密码', '红龙'] + [f"项目{i}" for i in range(4, 15)]
            self.flag = False
        else:
            self.left_items = left_items
            self.flag = True

        if top_data is None:
            self.top_data = [
                ['001', 'xxx', 'a1', 'b1', 'c1','d1'],
                ['002', 'yyy', 'a2', 'b2', 'c2','d2'],
                ['003', 'zzz', 'a3', 'b3', 'c3',"d2"]
            ]
            self.flag = False
        else:
            self.top_data = top_data
            self.flag = True

        # 初始化固定值映射
        self.fixed_values = {row[0]: row[1] for row in self.top_data}
        
        # 初始化Excel相关对象
        if self.flag:
            self.writer = ExcelWriter(excel_path)
            self.excel_first_columns = excel_name  # 实际上是 excel_first_columns 字典
            self.mapping = self.get_info.get_mapping()
            self.header_bases = self.get_info.get_header_bases()
            self.url = self.get_info.get_file_dict()
        
        # 初始化数据存储，并允许通过update引入新数据
        self.data_storage = {item: {row[0]: list(row[2:]) for row in self.top_data} 
                           for item in self.left_items}
        
        # 从JSON文件加载数据（用于二次整理时引入新数据）
        if json_path:
            try:
                json_data = self.get_info.get_json(json_path)
                if json_data:
                    self.data_storage.update(json_data)
                    logger.info("成功从JSON文件加载额外数据")
            except Exception as e:
                logger.exception("加载JSON数据时发生错误")
                QMessageBox.warning(self, "警告", f"加载JSON数据失败：{str(e)}")
        
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
        open_btn = QPushButton("打开")
        refresh_btn = QPushButton("刷新")
        save_btn = QPushButton("保存")
        export_btn = QPushButton("导出")
        sort_btn = QPushButton("排序")
        json_btn = QPushButton("写入JSON")
        reload_btn = QPushButton("重新选择路径")
        
        
        refresh_btn.clicked.connect(self.refresh_table)
        save_btn.clicked.connect(self.save_changes)
        export_btn.clicked.connect(self.export_data)
        open_btn.clicked.connect(self.on_open_clicked)
        sort_btn.clicked.connect(self.sort)
        json_btn.clicked.connect(self.export_json)
        reload_btn.clicked.connect(self.reload_paths)
        
        btn_layout.addWidget(open_btn)
        btn_layout.addWidget(refresh_btn)
        btn_layout.addWidget(save_btn)
        btn_layout.addWidget(export_btn)
        btn_layout.addWidget(reload_btn)
        right_layout.addLayout(btn_layout)       
        btn_layout.addWidget(sort_btn)
        btn_layout.addWidget(json_btn)
        
        main_layout.addLayout(right_layout)
        self.setCentralWidget(main_widget)
        
        # 初始化显示
        self.radio_group.buttonClicked.connect(self.refresh_table)
        self.refresh_table()
        
        ######### 2025-4-16 新增  ########     
         
        # 在右侧布局中添加日志输出区域
        self.log_output = QTextEdit()
        self.log_output.setReadOnly(True)  # 只读模式
        self.log_output.setMaximumHeight(100)  # 限制高度
        self.log_output.setStyleSheet("""
            QTextEdit {
                background-color: #f0f0f0;
                border: 1px solid #ccc;
                padding: 5px;
                font-family: Consolas, monospace;
            }
        """)
        right_layout.addWidget(self.log_output)  # 添加到右侧布局

        # 设置日志记录器
        self.logger = setup_logger(self.log_output)
        
        # 重定向 print 到日志框
        sys.stdout = self  # 自定义 stdout
        
    def write(self, text):
        """捕获 print 输出并重定向到日志"""
        if text.strip():  # 只记录非空文本
            self.logger.info(text.strip())
        
    def refresh_table(self):
        """
        刷新表格
        """
        try:
            selected_item = self.radio_group.checkedButton().text()
            current_data = self.data_storage[selected_item]

            self.table.setRowCount(len(current_data))
            for row_idx, (code, values) in enumerate(current_data.items()):
                # 编号
                item = QTableWidgetItem(code)
                item.setFlags(item.flags() & ~Qt.ItemIsEditable)  # 设置为不可编辑
                self.table.setItem(row_idx, 0, item)
                
                # 固定值
                item = QTableWidgetItem(self.fixed_values[code])
                item.setFlags(item.flags() & ~Qt.ItemIsEditable)  # 设置为不可编辑
                self.table.setItem(row_idx, 1, item)
                
                # 可编辑字段
                for col_idx, value in enumerate(values, start=2):
                    self.table.setItem(row_idx, col_idx, QTableWidgetItem(value))
        except Exception as e:
            logger.exception("刷新表格时发生错误")
            QMessageBox.warning(self, "警告", f"{e}")
                
    def save_changes(self):
        """
        保存修改
        """
        try:
            selected_item = self.radio_group.checkedButton().text()
            for row in range(self.table.rowCount()):
                code = self.table.item(row, 0).text()
                new_values = [self.table.item(row, col).text() for col in range(2, 6)]
                self.data_storage[selected_item][code] = new_values
        except Exception as e:
            logger.exception("保存数据时发生错误")
            QMessageBox.warning(self, "警告", f"保存失败：{str(e)}")

    def on_open_clicked(self):
        """
        打开HTML文件
        """
        if self.current_window:
            self.current_window.close()
        selected_item = self.radio_group.checkedButton().text()
        try:
            url = self.url[selected_item]       
            self.current_window = NewWindow(selected_item, 
                                          html_base_path=url,
                                          parent=self)

            self.current_window.destroyed.connect(lambda: setattr(self, 'current_window', None))
            self.current_window.show()
        except:
            QMessageBox.warning(self, "警告", "文件路径不存在，或者文件名称错误")

            
    def export_data(self):
        """
        导出数据
        """       
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

        # 写入Excel
        header = export_list['category']
        info_dicts = export_list['data']
        try:
            ex_header = self.mapping[header]
        except Exception as e:
            logger.exception(f"映射表错误: 未找到键 '{header}'")
            QMessageBox.warning(self, "错误", f"'{header}'未匹配成功，请检查映射表")
            return 0

        logger.info(f'开始写入 *{header}*')
        
        for info_dict in info_dicts:
            key = list(info_dict.keys())[0]
            value = info_dict[key]
            pre_scores = value['fields']
            try:     
                # 修复参数顺序：文件名用于查找行，表头数字用于计算列
                line_location, column_location = self.get_info.get_location(key, ex_header, self.excel_first_columns)
                if line_location is None or column_location is None:
                    logger.error(f"get_location 返回 None for key={key}, ex_header={ex_header}")
                    continue
                is_written = self.writer.write_info(line_location, column_location, value=pre_scores)
                if is_written == 0:
                    logger.warning(f'*{header}* 写入失败')
                    return 0
            except Exception as e:
                logger.exception(f"*{header}* 写入失败 - 键: {key}")
                return 0
        logger.info(f'*{header}* 写入完成')   

        return export_list
    
    def sort(self):
        """
        排序
        """
        try:
            stats = defaultdict(Counter)
            logger.info("开始排序")

            for name in self.data_storage:
                number_dict = self.data_storage[name]
                for number, values in number_dict.items():
                    for value in values:
                        if value.strip() and value.strip().isdigit():
                            stats[number][value] += 1

            dict_counter = {number: dict(counts.most_common()) for number, counts in stats.items()}
            
            for column, contents in dict_counter.items():
                try:
                    _, column_location = self.get_info.get_location(excel_first_num=column) 
                    self.writer.write_info(84, column_location, contents)
                except Exception as e:
                    logger.exception(f"排序写入失败 - 列: {column}")
                    
            logger.info("排序完成")
            return dict_counter
        except Exception as e:
            logger.exception("排序过程中发生错误")
            QMessageBox.critical(self, "错误", f"排序失败：{str(e)}")
            return None

    def export_json(self):
        """
        导出JSON文件
        """
        try:
            import json
            if not os.path.exists("./json"):
                os.makedirs("./json")
            json_path = f"./json/{datetime.now().strftime('%Y-%m-%d')}.json"
            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump(self.data_storage, f, ensure_ascii=False, indent=4)
            logger.info(f"JSON文件导出成功: {json_path}")
        except Exception as e:
            logger.exception("JSON导出失败")
            QMessageBox.critical(self, "错误", f"JSON导出失败：{str(e)}")
            return None

    def reload_paths(self):
        """
        重新选择路径并重新加载数据
        """
        try:
            # 关闭当前窗口
            self.close()
            
            # 重新运行路径选择器
            from window.table_qt_2 import PathSelector
            path_selector = PathSelector()
            result = path_selector.exec_()
            
            if result == QDialog.Accepted:
                folder_path, excel_path, json_path = path_selector.selected_paths
                
                # 验证路径有效性
                if not folder_path or not excel_path:
                    QMessageBox.critical(None, "错误", "必须选择有效的文件夹和Excel文件路径")
                    return
                
                # 创建新的主窗口实例
                new_window = EnhancedDataEditor(excel_path=excel_path,
                                               file_path=folder_path,
                                               json_path=json_path)
                new_window.show()
                
        except Exception as e:
            logger.exception("重新加载路径时发生错误")
            QMessageBox.critical(None, "错误", f"重新加载失败：{str(e)}")

if __name__ == "__main__":
    from src.Excel_Info import GetWriteInfo
    file_path = r"D:\Excel_Hander\excel\2025-05-19-竞彩"
    excel_path = r"D:\Excel_Hander\excel\副本5-19奥.xlsx"
    Eif = GetWriteInfo(file_path, excel_path)
    json_path = r"D:\Excel_Hander\dist\json\2025-05-19.json"
    # top_data = Eif.get_tabel_info()
    # files_names, excel_name = Eif.get_file_and_excel_info()
    app = QApplication(sys.argv)
    window = EnhancedDataEditor(excel_path=excel_path, file_path=file_path, json_path=json_path)
    window.show()
    sys.exit(app.exec_())
import sys
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                             QScrollArea, QRadioButton, QTableWidget, QTableWidgetItem,
                             QHeaderView, QPushButton, QButtonGroup, QDialog, QLabel, QMessageBox,
                             QTextEdit, QProgressDialog, QStyledItemDelegate, QComboBox)
from PyQt5.QtWebEngineWidgets import QWebEngineView  # 新增Web引擎组件
from PyQt5.QtCore import Qt, QUrl, QThread, QEvent, QSettings
from PyQt5.QtGui import QTextCursor, QIcon
from src.Excel_Info import GetWriteInfo
from src.Excel_Writer import ExcelWriter
from window.settings_dialog import SettingsDialog
import time
from pathlib import Path
from collections import Counter, defaultdict
import logging
import os
from datetime import datetime, timezone, timedelta

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
    
    # 防止重复添加处理器
    if not logger.handlers:
        # 添加处理器
        logger.addHandler(file_handler)
        logger.addHandler(console_handler)
    
    # 如果提供了文本窗口，添加GUI处理器
    if text_widget:
        # 检查是否已经添加了GUI处理器
        gui_handler_exists = any(
            isinstance(h, QTextEditLogger) and h.text_widget == text_widget 
            for h in logger.handlers
        )
        if not gui_handler_exists:
            gui_handler = QTextEditLogger(text_widget)
            gui_handler.setFormatter(formatter)
            logger.addHandler(gui_handler)
    
    # 禁用日志传播，防止重复输出
    logger.propagate = False
    
    return logger

# 创建logger实例
logger = setup_logger()

class NewWindow(QDialog):
    def __init__(self, selected_item, html_base_path, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_DeleteOnClose)  # 关闭时自动释放资源
        try:
            self.setWindowTitle(f"HTML查看器 - {selected_item}")
            self.setGeometry(0, 0, 1100, 800)

            self.html_base_path = Path(html_base_path)

            # 星期名称列表
            self.weekday_names = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]

            # 自动检测北京时区 (UTC+8) 当前星期
            beijing_tz = timezone(timedelta(hours=8))
            current_weekday = datetime.now(beijing_tz).weekday()  # Monday=0, Sunday=6
            self.default_day = self.weekday_names[current_weekday]
            self.current_day = self.default_day

            layout = QVBoxLayout()
            layout.setContentsMargins(0, 0, 0, 0)
            layout.setSpacing(0)

            # 工具栏：星期选择（紧凑）
            toolbar_widget = QWidget()
            toolbar_widget.setMaximumHeight(28)
            toolbar_widget.setStyleSheet("background-color: #f5f5f5; border-bottom: 1px solid #ddd;")
            toolbar_layout = QHBoxLayout(toolbar_widget)
            toolbar_layout.setContentsMargins(4, 1, 4, 1)
            toolbar_layout.setSpacing(3)
            toolbar_layout.addWidget(QLabel("高亮:"))
            self.day_combo = QComboBox()
            self.day_combo.setMaximumWidth(80)
            self.day_combo.setStyleSheet("font-size: 11px;")
            self.day_combo.addItems(self.weekday_names)
            idx = self.weekday_names.index(self.default_day)
            self.day_combo.setCurrentIndex(idx)
            self.day_combo.currentTextChanged.connect(self._on_day_changed)
            toolbar_layout.addWidget(self.day_combo)
            toolbar_layout.addStretch()
            layout.addWidget(toolbar_widget)

            # Web视图
            self.web_view = QWebEngineView()

            if self.html_base_path.exists():
                self.web_view.load(QUrl.fromLocalFile(str(self.html_base_path)))
            else:
                self.web_view.setHtml(f"<h1>文件未找到</h1><p>{self.html_base_path}</p>")

            # 页面加载完成后注入高亮JS
            self.web_view.loadFinished.connect(self._inject_highlight)

            layout.addWidget(self.web_view)
            self.setLayout(layout)

        except Exception as e:
            QMessageBox.warning(self, "错误", "当前HTML文件路径错误，请检查！")

    def closeEvent(self, event):
        """关闭窗口时释放 Web 引擎资源，防止 QtWebEngineProcess 进程残留"""
        if hasattr(self, 'web_view'):
            self.web_view.setPage(None)
            self.web_view.stop()
            self.web_view.deleteLater()
            self.web_view = None
        super().closeEvent(event)

    def _on_day_changed(self, day_text):
        """用户切换星期时重新注入高亮"""
        self.current_day = day_text
        self._inject_highlight()

    def _inject_highlight(self, ok=True):
        """通过 JavaScript 高亮当前星期文字"""
        if not ok:
            return
        js_code = f"""
        (function() {{
            var oldSpans = document.querySelectorAll('.weekday-highlight');
            for (var i = 0; i < oldSpans.length; i++) {{
                var parent = oldSpans[i].parentNode;
                var txt = document.createTextNode(oldSpans[i].textContent);
                parent.replaceChild(txt, oldSpans[i]);
                parent.normalize();
            }}
            var target = "{self.current_day}";
            if (!target) return;
            var walker = document.createTreeWalker(
                document.body, NodeFilter.SHOW_TEXT, null, false
            );
            var nodes = [];
            while (walker.nextNode()) nodes.push(walker.currentNode);
            for (var i = 0; i < nodes.length; i++) {{
                var node = nodes[i];
                if (node.textContent.indexOf(target) !== -1) {{
                    var span = document.createElement('span');
                    span.className = 'weekday-highlight';
                    span.style.backgroundColor = 'yellow';
                    span.style.color = 'red';
                    span.style.fontWeight = 'bold';
                    span.textContent = node.textContent;
                    node.parentNode.replaceChild(span, node);
                }}
            }}
        }})();
        """
        self.web_view.page().runJavaScript(js_code)






class SpaceToZeroDelegate(QStyledItemDelegate):
    """编辑代理：编辑时按空格/反引号自动替换为0，同时作为数据级别的兜底"""
    def createEditor(self, parent, option, index):
        editor = super().createEditor(parent, option, index)
        editor.installEventFilter(self)
        return editor

    def eventFilter(self, obj, event):
        if event.type() == QEvent.KeyPress:
            key = event.key()
            if key == Qt.Key_Space or key == Qt.Key_QuoteLeft:
                obj.insert("0")
                return True
        return super().eventFilter(obj, event)

    def setModelData(self, editor, model, index):
        """提交编辑前将空格/反引号替换为0"""
        text = editor.text()
        text = text.replace(" ", "0").replace("`", "0")
        model.setData(index, text)


class EnhancedDataEditor(QMainWindow):
    def __init__(self, top_data:list = None, 
                 left_items:list = None, 
                 excel_name:list = None, 
                 excel_path:str = None, 
                 file_path:str = None,
                 json_path:str = None,
                 sheet_name:str = None):
        """
        top_data：队伍数据
        left_items：html文件名称
        excel_name：excel文件名称
        excel_path：excel文件路径
        file_path：html文件路径
        json_path：json文件路径（用于二次整理时引入新数据）
        sheet_name：Excel sheet名称
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
            self.get_info = GetWriteInfo(file_path, excel_path, sheet_name)
            top_data = self.get_info.get_tabel_info()
            left_items, excel_name = self.get_info.get_file_and_excel_info()
        self.file_path = file_path  # 存储文件夹路径，供图片模式查找txt文件
        self.sheet_name = sheet_name  # 存储sheet名，供后台线程使用
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
            self.writer = ExcelWriter(excel_path, sheet_name)
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
                if json_data and isinstance(json_data, dict):
                    # 检测格式：新格式顶层为code，旧格式顶层为category
                    first_key = next(iter(json_data))
                    first_val = json_data[first_key]
                    if isinstance(first_val, dict) and any(
                        isinstance(v, list) for v in first_val.values()
                    ):
                        # 新格式：{code: {category: [scores]}}
                        imported_count = 0
                        for code, categories in json_data.items():
                            for category, scores in categories.items():
                                if category in self.data_storage and code in self.data_storage[category]:
                                    self.data_storage[category][code] = scores
                                    imported_count += 1
                        logger.info(f"成功从JSON文件加载数据: {imported_count} 项")
                    else:
                        # 旧格式：{category: {code: [scores]}}
                        self.data_storage.update(json_data)
                        logger.info("成功从JSON文件加载额外数据（旧格式）")
            except Exception as e:
                logger.exception("加载JSON数据时发生错误")
                QMessageBox.warning(self, "警告", f"加载JSON数据失败：{str(e)}")
        
        self.current_window = None
        self.is_dirty = False          # 未保存修改标记
        self.worker_thread = None      # 后台工作线程引用
        self.data_mode = 'html'        # 数据来源：'html' 或 'pic'
        self._load_pic_config()        # 加载图片模式配置
        self.init_ui()
        
    def init_ui(self):
        main_widget = QWidget()
        main_layout = QHBoxLayout(main_widget)
        
        # 左侧面板容器
        left_panel = QVBoxLayout()

        # HTML / 图片 模式切换按钮
        mode_layout = QHBoxLayout()
        active_style = """
            QPushButton { background-color: #2196F3; color: white; font-weight: bold;
            padding: 4px 10px; border-radius: 4px; border: 1px solid #1976D2; }
        """
        inactive_style = """
            QPushButton { background-color: #ccc; color: #666; font-weight: bold;
            padding: 4px 10px; border-radius: 4px; border: 1px solid #bbb; }
        """
        self.html_mode_btn = QPushButton("HTML")
        self.pic_mode_btn = QPushButton("图片")
        self.html_mode_btn.setStyleSheet(active_style)
        self.pic_mode_btn.setStyleSheet(inactive_style)
        self.html_mode_btn.clicked.connect(lambda: self._switch_data_mode('html'))
        self.pic_mode_btn.clicked.connect(lambda: self._switch_data_mode('pic'))
        mode_layout.addWidget(self.html_mode_btn)
        mode_layout.addWidget(self.pic_mode_btn)
        left_panel.addLayout(mode_layout)

        # 左侧滚动区域
        self.left_scroll = QScrollArea()
        self.left_scroll.setFixedWidth(150)
        self.left_scroll.setWidgetResizable(True)

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

        self.left_scroll.setWidget(radio_container)
        left_panel.addWidget(self.left_scroll)
        main_layout.addLayout(left_panel)
        
        # 右侧表格区域
        right_layout = QVBoxLayout()
        
        self.table = QTableWidget()
        self.table.setItemDelegate(SpaceToZeroDelegate(self.table))
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels(['编号', '队伍', '比分1', '比分2', '比分3','比分4'])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        right_layout.addWidget(self.table)
    

        # 按钮区域 - 三色分行布局
        # ── 绿色按钮行 ──
        green_btn_layout = QHBoxLayout()
        reload_btn = QPushButton("🔄 重新选择路径")
        reload_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                font-weight: bold;
                padding: 6px 12px;
                border-radius: 4px;
                border: 1px solid #45a049;
            }
            QPushButton:hover { background-color: #45a049; border: 1px solid #3d8b40; }
            QPushButton:pressed { background-color: #3d8b40; }
        """)
        reload_btn.clicked.connect(self.reload_paths)

        clear_btn = QPushButton("🗑️ 清空")
        clear_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                font-weight: bold;
                padding: 6px 12px;
                border-radius: 4px;
                border: 1px solid #45a049;
            }
            QPushButton:hover { background-color: #45a049; border: 1px solid #3d8b40; }
            QPushButton:pressed { background-color: #3d8b40; }
        """)
        clear_btn.clicked.connect(self._clear_current_page)

        green_btn_layout.addWidget(reload_btn)
        green_btn_layout.addWidget(clear_btn)
        green_btn_layout.addStretch()

        # ── 橙色按钮行 ──
        orange_btn_layout = QHBoxLayout()
        orange_style = """
            QPushButton {
                background-color: #FF9800;
                color: white;
                font-weight: bold;
                padding: 6px 12px;
                border-radius: 4px;
                border: 1px solid #F57C00;
                min-width: 80px;
            }
            QPushButton:hover { background-color: #F57C00; border: 1px solid #E65100; }
            QPushButton:pressed { background-color: #E65100; }
        """

        self.fill_btn = QPushButton("📥 填入数据")
        self.fill_btn.setStyleSheet(orange_style)
        self.fill_btn.clicked.connect(self._on_fill_from_txt)
        self.fill_btn.setVisible(False)

        refresh_btn = QPushButton("🔄 刷新")
        refresh_btn.setStyleSheet(orange_style)
        refresh_btn.clicked.connect(self.refresh_table)

        settings_btn = QPushButton("⚙️ 设置")
        settings_btn.setStyleSheet(orange_style)
        settings_btn.clicked.connect(self._open_settings)

        orange_btn_layout.addWidget(self.fill_btn)
        orange_btn_layout.addWidget(refresh_btn)
        orange_btn_layout.addWidget(settings_btn)
        orange_btn_layout.addStretch()

        # ── 蓝色按钮行 ──
        blue_btn_layout = QHBoxLayout()
        blue_style = """
            QPushButton {
                background-color: #2196F3;
                color: white;
                font-weight: bold;
                padding: 6px 12px;
                border-radius: 4px;
                border: 1px solid #1976D2;
                min-width: 80px;
            }
            QPushButton:hover { background-color: #1976D2; border: 1px solid #1565C0; }
            QPushButton:pressed { background-color: #1565C0; }
        """

        open_btn = QPushButton("📂 打开")
        save_btn = QPushButton("💾 保存")
        export_btn = QPushButton("📤 导出")
        sort_btn = QPushButton("📊 排序")
        json_btn = QPushButton("📝 写入JSON")

        open_btn.setStyleSheet(blue_style)
        save_btn.setStyleSheet(blue_style)
        export_btn.setStyleSheet(blue_style)
        sort_btn.setStyleSheet(blue_style)
        json_btn.setStyleSheet(blue_style)

        open_btn.clicked.connect(self.on_open_clicked)
        save_btn.clicked.connect(self.save_changes)
        export_btn.clicked.connect(self.export_data)
        sort_btn.clicked.connect(self.sort)
        json_btn.clicked.connect(self.export_json)

        blue_btn_layout.addWidget(open_btn)
        blue_btn_layout.addWidget(save_btn)
        blue_btn_layout.addWidget(export_btn)
        blue_btn_layout.addWidget(sort_btn)
        blue_btn_layout.addWidget(json_btn)
        blue_btn_layout.addStretch()

        # 添加三行到右侧布局
        right_layout.addLayout(green_btn_layout)
        right_layout.addLayout(orange_btn_layout)
        right_layout.addLayout(blue_btn_layout)
        
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

        # 版本号标签（不起眼的右下角）
        version_label = QLabel("v2.1.3")
        version_label.setStyleSheet("color: #999; font-size: 10px; padding: 2px;")
        version_label.setAlignment(Qt.AlignRight | Qt.AlignBottom)
        right_layout.addWidget(version_label)

        # 设置日志记录器
        self.logger = setup_logger(self.log_output)

        # 重定向 print 到日志框
        sys.stdout = self  # 自定义 stdout
        
    def write(self, text):
        """捕获 print 输出并重定向到日志"""
        if text.strip():  # 只记录非空文本
            self.logger.info(text.strip())

    def _load_pic_config(self):
        """加载图片模式配置（与 mapping_data.txt 同格式：excel值：类别名）"""
        self.pic_categories = []
        self.pic_mapping = {}
        try:
            pic_file = "mapping/mapping_pic.txt"
            if os.path.exists(pic_file):
                with open(pic_file, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if line and "：" in line:
                            value, key = line.split("：", 1)
                            self.pic_mapping[key.strip()] = value.strip()
                            self.pic_categories.append(key.strip())
                # 将图片类别追加到 data_storage
                for pic_cat in self.pic_categories:
                    if pic_cat not in self.data_storage:
                        self.data_storage[pic_cat] = {row[0]: list(row[2:]) for row in self.top_data}
        except Exception:
            pass

    def _rebuild_radio_buttons(self):
        """根据当前 data_mode 重建左侧单选按钮列表"""
        # 清空按钮组
        for btn in self.radio_group.buttons():
            self.radio_group.removeButton(btn)
        # 清空布局
        container = self.left_scroll.widget()
        if container:
            layout = container.layout()
            while layout.count():
                child = layout.takeAt(0)
                if child.widget():
                    child.widget().deleteLater()

        # 选择对应的列表
        items = self.left_items if self.data_mode == 'html' else self.pic_categories
        mapping = self.mapping if self.data_mode == 'html' else self.pic_mapping

        for idx, item in enumerate(items):
            radio = QRadioButton(item)
            if item in mapping:
                radio.setStyleSheet("color: green;")
            else:
                radio.setStyleSheet("color: red;")
            self.radio_group.addButton(radio, idx)
            container.layout().addWidget(radio)
            if idx == 0:
                radio.setChecked(True)

    def _switch_data_mode(self, mode):
        """切换数据来源模式"""
        if self.data_mode == mode:
            return
        self.data_mode = mode
        # 更新按钮样式
        active = """
            QPushButton { background-color: #2196F3; color: white; font-weight: bold;
            padding: 4px 10px; border-radius: 4px; border: 1px solid #1976D2; }
        """
        inactive = """
            QPushButton { background-color: #ccc; color: #666; font-weight: bold;
            padding: 4px 10px; border-radius: 4px; border: 1px solid #bbb; }
        """
        self.html_mode_btn.setStyleSheet(active if mode == 'html' else inactive)
        self.pic_mode_btn.setStyleSheet(active if mode == 'pic' else inactive)
        # 重建单选按钮
        self._rebuild_radio_buttons()
        # 显示/隐藏填入按钮
        self.fill_btn.setVisible(mode == 'pic')
        # 刷新表格
        self.refresh_table()

    def _on_fill_from_txt(self):
        """图片模式：从txt文件自动解析并填入数据到表格"""
        selected_item = self.radio_group.checkedButton().text()
        if not self.file_path:
            QMessageBox.warning(self, "警告", "未设置文件夹路径")
            return

        txt_path = os.path.join(self.file_path, f"{selected_item}.txt")
        if not os.path.exists(txt_path):
            QMessageBox.warning(self, "警告", f"未找到文件: {txt_path}")
            return

        try:
            with open(txt_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()

            txt_data = {}
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                parts = line.split()
                if len(parts) >= 1:
                    code = parts[0]
                    values = [v.replace(" ", "0").replace("`", "0") for v in parts[1:5]]
                    while len(values) < 4:
                        values.append('')
                    txt_data[code] = values

            filled = 0
            for row in range(self.table.rowCount()):
                code_item = self.table.item(row, 0)
                if code_item is None:
                    continue
                code = code_item.text()
                if code in txt_data:
                    for col_idx, val in enumerate(txt_data[code], start=2):
                        if col_idx < self.table.columnCount():
                            self.table.setItem(row, col_idx, QTableWidgetItem(val))
                    filled += 1

            if filled > 0:
                self.is_dirty = True
                self.logger.info(f"已从 {txt_path} 填入 {filled}/{len(txt_data)} 条数据")
                self.log_output.append(f"已从 {os.path.basename(txt_path)} 填入 {filled} 条数据")
            else:
                QMessageBox.warning(self, "提示", "未找到匹配的编号")
        except Exception as e:
            QMessageBox.warning(self, "警告", f"读取失败: {str(e)}")

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
                new_values = [self.table.item(row, col).text().replace(" ", "0").replace("`", "0") for col in range(2, 6)]
                self.data_storage[selected_item][code] = new_values
            self.is_dirty = True
        except Exception as e:
            logger.exception("保存数据时发生错误")
            QMessageBox.warning(self, "警告", f"保存失败：{str(e)}")

    def _clear_current_page(self):
        """清空当前页面所有输入内容及已保存数据"""
        reply = QMessageBox.question(
            self, '确认清空',
            '将清空当前页面所有输入内容及已保存数据，是否继续？',
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        if reply != QMessageBox.Yes:
            return
        try:
            selected_item = self.radio_group.checkedButton().text()
            # 清空表格显示
            for row in range(self.table.rowCount()):
                for col in range(2, self.table.columnCount()):
                    item = self.table.item(row, col)
                    if item is not None:
                        item.setText("")
            # 清空 data_storage 中对应的数据
            if selected_item in self.data_storage:
                for code in self.data_storage[selected_item]:
                    self.data_storage[selected_item][code] = ['', '', '', '']
                self.is_dirty = True
            self.logger.info(f"已清空 *{selected_item}* 的输入内容")
        except Exception as e:
            logger.exception("清空页面时发生错误")
            QMessageBox.warning(self, "警告", f"清空失败：{str(e)}")

    def _on_child_window_destroyed(self, obj):
        """子窗口销毁时，仅当它是当前窗口时才清除引用"""
        if self.current_window is obj:
            self.current_window = None

    def on_open_clicked(self):
        """
        打开文件：HTML模式打开HTML，图片模式打开txt
        """
        if self.current_window:
            self.current_window.close()
            self.current_window = None
        selected_item = self.radio_group.checkedButton().text()

        if self.data_mode == 'pic':
            # 图片模式：尝试打开对应的txt文件
            txt_path = None
            if self.file_path:
                txt_path = os.path.join(self.file_path, f"{selected_item}.txt")
            if not txt_path or not os.path.exists(txt_path):
                QMessageBox.warning(self, "警告", f"未找到对应的txt文件: {txt_path}")
                return
            try:
                with open(txt_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                dialog = QDialog(self)
                dialog.setWindowTitle(f"图片数据 - {selected_item}")
                dialog.setGeometry(200, 200, 600, 400)
                layout = QVBoxLayout()
                text_edit = QTextEdit()
                text_edit.setReadOnly(True)
                text_edit.setPlainText(content)
                layout.addWidget(text_edit)
                dialog.setLayout(layout)
                self.current_window = dialog
                self.current_window.destroyed.connect(self._on_child_window_destroyed)
                self.current_window.show()
            except Exception:
                QMessageBox.warning(self, "警告", "读取txt文件失败")
        else:
            # HTML模式：原有逻辑
            try:
                url = self.url[selected_item]
                self.current_window = NewWindow(selected_item,
                                              html_base_path=url,
                                              parent=self)
                self.current_window.destroyed.connect(self._on_child_window_destroyed)
                self.current_window.show()
            except:
                QMessageBox.warning(self, "警告", "文件路径不存在，或者文件名称错误")

            
    def export_data(self):
        """
        导出数据 - 主线程收集验证，后台线程写入（不阻塞UI）
        """
        self.save_changes()
        selected_item = self.radio_group.checkedButton().text()
        is_pic = (self.data_mode == 'pic' and selected_item in self.pic_categories)

        try:
            ex_header = self.pic_mapping[selected_item] if is_pic else self.mapping[selected_item]
        except Exception as e:
            logger.exception(f"映射表错误: 未找到键 '{selected_item}'")
            QMessageBox.warning(self, "错误", f"'{selected_item}'未匹配成功，请检查映射表")
            return 0

        logger.info(f'开始收集写入操作 *{selected_item}*')

        # 第一阶段：收集写操作并逐项验证（主线程，可弹窗）
        write_ops = []
        invalid_items = []

        for code, values in self.data_storage[selected_item].items():
            try:
                line_location, column_location = self.get_info.get_location(
                    code, ex_header, self.excel_first_columns
                )
                if line_location is None or column_location is None:
                    logger.error(f"get_location 返回 None for code={code}, ex_header={ex_header}")
                    continue

                # 验证每个分值，保持列位置不变
                validated_vals = []
                for val in values:
                    if is_pic:
                        # 图片模式：只拒绝空值，允许汉字直接通过
                        if val is None or str(val).strip() == "":
                            validated_vals.append('')
                        else:
                            validated_vals.append(str(val).strip())
                    else:
                        # HTML模式：标准验证
                        result = ExcelWriter.validate_value(val)
                        if result['valid']:
                            validated_vals.append(result['converted'])
                        else:
                            validated_vals.append('')  # 占位，保持列偏移正确
                            if val is not None and str(val).strip() != "":
                                invalid_items.append(f"code={code}, 值='{val}': {result['message']}")

                write_ops.append((line_location, column_location, validated_vals))

            except Exception as e:
                logger.exception(f"获取位置失败 - code: {code}")
                return 0

        # 发现无效数据时弹窗确认
        if invalid_items:
            detail = "\n".join(invalid_items[:20])
            if len(invalid_items) > 20:
                detail += f"\n... 还有 {len(invalid_items) - 20} 条"
            message = f"以下数据验证未通过:\n{detail}\n\n是否跳过无效项并继续写入？"
            reply = QMessageBox.question(self, '验证失败', message,
                                         QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if reply == QMessageBox.No:
                logger.warning(f'*{selected_item}* 用户取消写入（验证未通过）')
                return 0

        if not write_ops:
            logger.warning(f'*{selected_item}* 无有效写入操作')
            return 0

        logger.info(f'*{selected_item}* 共 {len(write_ops)} 条写入操作，开始后台写入')

        # 第二阶段：后台线程写入
        self._run_write_worker(write_ops, f"导出 {selected_item}")

    def _run_write_worker(self, write_ops, task_name):
        """启动后台写入线程，不阻塞UI"""
        # 等待上一个线程完全结束
        if self.worker_thread is not None:
            if self.worker_thread.isRunning():
                QMessageBox.warning(self, "提示", "已有写入任务正在进行，请等待完成")
                return
            # 等待线程彻底退出
            self.worker_thread.wait(3000)
            self.worker_thread = None

        from src.worker import ExcelWriteWorker

        self.worker_thread = QThread()
        self.worker = ExcelWriteWorker(
            self.writer.excel_path,
            getattr(self, 'sheet_name', None),
            write_ops
        )
        self.worker.moveToThread(self.worker_thread)

        # 连接信号
        self.worker_thread.started.connect(self.worker.run)
        self.worker.finished.connect(self.worker_thread.quit)
        self.worker.finished.connect(self._on_write_finished)
        self.worker.progress.connect(self._on_write_progress)
        self.worker_thread.finished.connect(self._on_thread_finished)

        self.worker_thread.start()

        # 进度对话框
        self.progress_dialog = QProgressDialog(
            f"正在{task_name}...", None, 0, len(write_ops), self
        )
        self.progress_dialog.setWindowTitle("请稍候")
        self.progress_dialog.setCancelButton(None)
        self.progress_dialog.setMinimumDuration(0)
        self.progress_dialog.show()

    def _on_thread_finished(self):
        """线程完成清理（避免 lambda 引用被覆盖的问题）"""
        if self.worker is not None:
            self.worker.deleteLater()
            self.worker = None
        self.worker_thread = None

    def _on_write_progress(self, current, total):
        """写入进度更新（主线程）"""
        if hasattr(self, 'progress_dialog') and self.progress_dialog:
            self.progress_dialog.setValue(current)
            self.progress_dialog.setLabelText(f"正在写入... ({current}/{total})")

    def _on_write_finished(self, success, message):
        """写入完成回调（主线程）"""
        if hasattr(self, 'progress_dialog') and self.progress_dialog:
            self.progress_dialog.close()
            self.progress_dialog = None

        if success:
            self.is_dirty = False
            logger.info(message)
            self.log_output.append(f"✅ {message}")
        else:
            logger.error(message)
            QMessageBox.critical(self, "错误", message)
    
    def sort(self):
        """
        排序 - 内存统计在主线程，写入在后台线程
        """
        try:
            stats = defaultdict(Counter)
            logger.info("开始排序")

            for name in self.data_storage:
                if name in self.pic_categories:
                    continue  # 图片模式数据不参与排序统计
                number_dict = self.data_storage[name]
                for number, values in number_dict.items():
                    for value in values:
                        if value.strip() and value.strip().isdigit():
                            stats[number][value] += 1

            dict_counter = {number: dict(counts.most_common()) for number, counts in stats.items()}

            # 收集写入操作（主线程）
            write_ops = []
            for column, contents in dict_counter.items():
                try:
                    _, column_location = self.get_info.get_location(header_num=column)
                    write_ops.append((84, column_location, contents))
                except Exception as e:
                    logger.exception(f"排序写入失败 - 列: {column}")

            if write_ops:
                self._run_write_worker(write_ops, "排序")

            logger.info("排序完成")
            return dict_counter
        except Exception as e:
            logger.exception("排序过程中发生错误")
            QMessageBox.critical(self, "错误", f"排序失败：{str(e)}")
            return None

    def export_json(self):
        """
        导出JSON文件 - 按比赛编号组织，便于跨sheet复用
        格式: {code: {category: [scores]}}
        """
        try:
            import json
            if not os.path.exists("./json"):
                os.makedirs("./json")

            # 转置为 code→category→scores 格式
            new_json_data = {}
            for category, codes in self.data_storage.items():
                for code, scores in codes.items():
                    if code not in new_json_data:
                        new_json_data[code] = {}
                    new_json_data[code][category] = scores

            json_path = f"./json/{datetime.now().strftime('%Y-%m-%d')}.json"
            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump(new_json_data, f, ensure_ascii=False, indent=4)
            logger.info(f"JSON文件导出成功: {json_path}")
            self.is_dirty = False
        except Exception as e:
            logger.exception("JSON导出失败")
            QMessageBox.critical(self, "错误", f"JSON导出失败：{str(e)}")
            return None

    def reload_paths(self):
        """
        重新选择路径并重新加载数据
        """
        try:
            # 先关闭打开的HTML窗口
            if self.current_window:
                self.current_window.close()
                self.current_window = None

            # 确认对话框
            dirty_msg = "，且有未保存的修改" if self.is_dirty else ""
            reply = QMessageBox.question(
                self, '确认重新选择',
                f'重新选择路径将关闭当前窗口{dirty_msg}，未保存的数据将会丢失。\n是否继续？',
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )
            if reply != QMessageBox.Yes:
                return

            # 关闭当前窗口
            self.close()

            # 重新运行路径选择器
            from window.table_qt_2 import PathSelector
            path_selector = PathSelector()
            result = path_selector.exec_()
            
            if result == QDialog.Accepted:
                folder_path, excel_path, json_path, sheet_name = path_selector.selected_paths
                
                # 验证路径有效性
                if not folder_path or not excel_path or not sheet_name:
                    QMessageBox.critical(None, "错误", "必须选择有效的文件夹、Excel文件和sheet")
                    return

                # 保存到 QSettings
                settings = QSettings("config.ini", QSettings.IniFormat)
                if not settings.value("paths/mapping_path"):
                    settings.setValue("paths/mapping_path", "mapping/mapping_data.txt")
                settings.setValue("paths/html_folder_path", folder_path)
                settings.setValue("paths/excel_path", excel_path)
                settings.setValue("paths/json_path", json_path)
                settings.setValue("paths/sheet_name", sheet_name)

                # 创建新的主窗口实例
                new_window = EnhancedDataEditor(excel_path=excel_path,
                                               file_path=folder_path,
                                               json_path=json_path,
                                               sheet_name=sheet_name)
                new_window.show()

        except Exception as e:
            logger.exception("重新加载路径时发生错误")
            QMessageBox.critical(None, "错误", f"重新加载失败：{str(e)}")

    def _open_settings(self):
        """打开设置对话框"""
        settings = QSettings("config.ini", QSettings.IniFormat)
        current_paths = {
            'mapping_path': settings.value("paths/mapping_path", "mapping/mapping_data.txt"),
            'html_folder_path': settings.value("paths/html_folder_path", ""),
            'excel_path': settings.value("paths/excel_path", ""),
            'json_path': settings.value("paths/json_path", ""),
            'sheet_name': settings.value("paths/sheet_name", ""),
        }

        dialog = SettingsDialog(current_paths, parent=self)
        if dialog.exec_() == QDialog.Accepted:
            new_paths = dialog.get_paths()
            self._reload_with_new_paths(new_paths)

    def _reload_with_new_paths(self, new_paths: dict):
        """根据新路径重新初始化数据"""
        html_folder = new_paths['html_folder_path']
        excel_path = new_paths['excel_path']
        json_path = new_paths['json_path']
        mapping_path = new_paths['mapping_path']
        sheet_name = new_paths.get('sheet_name', self.sheet_name)

        if not html_folder or not excel_path:
            QMessageBox.warning(self, "警告", "HTML文件夹路径和Excel路径不能为空")
            return

        if not sheet_name:
            QMessageBox.warning(self, "警告", "请选择Excel Sheet")
            return

        try:
            # 用新路径重新创建 GetWriteInfo（传入 mapping_path 和 sheet_name）
            self.get_info = GetWriteInfo(html_folder, excel_path, sheet_name, mapping_path)
            top_data = self.get_info.get_tabel_info()
            left_items, excel_name = self.get_info.get_file_and_excel_info()

            # 更新实例属性
            self.file_path = html_folder
            self.sheet_name = sheet_name
            self.top_data = top_data
            self.left_items = left_items
            self.flag = True
            self.fixed_values = {row[0]: row[1] for row in self.top_data}
            self.writer = ExcelWriter(excel_path, sheet_name)
            self.excel_first_columns = excel_name
            self.mapping = self.get_info.get_mapping()
            self.header_bases = self.get_info.get_header_bases()
            self.url = self.get_info.get_file_dict()

            # 重新构建 data_storage
            self.data_storage = {item: {row[0]: list(row[2:]) for row in self.top_data}
                               for item in self.left_items}

            # 重新加载图片模式配置
            self._load_pic_config()

            # 重新导入 JSON 数据
            if json_path and os.path.exists(json_path):
                json_data = self.get_info.get_json(json_path)
                if json_data and isinstance(json_data, dict):
                    first_key = next(iter(json_data))
                    first_val = json_data[first_key]
                    if isinstance(first_val, dict) and any(
                        isinstance(v, list) for v in first_val.values()
                    ):
                        for code, categories in json_data.items():
                            for category, scores in categories.items():
                                if category in self.data_storage and code in self.data_storage[category]:
                                    self.data_storage[category][code] = scores
                    else:
                        self.data_storage.update(json_data)

            # 重建单选按钮并刷新表格
            self._rebuild_radio_buttons()
            self.refresh_table()

            # 保存路径到 QSettings
            settings = QSettings("config.ini", QSettings.IniFormat)
            settings.setValue("paths/mapping_path", mapping_path)
            settings.setValue("paths/html_folder_path", html_folder)
            settings.setValue("paths/excel_path", excel_path)
            settings.setValue("paths/json_path", json_path)
            settings.setValue("paths/sheet_name", sheet_name)

            self.logger.info("设置已更新，数据已重新加载")

        except Exception as e:
            QMessageBox.critical(self, "错误", f"重新加载数据失败: {str(e)}")
            self.logger.exception("重新加载数据失败")

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